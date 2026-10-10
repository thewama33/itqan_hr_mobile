from __future__ import annotations

import frappe
from frappe.utils import now_datetime

from itqan_hr_mobile.services.notification_service import notify
from itqan_hr_mobile.services.recipient_resolver import users_for_employees


def publish_due_announcements():
	for name in frappe.get_all(
		"Mobile Announcement",
		filters={"docstatus": 1, "published": 0, "publish_from": ("<=", now_datetime())},
		pluck="name", limit_page_length=100,
	):
		publish_announcement(name)


def publish_announcement(announcement_name: str):
	doc = frappe.get_doc("Mobile Announcement", announcement_name)
	if doc.docstatus != 1 or doc.published:
		return
	now = now_datetime()
	if doc.publish_from and doc.publish_from > now:
		return
	if doc.publish_to and doc.publish_to < now:
		frappe.db.set_value(doc.doctype, doc.name, "published", 1, update_modified=False)
		return
	employees = _employees(doc)
	for employee, user in users_for_employees(employees):
		notify(
			user=user, employee=employee, notification_type="hr_announcement", title=doc.title,
			body=doc.message, reference_doctype=doc.doctype, reference_name=doc.name,
			route="announcement_details", route_params={"name": doc.name},
			event_key=f"Mobile Announcement|{doc.name}|published|{user}", priority=doc.priority,
			enqueue_push=bool(doc.send_push),
		)
	frappe.db.set_value(doc.doctype, doc.name, "published", 1, update_modified=False)


def _employees(doc) -> list[str]:
	if doc.audience_type == "Selected Employees":
		return [row.employee for row in doc.specific_employees]
	filters = {"status": "Active"}
	field = {"Company": "company", "Department": "department", "Branch": "branch", "Designation": "designation"}.get(doc.audience_type)
	if field:
		filters[field] = doc.get(field)
	return frappe.get_all("Employee", filters=filters, pluck="name")
