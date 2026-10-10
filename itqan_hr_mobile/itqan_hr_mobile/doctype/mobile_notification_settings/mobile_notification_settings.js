frappe.ui.form.on("Mobile Notification Settings", {
	refresh(frm) {
		if (!frappe.user.has_role("System Manager")) return;

		frm.add_custom_button(__("Upload Service Account JSON"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("Configure Firebase"),
				fields: [
					{
						fieldname: "security_notice",
						fieldtype: "HTML",
						options: `<p class="text-muted">${__(
							"The credential will be validated and encrypted using this site's encryption key. It will not be attached as a File."
						)}</p>`,
					},
					{
						fieldname: "credentials_file",
						fieldtype: "HTML",
						options: '<input class="form-control firebase-credentials-file" type="file" accept="application/json,.json">',
					},
				],
				primary_action_label: __("Encrypt and Save"),
				primary_action: async () => {
					const input = dialog.$wrapper.find(".firebase-credentials-file")[0];
					const file = input && input.files && input.files[0];
					if (!file) {
						frappe.msgprint(__("Select a Firebase service-account JSON file."));
						return;
					}
					if (file.size > 32768) {
						frappe.msgprint(__("The credential file must be smaller than 32 KB."));
						return;
					}
					const credentials_json = await file.text();
					dialog.get_primary_btn().prop("disabled", true);
					try {
						await frm.call("upload_firebase_credentials", { credentials_json });
						dialog.hide();
						await frm.reload_doc();
						frappe.show_alert({ message: __("Firebase credentials saved securely"), indicator: "green" });
					} finally {
						dialog.get_primary_btn().prop("disabled", false);
					}
				},
			});
			dialog.show();
		}, __("Firebase"));

		if (frm.doc.firebase_project_id) {
			frm.add_custom_button(
				__("Test Connection"),
				() => frm.call("test_firebase_connection").then(() =>
					frappe.show_alert({ message: __("Firebase authentication succeeded"), indicator: "green" })
				),
				__("Firebase")
			);
			frm.add_custom_button(
				__("Remove Credentials"),
				() => frappe.confirm(
					__("Remove the encrypted Firebase credentials from this site?"),
					() => frm.call("clear_firebase_credentials").then(() => frm.reload_doc())
				),
				__("Firebase")
			);
		}
	},
});
