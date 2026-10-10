from __future__ import annotations

import html
import argparse
import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from src.car_watch import evaluate_watch
from src.inventory_db import iter_inventory
from src.normalize import normalize_model
from src.source_registry_db import require_database


def active_watches(page_size=100):
    offset = 0
    while True:
        rows = sb_request("GET", "deal_watches?select=*,deal_watch_users!inner(*),watch_channel_preferences(*)"
                          "&status=eq.active&deal_watch_users.status=eq.active&order=watch_id.asc"
                          f"&limit={page_size}&offset={offset}")
        yield from rows
        if len(rows) < page_size:
            return
        offset += len(rows)


def inventory_matches(watch):
    constraints = watch.get("constraints") or {}
    parsed_make, parsed_model, _ = normalize_model(
        watch.get("natural_language_request") or "", watch.get("natural_language_request") or "")
    query = " ".join(str(x) for x in (constraints.get("make") or parsed_make,
                                     constraints.get("model") or parsed_model) if x)
    condition = constraints.get("condition") or "both"
    if condition == "used_demo":
        condition = "both"
    # Do not budget-filter the comparison cohort before calculating reference
    # prices. Customer constraints are enforced by the shared deal engine.
    for rows in iter_inventory(query=query, condition=condition):
        yield from evaluate_watch(watch, rows)


def event_type_for(vehicle):
    # New prices may alert again; another crawl at the same price must not.
    value = json.dumps([vehicle.get("price_lakh"),vehicle.get("price_basis"),
                        vehicle.get("condition_signal")],separators=(",", ":"))
    return "deal_match:" + hashlib.sha256(value.encode()).hexdigest()[:24]

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

def process_alerts(mode="instant", dry_run=False):
    require_database()
    sent=0;failed=0
    matched=0
    for watch in active_watches():
        if watch.get("status") != "active" or watch.get("frequency", "instant") not in {mode,"both"}:
            continue
        user=(watch.get("deal_watch_users") or {})
        if user.get("status") != "active":
            continue
        prefs=watch.get("watch_channel_preferences") or []
        for vehicle,evaluation in inventory_matches(watch):
            matched += 1
            for pref in prefs:
                if not pref.get("enabled") or not pref.get("consent_at"):continue
                if pref.get("frequency", "instant") not in {mode,"both"}:continue
                channel=pref.get("channel")
                if channel not in {"email","whatsapp"}:continue
                if dry_run:
                    continue
                event_type=event_type_for(vehicle)
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
                    fair_text=f"₹{float(fair):.2f}L (observed comparison median)" if fair is not None else "not established"
                    location=vehicle.get("location") or "India"
                    app=os.environ.get("APP_BASE_URL","https://buy-premium-car.vercel.app").rstrip("/")
                    dashboard=f"{app}/?q="+urllib.parse.quote(title)
                    reason="; ".join(evaluation.reasons[:2]) or "matches your Car Watch"
                    if channel=="email":
                        listing_url = vehicle.get("final_url") or vehicle.get("url") or dashboard
                        body=f"<h2>Car Watch hit</h2><p><b>{html.escape(title)}</b> — {html.escape(price)}</p><p>Comparison: {html.escape(fair_text)} · {html.escape(str(location))}</p><p>{html.escape(reason)}</p><p>Observed: {html.escape(str(vehicle.get('observed_at') or 'unknown'))}</p><p><a href='{html.escape(str(listing_url),quote=True)}'>Open original listing</a></p>"
                        provider=send_resend(user["email"],f"Car Watch hit: {title} at {price}",body,str(alert_id))
                    else:
                        if not user.get("phone_e164"):
                            raise RuntimeError("WhatsApp destination is missing")
                        provider=send_whatsapp(user["phone_e164"],[watch["name"],title,price,fair_text,str(location)])
                    provider_id=(provider.get("id") if isinstance(provider,dict) else None)
                    if channel == "whatsapp" and isinstance(provider,dict):
                        messages=provider.get("messages") or []
                        provider_id=messages[0].get("id") if messages else None
                    sb_request("PATCH",f"alert_events?alert_id=eq.{alert_id}",{"status":"sent","provider_message_id":provider_id,"sent_at":datetime.now(timezone.utc).isoformat()})
                    sent+=1
                except Exception as exc:
                    sb_request("PATCH",f"alert_events?alert_id=eq.{alert_id}",{"status":"failed","error_message":str(exc)[:500]})
                    failed+=1
    result={"matched":matched,"sent":sent,"failed":failed,"dry_run":dry_run}
    print(result)
    return result


def main():
    parser=argparse.ArgumentParser(description="Process watches against canonical PostgreSQL inventory")
    parser.add_argument("--mode",choices=("instant","daily"),default="instant")
    parser.add_argument("--dry-run",action="store_true",help="Evaluate matches without event writes or provider calls")
    args=parser.parse_args()
    result=process_alerts(args.mode,args.dry_run)
    if result["failed"]:
        raise SystemExit(1)

if __name__=="__main__":main()
