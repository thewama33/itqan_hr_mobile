import json

import frappe
from frappe import _
from frappe.model.document import Document

from itqan_hr_mobile.services import firebase


class MobileNotificationSettings(Document):
	def validate(self):
		for fieldname in ("shift_start_reminder_minutes", "shift_end_reminder_minutes", "missing_checkin_grace_minutes"):
			value = int(self.get(fieldname) or 0)
			if value < 0 or value > 1440:
				frappe.throw(_("Shift reminder minutes must be between 0 and 1440"))

	@frappe.whitelist()
	def upload_firebase_credentials(self, credentials_json: str):
		frappe.only_for("System Manager")
		credentials = _validate_service_account(credentials_json)
		self.firebase_credentials_json = json.dumps(credentials, separators=(",", ":"))
		self.firebase_project_id = credentials["project_id"]
		self.firebase_service_account = credentials["client_email"]
		self.firebase_enabled = 1
		self.save(ignore_permissions=True)
		firebase.reset_app()
		return {
			"configured": True,
			"project_id": self.firebase_project_id,
			"client_email": self.firebase_service_account,
		}

	@frappe.whitelist()
	def clear_firebase_credentials(self):
		frappe.only_for("System Manager")
		self.firebase_credentials_json = ""
		self.firebase_project_id = ""
		self.firebase_service_account = ""
		self.firebase_enabled = 0
		self.save(ignore_permissions=True)
		firebase.reset_app()
		return {"configured": False}

	@frappe.whitelist()
	def test_firebase_connection(self):
		frappe.only_for("System Manager")
		result = firebase.test_connection()
		return {"ok": True, **result}


def _validate_service_account(raw: str) -> dict:
	if not raw or len(raw.encode("utf-8")) > 32_768:
		frappe.throw(_("Select a valid Firebase service-account JSON file smaller than 32 KB"))
	try:
		credentials = json.loads(raw)
	except (TypeError, ValueError):
		frappe.throw(_("The selected file is not valid JSON"))
	required = ("type", "project_id", "private_key_id", "private_key", "client_email", "token_uri")
	if not isinstance(credentials, dict) or credentials.get("type") != "service_account":
		frappe.throw(_("The selected JSON is not a service-account credential"))
	if any(not credentials.get(key) for key in required):
		frappe.throw(_("The service-account credential is missing required fields"))
	if not str(credentials["token_uri"]).startswith("https://oauth2.googleapis.com/"):
		frappe.throw(_("The service-account token URI is not allowed"))
	return credentials
