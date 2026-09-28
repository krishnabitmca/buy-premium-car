from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

MAX_BODY_BYTES = 64 * 1024
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
WATCH_STATUSES = {"active", "paused", "archived"}


def _json_response(handler, status, payload):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _supabase_config():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("Supabase persistence is not configured")
    return url, key


def _supabase_request(method, path, payload=None, prefer=None):
    base, key = _supabase_config()
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    req = Request(base + "/rest/v1/" + path, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=15) as res:
            raw = res.read().decode("utf-8")
            return json.loads(raw) if raw else []
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"Supabase error {exc.code}: {detail[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Supabase connection error: {exc.reason}") from exc


def _phone_e164(value):
    s = (value or "").strip().replace(" ", "").replace("-", "")
    if not s:
        return None
    if s.startswith("0") and len(s) == 11:
        s = s[1:]
    if s.isdigit() and len(s) == 10:
        s = "+91" + s
    if not re.fullmatch(r"\+[1-9]\d{7,14}", s):
        raise ValueError("Enter a valid phone number, preferably in international format")
    return s


def _number(value, name, minimum=0, maximum=None):
    if value in (None, ""):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number")
    if x < minimum or (maximum is not None and x > maximum):
        raise ValueError(f"{name} is outside the supported range")
    return x


def _token_hash(token):
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def _new_access_token():
    return secrets.token_urlsafe(32)


def _auth_token(handler):
    header = (handler.headers.get("Authorization") or "").strip()
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
        if token:
            return token
    query = parse_qs(urlparse(handler.path).query)
    token = (query.get("token") or [None])[0]
    return token.strip() if isinstance(token, str) and token.strip() else None


def _find_user_by_token(token):
    if not token:
        return None
    rows = _supabase_request(
        "GET",
        "deal_watch_users"
        f"?access_token_hash=eq.{_token_hash(token)}"
        "&select=user_id,email,phone_e164,status",
    )
    return rows[0] if rows else None


def _find_user_by_email(email):
    rows = _supabase_request(
        "GET",
        f"deal_watch_users?email=eq.{email.replace('\\', '\\\\').replace(',', '%2C')}"
        "&select=user_id,email,phone_e164,status,access_token_hash",
    )
    return rows[0] if rows else None


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0 or length > MAX_BODY_BYTES:
        raise ValueError("Request body is missing or too large")
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def _require_user(handler):
    token = _auth_token(handler)
    if not token:
        raise PermissionError("Private watch access is required")
    user = _find_user_by_token(token)
    if not user:
        raise PermissionError("Invalid or expired watch access")
    if user.get("status") == "unsubscribed":
        raise PermissionError("Watch access is unsubscribed")
    return user


def _list_watches(user_id):
    watches = _supabase_request(
        "GET",
        "deal_watches"
        f"?user_id=eq.{user_id}"
        "&select=watch_id,name,category,natural_language_request,constraints,target_discount_pct,"
        "alert_quality,frequency,status,created_at,updated_at"
        "&order=created_at.desc",
    )
    channels = _supabase_request(
        "GET",
        f"channel_preferences?user_id=eq.{user_id}&select=channel,enabled,frequency",
    )
    events = _supabase_request(
        "GET",
        f"alert_events?user_id=eq.{user_id}"
        "&select=watch_id,listing_id,channel,status,created_at,sent_at"
        "&order=created_at.desc&limit=500",
    )
    by_watch = {}
    for event in events:
        bucket = by_watch.setdefault(event.get("watch_id"), [])
        bucket.append(event)
    for watch in watches:
        watch_id = watch.get("watch_id")
        bucket = by_watch.get(watch_id, [])
        sent = [e for e in bucket if e.get("status") == "sent"]
        watch["alerts_sent"] = len(sent)
        watch["last_alert_at"] = (sent[0].get("sent_at") or sent[0].get("created_at")) if sent else None
    return {"watches": watches, "channels": channels}


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.end_headers()

    def do_GET(self):
        try:
            token = _auth_token(self)
            if not token:
                _supabase_config()
                _json_response(self, 200, {"ok": True, "persistence": "configured"})
                return
            user = _require_user(self)
            data = _list_watches(user["user_id"])
            _json_response(self, 200, {"ok": True, "email": user["email"], **data})
        except PermissionError as exc:
            _json_response(self, 401, {"ok": False, "error": str(exc)})
        except Exception:
            _json_response(self, 200, {"ok": True, "persistence": "not-configured"})

    def do_POST(self):
        access_token = None
        try:
            data = _read_json(self)
            access_token = str(data.get("access_token") or "").strip() or None
            existing_user = _find_user_by_token(access_token) if access_token else None
            email = str(data.get("email", "")).strip().lower()
            if not EMAIL_RE.fullmatch(email):
                raise ValueError("Enter a valid email address")
            if existing_user and existing_user["email"] != email:
                raise PermissionError("The email does not match the private watch access")

            existing_by_email = _find_user_by_email(email)
            if existing_user:
                user_id = existing_user["user_id"]
                minted_token = None
                phone_existing = existing_user.get("phone_e164")
            elif existing_by_email:
                user_id = existing_by_email["user_id"]
                phone_existing = existing_by_email.get("phone_e164")
                minted_token = None
                if not existing_by_email.get("access_token_hash"):
                    access_token = _new_access_token()
                    minted_token = access_token
                    _supabase_request(
                        "PATCH",
                        f"deal_watch_users?user_id=eq.{user_id}",
                        {"access_token_hash": _token_hash(access_token)},
                        "return=minimal",
                    )
            else:
                access_token = _new_access_token()
                minted_token = access_token
                created = _supabase_request(
                    "POST",
                    "deal_watch_users",
                    {
                        "email": email,
                        "access_token_hash": _token_hash(access_token),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                    "return=representation",
                )
                if not created:
                    raise RuntimeError("User record could not be created")
                user_id = created[0]["user_id"]
                phone_existing = None

            name = str(data.get("name", "")).strip()
            if not name or len(name) > 100:
                raise ValueError("Watch name is required")
            channels = data.get("channels") or ["email"]
            if not isinstance(channels, list):
                raise ValueError("Invalid notification channels")
            channels = {str(c).lower() for c in channels}
            if not channels.issubset({"email", "whatsapp"}) or not channels:
                raise ValueError("Choose at least one notification channel")
            email_consent = bool(data.get("email_consent"))
            whatsapp_consent = bool(data.get("whatsapp_consent"))
            if "email" in channels and not email_consent:
                raise ValueError("Email alerts require explicit consent")
            if "whatsapp" in channels and not whatsapp_consent:
                raise ValueError("WhatsApp alerts require explicit consent")
            phone = _phone_e164(data.get("phone")) if data.get("phone") else phone_existing
            if "whatsapp" in channels and not phone:
                raise ValueError("WhatsApp alerts require a phone number")

            intent = data.get("intent") or {}
            budget_min = _number(intent.get("budget_min"), "Minimum budget", 0, 1000)
            budget_max = _number(intent.get("budget_max"), "Maximum budget", 0, 1000)
            age_min = _number(intent.get("min_age_years"), "Minimum vehicle age", 0, 100)
            age_max = _number(intent.get("max_age_years"), "Maximum vehicle age", 0, 100)
            if budget_min is not None and budget_max is not None and budget_min > budget_max:
                raise ValueError("Minimum budget cannot exceed maximum budget")
            if age_min is not None and age_max is not None and age_min > age_max:
                raise ValueError("Minimum vehicle age cannot exceed maximum age")
            _supabase_request(
                "PATCH",
                f"deal_watch_users?user_id=eq.{user_id}",
                {"phone_e164": phone, "updated_at": datetime.now(timezone.utc).isoformat()},
                "return=minimal",
            )

            watch_id = str(uuid.uuid4())
            constraints = {
                "budget_min_lakh": budget_min,
                "budget_max_lakh": budget_max,
                "min_age_years": age_min,
                "max_age_years": age_max,
                "make": intent.get("make"),
                "model": intent.get("model"),
                "condition": intent.get("condition"),
                "mileage_max_km": intent.get("max_mileage_km"),
                "max_owners": intent.get("max_owners"),
                "fuel": intent.get("fuel"),
                "transmission": intent.get("transmission"),
                "location": intent.get("location"),
                "radius_km": intent.get("radius_km"),
                "must_have": intent.get("must_have_text"),
                "nice_to_have": intent.get("nice_to_have_text"),
                "avoid": intent.get("avoid_text"),
            }
            _supabase_request(
                "POST",
                "deal_watches",
                {
                    "watch_id": watch_id,
                    "user_id": user_id,
                    "name": name,
                    "category": "automotive",
                    "natural_language_request": intent.get("query") or None,
                    "constraints": constraints,
                    "target_discount_pct": intent.get("target_discount_pct"),
                    "alert_quality": intent.get("alert_quality", "any"),
                    "frequency": intent.get("notification_frequency", "instant"),
                },
                "return=minimal",
            )
            now = datetime.now(timezone.utc).isoformat()
            for channel in ("email", "whatsapp"):
                if channel in channels:
                    _supabase_request(
                        "POST",
                        "channel_preferences?on_conflict=user_id,channel",
                        {
                            "user_id": user_id,
                            "channel": channel,
                            "enabled": True,
                            "frequency": intent.get("notification_frequency", "instant"),
                            "consent_at": now,
                            "consent_source": "car-watch-form",
                        },
                        "resolution=merge-duplicates",
                    )
            response = {"ok": True, "watch_id": watch_id, "message": "Car Watch saved"}
            if minted_token:
                response["access_token"] = minted_token
                response["manage_link"] = f"/#watch={minted_token}"
            _json_response(self, 201, response)
        except PermissionError as exc:
            _json_response(self, 401, {"ok": False, "error": str(exc)})
        except ValueError as exc:
            _json_response(self, 400, {"ok": False, "error": str(exc)})
        except RuntimeError as exc:
            _json_response(self, 503, {"ok": False, "error": str(exc)})
        except Exception:
            _json_response(self, 500, {"ok": False, "error": "Unable to save the Car Watch"})

    def _watch_mutation(self):
        user = _require_user(self)
        data = _read_json(self)
        watch_id = str(data.get("watch_id") or "").strip()
        if not watch_id:
            raise ValueError("Watch ID is required")
        if data.get("status") is not None:
            status = str(data["status"]).lower()
            if status not in WATCH_STATUSES:
                raise ValueError("Invalid watch status")
            if status == "archived":
                method = "PATCH"
                payload = {"status": "archived", "updated_at": datetime.now(timezone.utc).isoformat()}
            else:
                method = "PATCH"
                payload = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
            _supabase_request(
                method,
                f"deal_watches?watch_id=eq.{watch_id}&user_id=eq.{user['user_id']}",
                payload,
                "return=minimal",
            )
            return status
        raise ValueError("No watch change was requested")

    def do_PATCH(self):
        try:
            status = self._watch_mutation()
            _json_response(self, 200, {"ok": True, "status": status})
        except PermissionError as exc:
            _json_response(self, 401, {"ok": False, "error": str(exc)})
        except ValueError as exc:
            _json_response(self, 400, {"ok": False, "error": str(exc)})
        except RuntimeError as exc:
            _json_response(self, 503, {"ok": False, "error": str(exc)})
        except Exception:
            _json_response(self, 500, {"ok": False, "error": "Unable to update the Car Watch"})

    def do_DELETE(self):
        try:
            user = _require_user(self)
            query = parse_qs(urlparse(self.path).query)
            watch_id = (query.get("watch_id") or [""])[0].strip()
            if not watch_id:
                raise ValueError("Watch ID is required")
            _supabase_request(
                "PATCH",
                f"deal_watches?watch_id=eq.{watch_id}&user_id=eq.{user['user_id']}",
                {"status": "archived", "updated_at": datetime.now(timezone.utc).isoformat()},
                "return=minimal",
            )
            _json_response(self, 200, {"ok": True, "status": "archived"})
        except PermissionError as exc:
            _json_response(self, 401, {"ok": False, "error": str(exc)})
        except ValueError as exc:
            _json_response(self, 400, {"ok": False, "error": str(exc)})
        except RuntimeError as exc:
            _json_response(self, 503, {"ok": False, "error": str(exc)})
        except Exception:
            _json_response(self, 500, {"ok": False, "error": "Unable to archive the Car Watch"})

    def log_message(self, *_args):
        return
