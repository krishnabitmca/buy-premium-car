from __future__ import annotations

import html
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from src.car_watch import evaluate_watch

def sb_request(method,path,payload=None,prefer=None):
    base=os.environ["SUPABASE_URL"].rstrip("/")
    key=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    body=None if payload is None else json.dumps(payload).encode()
    headers={"apikey":key,"Authorization":f"Bearer {key}","Content-Type":"application/json"}
    if prefer:headers["Prefer"]=prefer
    req=urllib.request.Request(base+"/rest/v1/"+path,data=body,headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=20) as r:
        raw=r.read().decode()
        return json.loads(raw) if raw else []

def send_resend(to,subject,html_body,idempotency_key):
    key=os.environ.get("RESEND_API_KEY")
    sender=os.environ.get("RESEND_FROM_EMAIL")
    if not key or not sender:raise RuntimeError("Resend is not configured")
    payload=json.dumps({"from":sender,"to":[to],"subject":subject,"html":html_body}).encode()
    req=urllib.request.Request("https://api.resend.com/emails",data=payload,headers={
        "Authorization":f"Bearer {key}","Content-Type":"application/json","Idempotency-Key":idempotency_key
    },method="POST")
    with urllib.request.urlopen(req,timeout=20) as r:
        return json.loads(r.read().decode())

def send_whatsapp(phone,params):
    token=os.environ.get("WHATSAPP_ACCESS_TOKEN")
    phone_id=os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    template=os.environ.get("WHATSAPP_TEMPLATE_NAME")
    language=os.environ.get("WHATSAPP_TEMPLATE_LANGUAGE","en_US")
    version=os.environ.get("WHATSAPP_GRAPH_VERSION")
    if not all((token,phone_id,template,version)):raise RuntimeError("WhatsApp is not configured")
    body={"messaging_product":"whatsapp","to":phone,"type":"template","template":{
        "name":template,"language":{"code":language},
        "components":[{"type":"body","parameters":[{"type":"text","text":str(p)} for p in params]}]
    }}
    payload=json.dumps(body).encode()
    req=urllib.request.Request(f"https://graph.facebook.com/{version}/{phone_id}/messages",data=payload,headers={
        "Authorization":f"Bearer {token}","Content-Type":"application/json"
    },method="POST")
    with urllib.request.urlopen(req,timeout=20) as r:
        return json.loads(r.read().decode())

def main():
    watches=sb_request("GET","deal_watches?select=*,deal_watch_users(*),watch_channel_preferences(*)&status=eq.active")
    latest=Path("data/latest.json")
    if not latest.exists():return
    data=json.loads(latest.read_text(encoding="utf-8"))
    vehicles=data.get("vehicles") or []
    sent=0;failed=0
    for watch in watches:
        matches=evaluate_watch(watch,vehicles)
        user=(watch.get("deal_watch_users") or {})
        prefs=watch.get("watch_channel_preferences") or []
        for vehicle,evaluation in matches:
            for pref in prefs:
                if not pref.get("enabled"):continue
                channel=pref.get("channel")
                event_type="deal_match"
                existing=sb_request("GET",f"alert_events?select=alert_id,status&watch_id=eq.{watch['watch_id']}&listing_id=eq.{evaluation.listing_id}&channel=eq.{channel}&event_type=eq.{event_type}&limit=1")
                payload={"vehicle":vehicle,"evaluation":{"match_score":evaluation.match_score,"deal_score":evaluation.deal_score,"confidence":evaluation.confidence,"reasons":evaluation.reasons,"risks":evaluation.risks}}
                if existing:
                    if existing[0]["status"] in {"sent","pending"}:continue
                    alert_id=existing[0]["alert_id"]
                    sb_request("PATCH",f"alert_events?alert_id=eq.{alert_id}",{"status":"pending","payload":payload,"error_message":None})
                else:
                    row=sb_request("POST","alert_events",{"user_id":watch["user_id"],"watch_id":watch["watch_id"],"listing_id":evaluation.listing_id,"channel":channel,"event_type":event_type,"status":"pending","payload":payload},"return=representation")
                    alert_id=row[0]["alert_id"]
                try:
                    title=f"{vehicle.get('brand','')} {vehicle.get('model','')}".strip()
                    price=f"₹{float(vehicle.get('price_lakh') or 0):.2f}L"
                    fair=vehicle.get("comp_median")
                    fair_text=f"₹{float(fair):.2f}L" if fair is not None else "not established"
                    location=vehicle.get("location") or "India"
                    app=os.environ.get("APP_BASE_URL","https://buy-premium-car.vercel.app").rstrip("/")
                    dashboard=f"{app}/?q="+urllib.parse.quote(title)
                    reason="; ".join(evaluation.reasons[:2]) or "matches your Car Watch"
                    if channel=="email":
                        body=f"<h2>Car Watch hit</h2><p><b>{html.escape(title)}</b> — {html.escape(price)}</p><p>Fair value: {html.escape(fair_text)} · {html.escape(str(location))}</p><p>{html.escape(reason)}</p><p><a href='{html.escape(dashboard)}'>Open dashboard</a></p>"
                        provider=send_resend(user["email"],f"Car Watch hit: {title} at {price}",body,str(alert_id))
                    else:
                        if not user.get("phone_e164"):
                            raise RuntimeError("WhatsApp destination is missing")
                        provider=send_whatsapp(user["phone_e164"],[watch["name"],title,price,fair_text,str(location)])
                    provider_id=(provider.get("id") if isinstance(provider,dict) else None)
                    sb_request("PATCH",f"alert_events?alert_id=eq.{alert_id}",{"status":"sent","provider_message_id":provider_id,"sent_at":datetime.now(timezone.utc).isoformat()})
                    sent+=1
                except Exception as exc:
                    sb_request("PATCH",f"alert_events?alert_id=eq.{alert_id}",{"status":"failed","error_message":str(exc)[:500]})
                    failed+=1
    print(f"alerts_sent={sent} alerts_failed={failed}")

if __name__=="__main__":main()
