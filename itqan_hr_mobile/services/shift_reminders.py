from __future__ import annotations

from datetime import datetime, time, timedelta

import frappe
from frappe.utils import add_days, getdate, now_datetime

from itqan_hr_mobile.services.compatibility import doctype_exists, field_exists
from itqan_hr_mobile.services.notification_service import notify, setting_enabled
from itqan_hr_mobile.services.recipient_resolver import user_for_employee

logger = frappe.logger("itqan_hr_mobile")


def process_shift_reminders(now: datetime | None = None):
	if not setting_enabled("shift_notifications_enabled"):
		return
	if not _compatible():
		return
	settings = frappe.get_single("Mobile Notification Settings")
	rules = []
	if settings.shift_start_reminder_enabled:
		rules.append(("start", max(0, min(int(settings.shift_start_reminder_minutes or 0), 1440))))
	if settings.shift_end_reminder_enabled:
		rules.append(("end", max(0, min(int(settings.shift_end_reminder_minutes or 0), 1440))))
	if settings.missing_checkin_reminder_enabled:
		rules.append(("missing_checkin", max(0, min(int(settings.missing_checkin_grace_minutes or 0), 1440))))
	if not rules:
		return
	now = now or now_datetime()
	for assignment in _assignments_near(now):
		try:
			_process_assignment(assignment, rules, now)
		except Exception:
			logger.exception("Shift reminder failed for assignment %s", assignment.name)


def _compatible() -> bool:
	required = (("Shift Assignment", "employee"), ("Shift Assignment", "shift_type"), ("Shift Type", "start_time"), ("Shift Type", "end_time"))
	if not all(doctype_exists(dt) and field_exists(dt, field) for dt, field in required):
		logger.warning("Shift reminders skipped: compatible Shift Assignment/Shift Type fields are unavailable")
		return False
	return True


def _assignments_near(now: datetime) -> list[dict]:
	yesterday, tomorrow = add_days(now.date(), -1), add_days(now.date(), 1)
	return frappe.get_all(
		"Shift Assignment",
		filters={"docstatus": 1, "status": "Active", "start_date": ("<=", tomorrow)},
		or_filters=[["end_date", ">=", yesterday], ["end_date", "is", "not set"]],
		fields=["name", "employee", "shift_type", "start_date", "end_date"],
		limit_page_length=5000,
	)


def _process_assignment(assignment, rules: list[tuple[str, int]], now: datetime):
	fields = ["start_time", "end_time"]
	if field_exists("Shift Type", "begin_check_in_before_shift_start_time"):
		fields.append("begin_check_in_before_shift_start_time")
	times = frappe.db.get_value("Shift Type", assignment.shift_type, fields, as_dict=True)
	if not times or times.start_time is None or times.end_time is None:
		return
	user = user_for_employee(assignment.employee)
	if not user:
		return
	for shift_date in (add_days(now.date(), -1), now.date(), add_days(now.date(), 1)):
		if getdate(assignment.start_date) > getdate(shift_date) or (assignment.end_date and getdate(assignment.end_date) < getdate(shift_date)):
			continue
		start = datetime.combine(getdate(shift_date), _as_time(times.start_time))
		end = datetime.combine(getdate(shift_date), _as_time(times.end_time))
		if end <= start:
			end += timedelta(days=1)
		for boundary, minutes in rules:
			shift_datetime = start if boundary in ("start", "missing_checkin") else end
			target = shift_datetime + timedelta(minutes=minutes) if boundary == "missing_checkin" else shift_datetime - timedelta(minutes=minutes)
			if target <= now < target + timedelta(minutes=10):
				if boundary == "missing_checkin" and _has_checkin(assignment.employee, start, now, times.get("begin_check_in_before_shift_start_time") or 0):
					continue
				_type = "attendance_missing_checkin" if boundary == "missing_checkin" else f"shift_{boundary}_reminder"
				notify(
					user=user, employee=assignment.employee, notification_type=_type,
					reference_doctype="Shift Assignment", reference_name=assignment.name,
					route="employee_checkin" if boundary == "missing_checkin" else "shift_details",
					route_params={"name": assignment.name, "date": str(shift_date)},
					event_key=f"Shift Assignment|{assignment.name}|{shift_date}|{boundary}|{minutes}",
					context={"shift": assignment.shift_type, "time": shift_datetime.strftime("%I:%M %p")},
				)


def _has_checkin(employee: str, shift_start: datetime, now: datetime, early_minutes: int) -> bool:
	if not doctype_exists("Employee Checkin") or not field_exists("Employee Checkin", "time"):
		# Without a reliable check-in source, do not risk false reminders.
		return True
	window_start = shift_start - timedelta(minutes=int(early_minutes or 0))
	fields = ["name"]
	if field_exists("Employee Checkin", "log_type"):
		fields.append("log_type")
	logs = frappe.get_all(
		"Employee Checkin",
		filters={"employee": employee, "time": ("between", [window_start, now])},
		fields=fields, order_by="time asc", limit_page_length=20,
	)
	return any(not row.get("log_type") or row.get("log_type") == "IN" for row in logs)


def _as_time(value) -> time:
	if isinstance(value, time):
		return value
	if isinstance(value, timedelta):
		seconds = int(value.total_seconds()) % 86400
		return time(seconds // 3600, (seconds % 3600) // 60, seconds % 60)
	return time.fromisoformat(str(value))
