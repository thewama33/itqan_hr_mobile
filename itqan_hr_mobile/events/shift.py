from itqan_hr_mobile.events.common import employee_notification, guarded
from itqan_hr_mobile.services.compatibility import changed
from itqan_hr_mobile.services.notification_service import setting_enabled


@guarded
def after_insert(doc, method=None):
	if setting_enabled("shift_notifications_enabled"):
		employee_notification(doc, "shift_assigned", "shift_assignment_details", {"shift": doc.get("shift_type"), "start_date": doc.get("start_date")}, transition="assigned")


@guarded
def on_change(doc, method=None):
	if setting_enabled("shift_notifications_enabled") and any(changed(doc, field) for field in ("shift_type", "start_date", "end_date", "status")):
		value = "|".join(str(doc.get(field) or "") for field in ("shift_type", "start_date", "end_date", "status"))
		employee_notification(doc, "shift_changed", "shift_assignment_details", {"shift": doc.get("shift_type")}, transition=f"changed|{value}")
