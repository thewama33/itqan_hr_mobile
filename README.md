# Itqan HR Mobile Notifications

A reusable Frappe v15+ backend for employee mobile push notifications. It provides multi-device registration, private in-app history, asynchronous Firebase Cloud Messaging (FCM), English/Arabic templates, explicit HR event adapters, announcements, and configurable document-expiry reminders. It modifies no Frappe, ERPNext, or HRMS core files.

## Architecture

```text
HR document event -> guarded event adapter -> employee/user resolver
                  -> Mobile Notification (idempotent event_key)
                  -> enqueue_after_commit -> Firebase service -> enabled devices
```

Event adapters contain no Firebase code. A failed adapter is logged and cannot abort the HR operation; network delivery only starts after the database transaction commits. One history record is stored per recipient, while every enabled device for that user receives the push.

## Supported versions and events

- Frappe Framework 15+, ERPNext 15+, and Frappe HR/HRMS 15+.
- Leave Application: approved, rejected, cancelled, and approver-required.
- Attendance Request: submitted/approved and workflow approved/rejected when corresponding fields exist.
- Employee Advance: submitted/approved, workflow rejected, and paid.
- Salary Slip: first submitted state; no salary values are included.
- Shift Assignment: assigned and meaningful shift/date/status changes.
- Optional shift start/end reminders, evaluated every five minutes with independent enable switches and lead times.
- Mobile Announcement: all active employees or company/department/branch/designation/selected employees.
- Configurable document expiry rules, disabled by default.

Optional upstream DocTypes are referenced only by string hooks and runtime metadata checks. Missing HRMS features therefore do not create import-time dependencies.

## Installation

```bash
cd /path/to/frappe-bench
bench get-app https://your.git/itqan_hr_mobile.git
bench --site your-site install-app itqan_hr_mobile
bench --site your-site migrate
bench build --app itqan_hr_mobile
bench restart
```

The package declares `firebase-admin>=6.2,<8` in `pyproject.toml`. For an existing checkout, run `bench setup requirements`, migrate, and restart web, scheduler, and worker processes.

### Docker

Build the app and dependency into the image; do not install them interactively in a running production container. Add the app to `apps.json` or the image build, rebuild the image, inject credentials as a secret, then run commands equivalent to:

```bash
docker compose exec backend bench --site your-site install-app itqan_hr_mobile
docker compose exec backend bench --site your-site migrate
docker compose exec frontend bench build --app itqan_hr_mobile
docker compose restart backend websocket queue-short queue-long scheduler frontend
```

Service names vary by deployment.

## Firebase setup

Create a Firebase service account with minimum messaging access. Never commit its JSON file or ship it to Flutter. Configure either this in `site_config.json`:

### Desk setup (recommended for individual sites)

1. Open **Mobile Notification Settings** as a System Manager.
2. Choose **Firebase → Upload Service Account JSON**.
3. Select the JSON downloaded from Firebase Console and click **Encrypt and Save**.
4. Use **Firebase → Test Connection** to authenticate with Google.

The browser reads the selected file locally and sends it to the protected setup method. The server validates the credential, encrypts it using the site's encryption key, and stores it in Frappe's `__Auth` password store. It is not saved as a File, committed to the app, returned through APIs, or displayed again. The visible settings show only project ID and service-account email. Environment variables and `site_config.json` remain supported as deployment-oriented fallbacks.

To rotate a key, upload the new JSON; it replaces the encrypted value. Use **Remove Credentials** to delete the encrypted value and disable Firebase for the site.

### Deployment configuration

Alternatively, configure this in `site_config.json`:

```json
{
  "itqan_hr_mobile": {
    "firebase_project_id": "my-project",
    "firebase_credentials_path": "/run/secrets/firebase-service-account.json"
  }
}
```

or environment variables:

```bash
export ITQAN_FIREBASE_PROJECT_ID=my-project
export GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/firebase-service-account.json
```

Restart web and workers after changes. Application Default Credentials are used when no path is supplied. Credentials and tokens are never returned by APIs or logged. Open **Mobile Notification Settings** to manage feature flags. Standard Frappe Notification Log creation is independent and opt-in.

## Flutter API flows

All calls require session or API-token authentication. The backend always uses `frappe.session.user`; no user argument is accepted.

Register or upsert a device:

```bash
curl -X POST https://erp.example.com/api/method/itqan_hr_mobile.api.device.register_device \
  -H 'Authorization: token API_KEY:API_SECRET' -H 'Content-Type: application/json' \
  -d '{"device_id":"installation-uuid","fcm_token":"FCM_TOKEN","platform":"Android","device_name":"Pixel","app_version":"2.0.0","os_version":"16"}'
```

On FCM token refresh:

```bash
curl -X POST https://erp.example.com/api/method/itqan_hr_mobile.api.device.update_device_token \
  -H 'Authorization: token API_KEY:API_SECRET' -H 'Content-Type: application/json' \
  -d '{"device_id":"installation-uuid","fcm_token":"NEW_TOKEN"}'
```

Call `heartbeat(device_id, app_version, os_version)` periodically. On logout call `unregister_device(device_id)`; the record is retained but disabled. `list_my_devices` omits FCM tokens.

Notification endpoints:

- `GET ...api.notifications.get_notifications?limit=20&offset=0&unread_only=0`
- `POST ...api.notifications.mark_as_read` with `notification_name`
- `POST ...api.notifications.mark_all_as_read`
- `GET ...api.notifications.get_unread_count`
- `POST ...api.notifications.delete_my_notification` with `notification_name`

Every operation applies a server-side ownership condition. Desk query and permission hooks add another boundary.

## FCM payload

FCM receives display and string-only data payloads:

```json
{
  "notification": {"title": "Leave Request Rejected", "body": "Your leave request ... has been rejected."},
  "data": {
    "type": "leave_rejected",
    "reference_doctype": "Leave Application",
    "reference_name": "HR-LAP-00015",
    "route": "leave_details",
    "route_params": "{\"name\":\"HR-LAP-00015\"}",
    "notification_name": "..."
  }
}
```

Routes are stable logical identifiers; Flutter owns navigation. Push bodies intentionally exclude payroll values and confidential details.

## Announcements and expiry rules

Submit a **Mobile Announcement** to enqueue fan-out on the long queue. `publish_from` can defer it; an hourly job publishes due records. Audience filters operate on active employees with enabled linked users.

Expiry mappings live in **Mobile Notification Settings**. Each row declares a DocType, Date field, Employee field, thresholds such as `30,14,7,1`, templates, and an optional route. Runtime metadata validates mappings. The daily job queries exact threshold dates, caps each query, and uses event keys to prevent repeats. Placeholders include `{expiry_date}`, `{days}`, and `{name}`.

Core messages use `User.language`, then the configured default, then English. Arabic UTF-8 text is included.

### Shift reminders

In **Mobile Notification Settings → Shift Reminders**, enable start and/or end reminders and choose a lead time from 0 to 1440 minutes. You can also enable **Remind When Employee Has Not Checked In** and configure a grace period after shift start. The five-minute scheduler reads submitted active Shift Assignments and Shift Type times, supports overnight shifts and early check-in windows, and creates one deduplicated notification per assignment/date/rule. All reminders are disabled by default.

## Adding an event

Add a small module under `itqan_hr_mobile/events`, register a targeted `doc_events` hook, resolve through `recipient_resolver`, and call `notification_service.notify`. Include a transition-specific event key, logical route, and non-sensitive context. Keep optional schema decisions in `services/compatibility.py` and localized text in `services/templates.py`.

## Operations and troubleshooting

History states are `Pending`, `Queued`, `Sent`, `Failed`, or `Skipped`. Invalid/unregistered FCM responses disable the device. Retry a failed record server-side:

```python
from itqan_hr_mobile.services.notification_service import retry_failed
retry_failed("mobile-notification-name")
```

Check worker availability, Firebase IAM/project configuration, the secret path inside the worker, and `itqan_hr_mobile` logs. `Skipped` normally means Firebase was disabled or no enabled device existed. Set **Disable Devices Inactive For (Days)** to a positive number to enable daily stale-device maintenance; zero disables it.

## Security

- Guest registration is rejected; arbitrary users cannot be supplied.
- Tokens are hidden in Desk metadata and omitted from client APIs.
- History APIs enforce ownership independently of DocType permissions.
- Only System Manager can administer all devices/history; HR roles do not receive blanket history access.
- ORM and validated metadata are used; secrets are sanitized from errors.
- Delivery happens after commit and cannot roll back HR transactions.

## Testing and upgrades

```bash
bench --site your-test-site run-tests --app itqan_hr_mobile
```

Tests mock Firebase and never contact the network. Before upgrading, back up, update the app and image/dependency lock, migrate, rebuild, restart workers, and run tests on staging. Review bespoke workflow state names after major HRMS customizations.

## License

MIT
