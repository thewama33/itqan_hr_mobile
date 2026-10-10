from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

from itqan_hr_mobile.events import leave, salary
from itqan_hr_mobile.services import firebase, notification_service
from itqan_hr_mobile.services.shift_reminders import _as_time, _has_checkin
from itqan_hr_mobile.itqan_hr_mobile.doctype.mobile_notification_settings.mobile_notification_settings import (
	_validate_service_account,
)


class FakeDoc(dict):
	doctype = "Leave Application"
	name = "HR-LAP-TEST"
	docstatus = 0

	def __getattr__(self, key):
		return self.get(key)

	def get_doc_before_save(self):
		return self.pop("_before", None)


class TestEventDeduplication(FrappeTestCase):
	@patch("itqan_hr_mobile.events.leave.setting_enabled", return_value=True)
	@patch("itqan_hr_mobile.events.leave.employee_notification")
	def test_leave_open_to_approved_once(self, notify, _enabled):
		doc = FakeDoc(status="Approved", employee="EMP", from_date="2026-01-01", to_date="2026-01-02", _before={"status": "Open"})
		leave.on_change(doc)
		notify.assert_called_once()

	@patch("itqan_hr_mobile.events.leave.setting_enabled", return_value=True)
	@patch("itqan_hr_mobile.events.leave.employee_notification")
	def test_leave_open_to_rejected_once(self, notify, _enabled):
		doc = FakeDoc(status="Rejected", employee="EMP", _before={"status": "Open"})
		leave.on_change(doc)
		notify.assert_called_once()

	@patch("itqan_hr_mobile.events.leave.setting_enabled", return_value=True)
	@patch("itqan_hr_mobile.events.leave.employee_notification")
	def test_unchanged_rejected_does_not_notify(self, notify, _enabled):
		doc = FakeDoc(status="Rejected", employee="EMP", _before={"status": "Rejected"})
		leave.on_change(doc)
		notify.assert_not_called()

	@patch("itqan_hr_mobile.events.salary.setting_enabled", return_value=True)
	@patch("itqan_hr_mobile.events.salary.employee_notification")
	def test_salary_submit_once(self, notify, _enabled):
		doc = FakeDoc(employee="EMP", end_date="2026-10-31")
		doc.doctype, doc.name = "Salary Slip", "SAL-TEST"
		salary.on_submit(doc)
		notify.assert_called_once()


class TestDelivery(FrappeTestCase):
	def test_shift_time_from_timedelta(self):
		from datetime import timedelta

		self.assertEqual(str(_as_time(timedelta(hours=21, minutes=30))), "21:30:00")

	@patch("itqan_hr_mobile.services.shift_reminders.field_exists", return_value=True)
	@patch("itqan_hr_mobile.services.shift_reminders.doctype_exists", return_value=True)
	@patch("itqan_hr_mobile.services.shift_reminders.frappe")
	def test_missing_checkin_detects_in_log(self, frappe_mock, _doctype, _field):
		from datetime import datetime

		frappe_mock.get_all.return_value = [{"name": "CHECKIN-1", "log_type": "IN"}]
		self.assertTrue(_has_checkin("EMP", datetime(2026, 10, 11, 9), datetime(2026, 10, 11, 9, 5), 30))

	@patch("itqan_hr_mobile.services.shift_reminders.field_exists", return_value=True)
	@patch("itqan_hr_mobile.services.shift_reminders.doctype_exists", return_value=True)
	@patch("itqan_hr_mobile.services.shift_reminders.frappe")
	def test_missing_checkin_when_no_logs(self, frappe_mock, _doctype, _field):
		from datetime import datetime

		frappe_mock.get_all.return_value = []
		self.assertFalse(_has_checkin("EMP", datetime(2026, 10, 11, 9), datetime(2026, 10, 11, 9, 5), 30))
	def test_rejects_non_service_account_credentials(self):
		with patch("itqan_hr_mobile.itqan_hr_mobile.doctype.mobile_notification_settings.mobile_notification_settings.frappe.throw", side_effect=ValueError):
			with self.assertRaises(ValueError):
				_validate_service_account('{"type":"authorized_user"}')

	@patch("itqan_hr_mobile.services.firebase.frappe")
	def test_encrypted_settings_credentials_are_loaded(self, frappe_mock):
		frappe_mock.db.exists.return_value = True
		frappe_mock.get_single.return_value.get_password.return_value = '{"type":"service_account","project_id":"project"}'
		self.assertEqual(firebase._stored_credentials()["project_id"], "project")

	@patch("itqan_hr_mobile.services.recipient_resolver.frappe")
	def test_employee_without_user_is_safe(self, frappe_mock):
		from itqan_hr_mobile.services.recipient_resolver import user_for_employee
		with patch("itqan_hr_mobile.services.recipient_resolver.get_employee_user", return_value=None):
			self.assertIsNone(user_for_employee("EMP-MISSING"))

	@patch("itqan_hr_mobile.services.notification_service.frappe")
	@patch("itqan_hr_mobile.services.notification_service.enabled_devices", return_value=[])
	def test_user_without_device_is_skipped(self, _devices, frappe_mock):
		frappe_mock.get_doc.return_value = SimpleNamespace(name="N1", user="u@example.com", push_status="Queued", notification_type="x", reference_doctype=None, reference_name=None, route=None, route_params_json="{}")
		notification_service.deliver_notification("N1")
		self.assertTrue(frappe_mock.db.set_value.called)

	@patch("itqan_hr_mobile.services.notification_service.firebase.send_to_token", return_value="message-id")
	@patch("itqan_hr_mobile.services.notification_service.setting_enabled", return_value=True)
	@patch("itqan_hr_mobile.services.notification_service.enabled_devices")
	@patch("itqan_hr_mobile.services.notification_service.frappe")
	def test_multiple_enabled_devices_receive(self, frappe_mock, devices, _enabled, send):
		devices.return_value = [SimpleNamespace(name="D1", fcm_token="one"), SimpleNamespace(name="D2", fcm_token="two")]
		frappe_mock.get_doc.return_value = SimpleNamespace(name="N1", user="u", push_status="Queued", notification_type="x", title="t", body="b", reference_doctype=None, reference_name=None, route=None, route_params_json="{}")
		notification_service.deliver_notification("N1")
		self.assertEqual(send.call_count, 2)

	def test_disabled_devices_are_filtered_by_resolver(self):
		with patch("itqan_hr_mobile.services.recipient_resolver.frappe") as frappe_mock:
			from itqan_hr_mobile.services.recipient_resolver import enabled_devices
			enabled_devices("u")
			self.assertEqual(frappe_mock.get_all.call_args.kwargs["filters"]["enabled"], 1)

	def test_invalid_token_detection(self):
		class UnregisteredError(Exception):
			pass
		self.assertTrue(firebase.is_invalid_token_error(UnregisteredError("gone")))

	@patch("itqan_hr_mobile.api.device.frappe")
	def test_guest_device_registration_is_rejected(self, frappe_mock):
		from itqan_hr_mobile.api import device
		frappe_mock.session.user = "Guest"
		frappe_mock.throw.side_effect = PermissionError
		with self.assertRaises(PermissionError):
			device.register_device("device", "token")

	@patch("itqan_hr_mobile.api.notifications.frappe")
	def test_notification_ownership_filter(self, frappe_mock):
		from itqan_hr_mobile.api.notifications import get_notifications
		frappe_mock.session.user = "employee@example.com"
		frappe_mock.get_all.return_value = []
		get_notifications()
		self.assertEqual(frappe_mock.get_all.call_args.kwargs["filters"]["user"], "employee@example.com")

	@patch("itqan_hr_mobile.services.notification_service.frappe")
	def test_fcm_is_enqueued_after_commit(self, frappe_mock):
		frappe_mock.db.exists.return_value = None
		frappe_mock.db.get_value.return_value = 1
		doc = MagicMock(name="notification")
		doc.name = "N1"
		frappe_mock.get_doc.return_value = doc
		with patch("itqan_hr_mobile.services.notification_service.render", return_value=("t", "b")):
			notification_service.notify(user="u", employee=None, notification_type="x")
		self.assertTrue(frappe_mock.enqueue.call_args.kwargs["enqueue_after_commit"])
