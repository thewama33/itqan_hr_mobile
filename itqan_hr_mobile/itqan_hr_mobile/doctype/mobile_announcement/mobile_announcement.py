import frappe
from frappe.model.document import Document


class MobileAnnouncement(Document):
	def validate(self):
		if self.publish_to and self.publish_from and self.publish_to < self.publish_from:
			frappe.throw("Publish To cannot be before Publish From")

		if self.audience_type == "Selected Employees" and not self.specific_employees:
			frappe.throw("Select at least one employee")
