import frappe


def _is_admin(user: str) -> bool:
	return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def device_query(user=None):
	user = user or frappe.session.user
	return None if _is_admin(user) else f"`tabMobile Device`.`user` = {frappe.db.escape(user)}"


def notification_query(user=None):
	user = user or frappe.session.user
	return None if _is_admin(user) else f"`tabMobile Notification`.`user` = {frappe.db.escape(user)}"


def device_permission(doc, user=None, permission_type=None):
	user = user or frappe.session.user
	return _is_admin(user) or doc.user == user


def notification_permission(doc, user=None, permission_type=None):
	user = user or frappe.session.user
	return _is_admin(user) or doc.user == user
