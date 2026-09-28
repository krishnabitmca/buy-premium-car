from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_BODY_BYTES = 64 * 1024
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _json_response(handler, status, payload):
    body=json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type","application/json; charset=utf-8")
    handler.send_header("Cache-Control","no-store")
    handler.send_header("Content-Length",str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def _supabase_config():
    url=os.getenv("SUPABASE_URL","").rstrip("/")
    key=os.getenv("SUPABASE_SERVICE_ROLE_KEY","")
    if not url or not key:
        raise RuntimeError("Supabase persistence is not configured")
    return url,key

def _supabase_request(method,path,payload=None,prefer=None):
    base,key=_supabase_config()
    body=None if payload is None else json.dumps(payload).encode("utf-8")
    headers={"apikey":key,"Authorization":f"Bearer {key}","Content-Type":"application/json"}
    if prefer: headers["Prefer"]=prefer
    req=Request(base+"/rest/v1/"+path,data=body,headers=headers,method=method)
    try:
        with urlopen(req,timeout=15) as res:
            raw=res.read().decode("utf-8")
            return json.loads(raw) if raw else []
    except HTTPError as exc:
        detail=exc.read().decode("utf-8","replace")
        raise RuntimeError(f"Supabase error {exc.code}: {detail[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Supabase connection error: {exc.reason}") from exc

def _phone_e164(value):
    s=(value or "").strip().replace(" ","").replace("-","")
    if not s:return None
    if s.startswith("0") and len(s)==11:s=s[1:]
    if s.isdigit() and len(s)==10:s="+91"+s
    if not re.fullmatch(r"\+[1-9]\d{7,14}",s):
        raise ValueError("Enter a valid phone number, preferably in international format")
    return s

def _number(value,name,minimum=0,maximum=None):
    if value in (None,""):return None
    try:x=float(value)
    except (TypeError,ValueError):raise ValueError(f"{name} must be a number")
    if x<minimum or (maximum is not None and x>maximum):raise ValueError(f"{name} is outside the supported range")
    return x

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.send_header("Access-Control-Allow-Methods","POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        try:
            _supabase_config()
            _json_response(self,200,{"ok":True,"persistence":"configured"})
        except Exception:
            _json_response(self,200,{"ok":True,"persistence":"not-configured"})

    def do_POST(self):
        try:
            length=int(self.headers.get("Content-Length","0"))
            if length<=0 or length>MAX_BODY_BYTES:
                raise ValueError("Request body is missing or too large")
            raw=self.rfile.read(length)
            data=json.loads(raw.decode("utf-8"))
            email=str(data.get("email","")).strip().lower()
            if not EMAIL_RE.fullmatch(email):
                raise ValueError("Enter a valid email address")
            name=str(data.get("name","")).strip()
            if not name or len(name)>100:raise ValueError("Watch name is required")
            channels=data.get("channels") or ["email"]
            if not isinstance(channels,list):raise ValueError("Invalid notification channels")
            channels={str(c).lower() for c in channels}
            if not channels.issubset({"email","whatsapp"}) or not channels:raise ValueError("Choose at least one notification channel")
            email_consent=bool(data.get("email_consent"))
            whatsapp_consent=bool(data.get("whatsapp_consent"))
            if "email" in channels and not email_consent:raise ValueError("Email alerts require explicit consent")
            if "whatsapp" in channels and not whatsapp_consent:raise ValueError("WhatsApp alerts require explicit consent")
            phone=_phone_e164(data.get("phone")) if "whatsapp" in channels else _phone_e164(data.get("phone")) if data.get("phone") else None

            intent=data.get("intent") or {}
            budget_min=_number(intent.get("budget_min"),"Minimum budget",0,1000)
            budget_max=_number(intent.get("budget_max"),"Maximum budget",0,1000)
            age_min=_number(intent.get("min_age_years"),"Minimum vehicle age",0,100)
            age_max=_number(intent.get("max_age_years"),"Maximum vehicle age",0,100)
            if budget_min is not None and budget_max is not None and budget_min>budget_max:raise ValueError("Minimum budget cannot exceed maximum budget")
            if age_min is not None and age_max is not None and age_min>age_max:raise ValueError("Minimum vehicle age cannot exceed maximum age")

            user_rows=_supabase_request(
                "POST","deal_watch_users?on_conflict=email",
                {"email":email,"phone_e164":phone,"updated_at":datetime.now(timezone.utc).isoformat()},
                "resolution=merge-duplicates,return=representation",
            )
            if not user_rows:raise RuntimeError("User record could not be created")
            user_id=user_rows[0]["user_id"]
            watch_id=str(uuid.uuid4())
            constraints={
                "budget_min_lakh":budget_min,"budget_max_lakh":budget_max,
                "min_age_years":age_min,"max_age_years":age_max,
                "make":intent.get("make"),"model":intent.get("model"),
                "condition":intent.get("condition"),"mileage_max_km":intent.get("max_mileage_km"),
                "max_owners":intent.get("max_owners"),"fuel":intent.get("fuel"),
                "transmission":intent.get("transmission"),"location":intent.get("location"),
                "radius_km":intent.get("radius_km"),"must_have":intent.get("must_have_text"),
                "nice_to_have":intent.get("nice_to_have_text"),"avoid":intent.get("avoid_text")
            }
            _supabase_request("POST","deal_watches",{
                "watch_id":watch_id,"user_id":user_id,"name":name,"category":"automotive",
                "natural_language_request":intent.get("query") or None,"constraints":constraints,
                "target_discount_pct":intent.get("target_discount_pct"),
                "alert_quality":intent.get("alert_quality","exceptional"),
                "frequency":intent.get("notification_frequency","instant"),
            },"return=minimal")
            now=datetime.now(timezone.utc).isoformat()
            for channel in ("email","whatsapp"):
                enabled=channel in channels
                consent=(email_consent if channel=="email" else whatsapp_consent)
                if enabled:
                    _supabase_request("POST","channel_preferences?on_conflict=user_id,channel",{
                        "user_id":user_id,"channel":channel,"enabled":True,
                        "frequency":intent.get("notification_frequency","instant"),
                        "consent_at":now,"consent_source":"car-watch-form"
                    },"resolution=merge-duplicates")
            _json_response(self,201,{"ok":True,"watch_id":watch_id,"message":"Car Watch saved"})
        except ValueError as exc:
            _json_response(self,400,{"ok":False,"error":str(exc)})
        except RuntimeError as exc:
            _json_response(self,503,{"ok":False,"error":str(exc)})
        except Exception as exc:
            _json_response(self,500,{"ok":False,"error":"Unable to save the Car Watch"})

    def log_message(self, *_args):
        return
