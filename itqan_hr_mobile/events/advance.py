from itqan_hr_mobile.events.common import employee_notification, guarded, manager_approval_notifications
from itqan_hr_mobile.services.compatibility import get_workflow_state_field, old_value
from itqan_hr_mobile.services.notification_service import setting_enabled


@guarded
def after_insert(doc, method=None):
	manager_approval_notifications(doc, "employee_advance_details")


@guarded
def on_change(doc, method=None):
	if not setting_enabled("employee_advance_notifications_enabled"):
		return
	field = get_workflow_state_field(doc.doctype)
	state = str(doc.get(field) or "") if field else ""
	old = str(old_value(doc, field) or "") if field else ""
	mapping = {"approved": "employee_advance_approved", "rejected": "employee_advance_rejected", "paid": "employee_advance_paid"}
	if state.lower() in mapping and state != old:
		employee_notification(doc, mapping[state.lower()], "employee_advance_details", transition=f"{field}|{state}")


@guarded
def on_submit(doc, method=None):
	field = get_workflow_state_field(doc.doctype)
	state = str(doc.get(field) or "").lower() if field else ""
	if setting_enabled("employee_advance_notifications_enabled") and state not in ("approved", "rejected"):
		employee_notification(doc, "employee_advance_approved", "employee_advance_details", transition="docstatus|1")
