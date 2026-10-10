from itqan_hr_mobile.events.common import employee_notification, guarded, manager_approval_notifications
from itqan_hr_mobile.services.compatibility import get_workflow_state_field, old_value
from itqan_hr_mobile.services.notification_service import setting_enabled


@guarded
def after_insert(doc, method=None):
	manager_approval_notifications(doc, "attendance_request_details")


@guarded
def on_change(doc, method=None):
	if not setting_enabled("attendance_notifications_enabled"):
		return
	field = get_workflow_state_field(doc.doctype)
	state = str(doc.get(field) or "") if field else ""
	old = str(old_value(doc, field) or "") if field else ""
	if state.lower() in ("approved", "rejected") and state != old:
		employee_notification(doc, f"attendance_request_{state.lower()}", "attendance_request_details", transition=f"{field}|{state}")


@guarded
def on_submit(doc, method=None):
	field = get_workflow_state_field(doc.doctype)
	state = str(doc.get(field) or "").lower() if field else ""
	if setting_enabled("attendance_notifications_enabled") and state not in ("approved", "rejected"):
		employee_notification(doc, "attendance_request_approved", "attendance_request_details", transition="docstatus|1")


@guarded
def on_cancel(doc, method=None):
	# A workflow rejection is handled in on_change. Cancellation has no stable rejection meaning.
	return None


def notify_approver_on_draft(doc):
	manager_approval_notifications(doc, "attendance_request_details")
