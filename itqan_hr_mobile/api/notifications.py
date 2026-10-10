from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, now_datetime


def _user():
	if not frappe.session.user or frappe.session.user == "Guest":
		frappe.throw(_("Authentication is required"), frappe.PermissionError)
	return frappe.session.user


def _owned(name):
	if not frappe.db.exists("Mobile Notification", {"name": name, "user": _user()}):
		frappe.throw(_("Notification not found"), frappe.DoesNotExistError)


@frappe.whitelist(methods=["GET"])
def get_notifications(limit=20, offset=0, unread_only=0):
	limit, offset = min(max(cint(limit), 1), 100), max(cint(offset), 0)
	filters = {"user": _user()}
	if cint(unread_only):
		filters["read"] = 0
	rows = frappe.get_all("Mobile Notification", filters=filters, fields=["name", "notification_type", "title", "body", "creation", "read", "reference_doctype", "reference_name", "route", "route_params_json", "priority", "push_status"], order_by="creation desc", limit_start=offset, limit_page_length=limit)
	for row in rows:
		row["type"] = row.pop("notification_type")
		try:
			row["route_params"] = json.loads(row.pop("route_params_json") or "{}")
		except ValueError:
			row["route_params"] = {}
	return rows


@frappe.whitelist(methods=["POST"])
def mark_as_read(notification_name):
	_owned(notification_name)
	frappe.db.set_value("Mobile Notification", notification_name, {"read": 1, "read_at": now_datetime()}, update_modified=False)
	return {"name": notification_name, "read": 1}


@frappe.whitelist(methods=["POST"])
def mark_all_as_read():
	user = _user()
	frappe.db.set_value("Mobile Notification", {"user": user, "read": 0}, {"read": 1, "read_at": now_datetime()}, update_modified=False)
	return {"updated": True}


@frappe.whitelist(methods=["GET"])
def get_unread_count():
	return {"count": frappe.db.count("Mobile Notification", {"user": _user(), "read": 0})}


@frappe.whitelist(methods=["POST"])
def delete_my_notification(notification_name):
	_owned(notification_name)
	frappe.delete_doc("Mobile Notification", notification_name, ignore_permissions=True)
	return {"deleted": True}
