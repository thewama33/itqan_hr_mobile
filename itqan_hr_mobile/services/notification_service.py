from __future__ import annotations

import json

import frappe
from frappe.utils import now_datetime

from itqan_hr_mobile.services import firebase
from itqan_hr_mobile.services.compatibility import doctype_exists
from itqan_hr_mobile.services.recipient_resolver import enabled_devices
from itqan_hr_mobile.services.templates import render

logger = frappe.logger("itqan_hr_mobile")


def setting_enabled(fieldname: str, default: bool = True) -> bool:
	if not doctype_exists("Mobile Notification Settings"):
		return default
	try:
		master = frappe.db.get_single_value("Mobile Notification Settings", "enabled")
		feature = frappe.db.get_single_value("Mobile Notification Settings", fieldname)
		return bool(master if master is not None else 1) and bool(feature if feature is not None else default)
	except Exception:
		return default


def notify(
	*, user: str, employee: str | None, notification_type: str, reference_doctype: str | None = None,
	reference_name: str | None = None, route: str | None = None, route_params: dict | None = None,
	event_key: str | None = None, context: dict | None = None, title: str | None = None,
	body: str | None = None, priority: str = "Normal",
	enqueue_push: bool = True,
) -> str | None:
	if not user or user == "Guest" or not frappe.db.get_value("User", user, "enabled"):
		return None
	if event_key and frappe.db.exists("Mobile Notification", {"event_key": event_key, "user": user}):
		return None
	if not (title and body):
		title, body = render(notification_type, user, context)
	doc = frappe.get_doc({
		"doctype": "Mobile Notification", "user": user, "employee": employee,
		"notification_type": notification_type, "title": title, "body": body,
		"reference_doctype": reference_doctype, "reference_name": reference_name,
		"route": route, "route_params_json": json.dumps(route_params or {}, ensure_ascii=False),
		"priority": priority, "push_status": "Pending", "event_key": event_key,
	})
	doc.insert(ignore_permissions=True)
	if enqueue_push:
		frappe.db.set_value("Mobile Notification", doc.name, "push_status", "Queued", update_modified=False)
		frappe.enqueue(
			"itqan_hr_mobile.services.notification_service.deliver_notification",
			queue="short", enqueue_after_commit=True, notification_name=doc.name,
			job_id=f"mobile-notification-{doc.name}", deduplicate=True,
		)
	else:
		frappe.db.set_value("Mobile Notification", doc.name, {"push_status": "Skipped", "error_message": "Push disabled for this notification"}, update_modified=False)
	_create_system_notification(doc)
	return doc.name


def deliver_notification(notification_name: str, force: bool = False) -> None:
	doc = frappe.get_doc("Mobile Notification", notification_name)
	if doc.push_status == "Sent" and not force:
		return
	if not setting_enabled("firebase_enabled"):
		_set_delivery(doc.name, "Skipped", error="Firebase delivery is disabled")
		return
	devices = enabled_devices(doc.user)
	if not devices:
		_set_delivery(doc.name, "Skipped", error="No enabled mobile devices")
		return
	payload = {
		"type": doc.notification_type,
		"reference_doctype": doc.reference_doctype,
		"reference_name": doc.reference_name,
		"route": doc.route,
		"route_params": doc.route_params_json or "{}",
		"notification_name": doc.name,
	}
	message_ids, errors = [], []
	for device in devices:
		try:
			message_ids.append(firebase.send_to_token(device.fcm_token, doc.title, doc.body, payload))
		except Exception as exc:
			if firebase.is_invalid_token_error(exc):
				frappe.db.set_value("Mobile Device", device.name, "enabled", 0, update_modified=False)
			errors.append(firebase.sanitized_error(exc))
	if message_ids:
		_set_delivery(doc.name, "Sent", message_id=message_ids[0], error="; ".join(errors))
	else:
		_set_delivery(doc.name, "Failed", error="; ".join(errors) or "FCM delivery failed")
		logger.warning("Mobile notification %s delivery failed: %s", doc.name, "; ".join(errors))


def retry_failed(notification_name: str) -> None:
	status, retry_count = frappe.db.get_value("Mobile Notification", notification_name, ["push_status", "retry_count"])
	max_retries = int(frappe.db.get_single_value("Mobile Notification Settings", "max_retry_count") or 2)
	if status != "Failed" or int(retry_count or 0) >= max_retries:
		return
	frappe.db.set_value("Mobile Notification", notification_name, "retry_count", int(retry_count or 0) + 1, update_modified=False)
	frappe.enqueue(
		"itqan_hr_mobile.services.notification_service.deliver_notification",
		queue="short", notification_name=notification_name, force=True,
		job_id=f"mobile-notification-retry-{notification_name}-{frappe.generate_hash(length=6)}",
	)


def _set_delivery(name: str, status: str, message_id: str | None = None, error: str | None = None):
	values = {"push_status": status, "push_sent": status == "Sent", "error_message": (error or "")[:500]}
	if status == "Sent":
		values.update(push_sent_at=now_datetime(), firebase_message_id=message_id)
	frappe.db.set_value("Mobile Notification", name, values, update_modified=False)


def _create_system_notification(doc):
	if not setting_enabled("send_system_notification", default=False) or not doctype_exists("Notification Log"):
		return
	try:
		frappe.get_doc({
			"doctype": "Notification Log", "for_user": doc.user, "subject": doc.title,
			"email_content": doc.body, "type": "Alert", "document_type": doc.reference_doctype,
			"document_name": doc.reference_name,
		}).insert(ignore_permissions=True)
	except Exception:
		logger.exception("Could not create system notification for %s", doc.name)
