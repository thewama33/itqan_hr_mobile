from __future__ import annotations

import frappe

from itqan_hr_mobile.services.compatibility import field_exists, get_employee_user

logger = frappe.logger("itqan_hr_mobile")


def user_for_employee(employee: str | None) -> str | None:
	user = get_employee_user(employee)
	if employee and not user:
		logger.info("Skipping mobile notification: employee %s has no enabled linked user", employee)
	return user


def employee_for_user(user: str) -> str | None:
	if not field_exists("Employee", "user_id"):
		return None
	return frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name") or frappe.db.get_value(
		"Employee", {"user_id": user}, "name"
	)


def users_for_employees(employees: list[str]) -> list[tuple[str, str]]:
	resolved = []
	for employee in dict.fromkeys(employees):
		if user := user_for_employee(employee):
			resolved.append((employee, user))
	return resolved


def enabled_devices(user: str) -> list[dict]:
	return frappe.get_all(
		"Mobile Device",
		filters={"user": user, "enabled": 1},
		fields=["name", "fcm_token", "platform"],
	)


def approvers_for(doc) -> list[str]:
	users = []
	for field in ("leave_approver", "approver", "expense_approver"):
		value = doc.get(field)
		if value and frappe.db.exists("User", value):
			users.append(value)
	if not users and doc.get("employee") and field_exists("Employee", "leave_approver"):
		value = frappe.db.get_value("Employee", doc.employee, "leave_approver")
		if value:
			users.append(value)
	return [user for user in dict.fromkeys(users) if frappe.db.get_value("User", user, "enabled")]
