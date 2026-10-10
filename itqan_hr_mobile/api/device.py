from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now_datetime

from itqan_hr_mobile.services.recipient_resolver import employee_for_user


def _user() -> str:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Authentication is required"), frappe.PermissionError)
	if not frappe.db.get_value("User", user, "enabled"):
		frappe.throw(_("User is disabled"), frappe.PermissionError)
	return user


def _required(value: str | None, label: str, max_length: int = 1024) -> str:
	value = str(value or "").strip()
	if not value:
		frappe.throw(_("{0} is required").format(label))
	if len(value) > max_length:
		frappe.throw(_("{0} is too long").format(label))
	return value


@frappe.whitelist(methods=["POST"])
def register_device(device_id, fcm_token, platform="Other", device_name=None, app_version=None, os_version=None):
	user = _user()
	device_id = _required(device_id, "device_id", 255)
	fcm_token = _required(fcm_token, "fcm_token", 4096)
	if platform not in ("Android", "iOS", "Other"):
		frappe.throw(_("Invalid platform"))
	# An FCM registration token identifies one app installation. If the same
	# installation signs in as another user, leaving its old record enabled
	# could disclose that user's future notifications.
	for stale_name in frappe.get_all(
		"Mobile Device", filters={"fcm_token": fcm_token, "user": ("!=", user), "enabled": 1}, pluck="name"
	):
		frappe.db.set_value("Mobile Device", stale_name, "enabled", 0, update_modified=False)
	name = frappe.db.exists("Mobile Device", {"user": user, "device_id": device_id})
	values = {
		"employee": employee_for_user(user), "fcm_token": fcm_token, "platform": platform,
		"device_name": str(device_name or "")[:255], "app_version": str(app_version or "")[:255],
		"os_version": str(os_version or "")[:255], "enabled": 1, "last_seen": now_datetime(),
		"token_updated_at": now_datetime(),
	}
	if name:
		frappe.db.set_value("Mobile Device", name, values)
	else:
		doc = frappe.get_doc({"doctype": "Mobile Device", "user": user, "device_id": device_id, **values})
		doc.created_from_ip = getattr(frappe.local, "request_ip", None)
		doc.insert(ignore_permissions=True)
		name = doc.name
	return {"name": name, "device_id": device_id, "enabled": 1}


@frappe.whitelist(methods=["POST"])
def update_device_token(device_id, fcm_token):
	user = _user()
	name = _owned_device(user, device_id)
	frappe.db.set_value("Mobile Device", name, {"fcm_token": _required(fcm_token, "fcm_token", 4096), "enabled": 1, "token_updated_at": now_datetime(), "last_seen": now_datetime()})
	return {"name": name, "updated": True}


@frappe.whitelist(methods=["POST"])
def unregister_device(device_id):
	user = _user()
	name = _owned_device(user, device_id)
	frappe.db.set_value("Mobile Device", name, {"enabled": 0, "last_seen": now_datetime()})
	return {"name": name, "enabled": 0}


@frappe.whitelist(methods=["POST"])
def heartbeat(device_id, app_version=None, os_version=None):
	user = _user()
	name = _owned_device(user, device_id)
	values = {"last_seen": now_datetime()}
	if app_version is not None:
		values["app_version"] = str(app_version)[:255]
	if os_version is not None:
		values["os_version"] = str(os_version)[:255]
	frappe.db.set_value("Mobile Device", name, values)
	return {"name": name, "last_seen": values["last_seen"]}


@frappe.whitelist(methods=["GET"])
def list_my_devices():
	return frappe.get_all("Mobile Device", filters={"user": _user()}, fields=["name", "device_id", "platform", "device_name", "app_version", "os_version", "enabled", "last_seen", "token_updated_at"], order_by="last_seen desc")


def _owned_device(user, device_id):
	name = frappe.db.exists("Mobile Device", {"user": user, "device_id": _required(device_id, "device_id", 255)})
	if not name:
		frappe.throw(_("Device not found"), frappe.DoesNotExistError)
	return name
