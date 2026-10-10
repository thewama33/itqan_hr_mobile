import frappe
from frappe.model.document import Document


class MobileDevice(Document):
	def validate(self):
		self.platform = self.platform if self.platform in ("Android", "iOS", "Other") else "Other"
		duplicate = frappe.db.exists(
			"Mobile Device", {"user": self.user, "device_id": self.device_id, "name": ("!=", self.name)}
		)
		if duplicate:
			frappe.throw("A device with this ID is already registered for this user")
