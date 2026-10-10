from frappe.utils import formatdate

from itqan_hr_mobile.events.common import employee_notification, guarded
from itqan_hr_mobile.services.notification_service import setting_enabled


@guarded
def on_submit(doc, method=None):
	if not setting_enabled("salary_notifications_enabled"):
		return
	month = formatdate(doc.get("end_date") or doc.get("start_date"), "MMMM yyyy")
	employee_notification(doc, "salary_slip_available", "salary_slip_details", {"month": month}, transition="docstatus|1")
