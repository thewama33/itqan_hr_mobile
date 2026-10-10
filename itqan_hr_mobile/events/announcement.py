import frappe

from itqan_hr_mobile.events.common import guarded
from itqan_hr_mobile.services.notification_service import setting_enabled


@guarded
def on_change(doc, method=None):
	if doc.docstatus != 1 or doc.published or not setting_enabled("announcement_notifications_enabled"):
		return
	frappe.enqueue(
		"itqan_hr_mobile.services.announcements.publish_announcement",
		queue="long", enqueue_after_commit=True, announcement_name=doc.name,
		job_id=f"mobile-announcement-{doc.name}", deduplicate=True,
	)
