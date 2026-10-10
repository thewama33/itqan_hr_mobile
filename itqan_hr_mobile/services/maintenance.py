import frappe
from frappe.utils import add_days, now_datetime

from itqan_hr_mobile.services.compatibility import doctype_exists


def disable_stale_devices():
	if not doctype_exists("Mobile Device"):
		return
	try:
		days = int(frappe.db.get_single_value("Mobile Notification Settings", "device_stale_days") or 0)
	except (TypeError, ValueError):
		return
	if days <= 0:
		return
	cutoff = add_days(now_datetime(), -days)
	for name in frappe.get_all("Mobile Device", filters={"enabled": 1, "last_seen": ("<", cutoff)}, pluck="name", limit_page_length=1000):
		frappe.db.set_value("Mobile Device", name, "enabled", 0, update_modified=False)
