from __future__ import annotations

import json
import os
from pathlib import Path

import frappe

logger = frappe.logger("itqan_hr_mobile")
_app = None


class FirebaseNotConfigured(RuntimeError):
	pass


def _config() -> dict:
	stored = _stored_credentials()
	configured = frappe.conf.get("itqan_hr_mobile") or {}
	if isinstance(configured, str):
		try:
			configured = json.loads(configured)
		except ValueError:
			configured = {}
	return {
		"project_id": (stored or {}).get("project_id") or os.getenv("ITQAN_FIREBASE_PROJECT_ID") or configured.get("firebase_project_id"),
		"credentials_path": os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or configured.get("firebase_credentials_path"),
		"credentials": stored,
	}


def _stored_credentials() -> dict | None:
	try:
		if not frappe.db.exists("DocType", "Mobile Notification Settings"):
			return None
		doc = frappe.get_single("Mobile Notification Settings")
		raw = doc.get_password("firebase_credentials_json", raise_exception=False)
		credentials = json.loads(raw) if raw else None
		return credentials if isinstance(credentials, dict) and credentials.get("type") == "service_account" else None
	except Exception:
		return None


def get_app():
	global _app
	if _app:
		return _app
	try:
		import firebase_admin
		from firebase_admin import credentials
	except ImportError as exc:
		raise FirebaseNotConfigured("firebase-admin is not installed") from exc
	config = _config()
	options = {"projectId": config["project_id"]} if config["project_id"] else None
	path = config["credentials_path"]
	if config["credentials"]:
		credential = credentials.Certificate(config["credentials"])
	elif path:
		path = str(Path(path).expanduser())
		if not Path(path).is_file():
			raise FirebaseNotConfigured("Firebase credentials file does not exist")
		credential = credentials.Certificate(path)
	else:
		credential = credentials.ApplicationDefault()
	try:
		_app = firebase_admin.get_app("itqan_hr_mobile")
	except ValueError:
		_app = firebase_admin.initialize_app(credential, options, name="itqan_hr_mobile")
	return _app


def reset_app() -> None:
	global _app
	if not _app:
		return
	try:
		import firebase_admin

		firebase_admin.delete_app(_app)
	except (ImportError, ValueError):
		pass
	finally:
		_app = None


def test_connection() -> dict:
	try:
		from google.auth.transport.requests import Request
	except ImportError as exc:
		raise FirebaseNotConfigured("Google authentication dependencies are not installed") from exc
	app = get_app()
	google_credential = app.credential.get_credential()
	if getattr(google_credential, "requires_scopes", False):
		google_credential = google_credential.with_scopes(["https://www.googleapis.com/auth/firebase.messaging"])
	google_credential.refresh(Request())
	config = _config()
	return {"project_id": config["project_id"], "credential_type": "service_account" if config["credentials"] else "external"}


def send_to_token(token: str, title: str, body: str, data: dict) -> str:
	from firebase_admin import messaging

	message = messaging.Message(
		notification=messaging.Notification(title=title, body=body),
		data={str(key): str(value or "") for key, value in data.items()},
		token=token,
	)
	return messaging.send(message, app=get_app())


def is_invalid_token_error(exc: Exception) -> bool:
	name = exc.__class__.__name__
	return name in {"UnregisteredError", "InvalidArgumentError", "SenderIdMismatchError"} or any(
		marker in str(exc).lower() for marker in ("not a valid fcm", "registration-token-not-registered", "unregistered")
	)


def sanitized_error(exc: Exception, limit: int = 500) -> str:
	message = str(exc).replace("\n", " ")
	config = _config()
	if config.get("credentials_path"):
		message = message.replace(config["credentials_path"], "[credentials path]")
	return message[:limit]
