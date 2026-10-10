from __future__ import annotations

import frappe

from itqan_hr_mobile.services.notification_service import notify, setting_enabled
from itqan_hr_mobile.services.recipient_resolver import approvers_for, user_for_employee

logger = frappe.logger("itqan_hr_mobile")


def employee_notification(doc, notification_type, route, context=None, transition=None, **kwargs):
	user = user_for_employee(doc.get("employee"))
	if not user:
		return
	transition = transition or notification_type
	notify(
		user=user, employee=doc.get("employee"), notification_type=notification_type,
		reference_doctype=doc.doctype, reference_name=doc.name, route=route,
		route_params={"name": doc.name}, event_key=f"{doc.doctype}|{doc.name}|{transition}",
		context=context or {}, **kwargs,
	)


def manager_approval_notifications(doc, route):
	if not setting_enabled("manager_notifications_enabled"):
		return
	for approver in approvers_for(doc):
		notify(
			user=approver, employee=None, notification_type="manager_approval_required",
			reference_doctype=doc.doctype, reference_name=doc.name, route=route,
			route_params={"name": doc.name}, event_key=f"{doc.doctype}|{doc.name}|approval|required|{approver}",
			context={"employee_name": doc.get("employee_name") or doc.get("employee")},
		)


def guarded(handler):
	def wrapper(doc, method=None):
		try:
			return handler(doc, method)
		except Exception:
			logger.exception("Mobile notification handler failed for %s %s", doc.doctype, doc.name)
	return wrapper
