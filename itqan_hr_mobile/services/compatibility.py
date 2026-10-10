from __future__ import annotations

import frappe


def doctype_exists(doctype: str) -> bool:
	try:
		return bool(frappe.db.exists("DocType", doctype))
	except Exception:
		return False


def field_exists(doctype: str, fieldname: str) -> bool:
	try:
		return doctype_exists(doctype) and bool(frappe.get_meta(doctype).has_field(fieldname))
	except Exception:
		return False


def get_employee_user(employee: str | None) -> str | None:
	if not employee or not doctype_exists("Employee") or not field_exists("Employee", "user_id"):
		return None
	user = frappe.db.get_value("Employee", employee, "user_id")
	if not user or user == "Guest":
		return None
	return user if frappe.db.get_value("User", user, "enabled") else None


def safe_get_before_save(doc):
	try:
		return doc.get_doc_before_save()
	except Exception:
		return getattr(doc, "_doc_before_save", None)


def old_value(doc, fieldname: str):
	before = safe_get_before_save(doc)
	return before.get(fieldname) if before else None


def changed(doc, fieldname: str) -> bool:
	before = safe_get_before_save(doc)
	return bool(before and before.get(fieldname) != doc.get(fieldname))


def is_hrms_installed() -> bool:
	try:
		return "hrms" in frappe.get_installed_apps()
	except Exception:
		return False


def get_frappe_major_version() -> int:
	try:
		return int(frappe.__version__.split(".", 1)[0])
	except (AttributeError, TypeError, ValueError):
		return 0


def get_workflow_state_field(doctype: str) -> str | None:
	for candidate in ("workflow_state", "status"):
		if field_exists(doctype, candidate):
			return candidate
	return None
