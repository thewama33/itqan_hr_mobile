from __future__ import annotations

import frappe

MESSAGES = {
	"leave_approved": {
		"en": ("Leave Request Approved", "Your leave request from {from_date} to {to_date} has been approved."),
		"ar": ("تمت الموافقة على طلب الإجازة", "تمت الموافقة على طلب إجازتك من {from_date} إلى {to_date}."),
	},
	"leave_rejected": {
		"en": ("Leave Request Rejected", "Your leave request from {from_date} to {to_date} has been rejected."),
		"ar": ("تم رفض طلب الإجازة", "تم رفض طلب إجازتك من {from_date} إلى {to_date}."),
	},
	"leave_cancelled": {"en": ("Leave Request Cancelled", "Your leave request has been cancelled."), "ar": ("تم إلغاء طلب الإجازة", "تم إلغاء طلب إجازتك.")},
	"attendance_request_approved": {"en": ("Attendance Request Approved", "Your attendance request has been approved."), "ar": ("تمت الموافقة على طلب الحضور", "تمت الموافقة على طلب الحضور الخاص بك.")},
	"attendance_request_rejected": {"en": ("Attendance Request Rejected", "Your attendance request has been rejected."), "ar": ("تم رفض طلب الحضور", "تم رفض طلب الحضور الخاص بك.")},
	"employee_advance_approved": {"en": ("Employee Advance Approved", "Your employee advance has been approved."), "ar": ("تمت الموافقة على السلفة", "تمت الموافقة على طلب السلفة الخاص بك.")},
	"employee_advance_rejected": {"en": ("Employee Advance Rejected", "Your employee advance has been rejected."), "ar": ("تم رفض السلفة", "تم رفض طلب السلفة الخاص بك.")},
	"employee_advance_paid": {"en": ("Employee Advance Paid", "Your employee advance has been paid."), "ar": ("تم دفع السلفة", "تم دفع السلفة الخاصة بك.")},
	"salary_slip_available": {"en": ("Salary Slip Available", "Your salary slip for {month} is now available."), "ar": ("قسيمة الراتب متاحة", "قسيمة راتب شهر {month} أصبحت متاحة الآن.")},
	"shift_assigned": {"en": ("Shift Assigned", "You have been assigned to {shift} from {start_date}."), "ar": ("تم تعيين وردية", "تم تعيينك في وردية {shift} اعتباراً من {start_date}.")},
	"shift_changed": {"en": ("Shift Updated", "Your shift assignment has been updated to {shift}."), "ar": ("تم تحديث الوردية", "تم تحديث تعيين ورديتك إلى {shift}.")},
	"shift_start_reminder": {"en": ("Shift Starting Soon", "Your {shift} shift starts at {time}."), "ar": ("تبدأ ورديتك قريبًا", "تبدأ وردية {shift} الساعة {time}.")},
	"shift_end_reminder": {"en": ("Shift Ending Soon", "Your {shift} shift ends at {time}."), "ar": ("تنتهي ورديتك قريبًا", "تنتهي وردية {shift} الساعة {time}.")},
	"attendance_missing_checkin": {"en": ("Check-in Reminder", "No check-in was recorded for your {shift} shift starting at {time}."), "ar": ("تذكير بتسجيل الحضور", "لم يتم تسجيل حضورك لوردية {shift} التي تبدأ الساعة {time}.")},
	"manager_approval_required": {"en": ("New Request", "{employee_name} submitted a request requiring your approval."), "ar": ("طلب جديد", "قدم {employee_name} طلباً يحتاج إلى موافقتك.")},
}


def language_for_user(user: str) -> str:
	language = frappe.db.get_value("User", user, "language")
	if not language:
		try:
			language = frappe.db.get_single_value("Mobile Notification Settings", "default_language")
		except Exception:
			language = None
	return "ar" if str(language or "en").lower().startswith("ar") else "en"


def render(notification_type: str, user: str, context: dict | None = None) -> tuple[str, str]:
	context = context or {}
	variants = MESSAGES.get(notification_type, {})
	title, body = variants.get(language_for_user(user), variants.get("en", (notification_type.replace("_", " ").title(), "")))
	return title.format_map(_SafeDict(context)), body.format_map(_SafeDict(context))


class _SafeDict(dict):
	def __missing__(self, key):
		return "{" + key + "}"
