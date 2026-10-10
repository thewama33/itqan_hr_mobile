from itqan_hr_mobile.events.common import employee_notification, guarded, manager_approval_notifications
from itqan_hr_mobile.services.compatibility import old_value
from itqan_hr_mobile.services.notification_service import setting_enabled


@guarded
def on_change(doc, method=None):
	if not setting_enabled("leave_notifications_enabled"):
		return
	old_status, status = old_value(doc, "status"), doc.get("status")
	if status in ("Approved", "Rejected") and old_status != status:
		employee_notification(
			doc, f"leave_{status.lower()}", "leave_details",
			{"from_date": doc.get("from_date"), "to_date": doc.get("to_date")}, transition=f"status|{status}",
		)
	if doc.docstatus == 0 and (not old_status or old_status == "Open"):
		manager_approval_notifications(doc, "leave_details")


@guarded
def on_cancel(doc, method=None):
	if setting_enabled("leave_notifications_enabled"):
		employee_notification(doc, "leave_cancelled", "leave_details", transition="docstatus|2")
