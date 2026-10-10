from __future__ import annotations

import frappe
from frappe.utils import add_days, getdate, nowdate

from itqan_hr_mobile.services.compatibility import doctype_exists, field_exists
from itqan_hr_mobile.services.notification_service import notify, setting_enabled
from itqan_hr_mobile.services.recipient_resolver import user_for_employee

logger = frappe.logger("itqan_hr_mobile")


def send_document_expiry_reminders():
	if not setting_enabled("document_expiry_notifications_enabled", default=False):
		return
	settings = frappe.get_single("Mobile Notification Settings")
	for rule in settings.get("expiry_rules") or []:
		if not rule.enabled or not _valid_rule(rule):
			continue
		for days in _thresholds(rule.days_before_expiry):
			_send_for_rule(rule, days)


def _valid_rule(rule) -> bool:
	valid = doctype_exists(rule.reference_doctype) and field_exists(rule.reference_doctype, rule.date_field) and field_exists(rule.reference_doctype, rule.employee_field)
	if not valid:
		logger.warning("Skipping invalid document expiry rule for %s", rule.reference_doctype)
	return valid


def _thresholds(value) -> list[int]:
	result = []
	for item in str(value or "").split(","):
		try:
			days = int(item.strip())
			if 0 <= days <= 3660:
				result.append(days)
		except ValueError:
			continue
	return sorted(set(result), reverse=True)


def _send_for_rule(rule, days: int):
	expiry_date = add_days(nowdate(), days)
	rows = frappe.get_all(rule.reference_doctype, filters={rule.date_field: expiry_date}, fields=["name", rule.employee_field, rule.date_field], limit_page_length=1000)
	for row in rows:
		employee = row.get(rule.employee_field)
		if not (user := user_for_employee(employee)):
			continue
		context = {"expiry_date": getdate(row.get(rule.date_field)), "days": days, "name": row.name}
		notify(
			user=user, employee=employee, notification_type="document_expiry_warning",
			title=(rule.notification_title or "Document Expiry Reminder").format_map(_Safe(context)),
			body=(rule.notification_body or "Your document expires on {expiry_date}.").format_map(_Safe(context)),
			reference_doctype=rule.reference_doctype, reference_name=row.name, route=rule.route,
			route_params={"name": row.name},
			event_key=f"{rule.reference_doctype}|{row.name}|expiry|{expiry_date}|{days}",
		)


class _Safe(dict):
	def __missing__(self, key):
		return "{" + key + "}"
