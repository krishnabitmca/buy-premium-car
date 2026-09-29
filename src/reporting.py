from __future__ import annotations
import csv,json
from datetime import datetime,timezone
from pathlib import Path

def format_car(v,nego):
    target,walk=nego(v)
    return {
        "brand":v.brand,"model":v.model,"variant":v.variant or "",
        "mfg_year":v.year_manufacture,"reg_year":v.year_registration,
        "km":v.mileage_km,"owners":v.owner_count,"price_lakh":v.price_lakh,
        "location":v.location or "","seller_city":v.seller_city or v.location or "",
        "seller_state":v.seller_state or "","registration_state":v.registration_state or "",
        "source":v.source_name,"url":v.url,"image_urls":v.image_urls,
        "source_count":v.source_count,"source_listings":v.source_listings,
        "lowest_observed_price_lakh":v.lowest_observed_price_lakh,
        "highest_observed_price_lakh":v.highest_observed_price_lakh,
        "identity_confidence":v.identity_confidence,
        "live":v.live_verified,"comparables":v.comparable_count,
        "comp_median":v.comparable_median_lakh,"comp_low":v.comparable_low_lakh,
        "comp_high":v.comparable_high_lakh,"discount_pct":v.discount_vs_comparable_pct,
        "km_per_year":v.km_per_year,"score":v.opportunity_score,"class":v.opportunity_class,
        "negotiation_target_lakh":target,"walk_away_lakh":walk,
        "certification":v.certification,"condition_signal":v.condition_signal,
        "notes":"; ".join(v.verification_notes),
        "decision_signals":{
            "price_context":f"{v.discount_vs_comparable_pct:.1f}% below comparable median" if v.discount_vs_comparable_pct is not None else "Market comparison not established",
            "sources":v.source_count,
            "verification":"verified" if v.live_verified and v.data_consistent else "needs review"
        }
    }

def write_csv(path,vehicles,negotiation_lookup):
    Path(path).parent.mkdir(parents=True,exist_ok=True);rows=[format_car(v,negotiation_lookup) for v in vehicles]
    if not rows:Path(path).write_text("",encoding="utf-8");return
    with open(path,"w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)

def render_report(path,run_date,vehicles,new_sources,negotiation_lookup,changed_only=True):
    reportable=[v for v in vehicles if v.live_verified and v.opportunity_class in {"exceptional","bargain","low-mileage-watch"}]
    reportable.sort(key=lambda x:(x.opportunity_class!="exceptional",-(x.opportunity_score or 0),x.price_lakh or 999))
    lines=[f"# Premium Car Deal Radar — {run_date}","","**Verification mode:** live vehicle page required; stale/sold indicators excluded.",""]
    if not reportable and not new_sources:lines.append("No genuinely attractive new or materially changed opportunities were detected in this run.")
    if reportable:
        lines += ["## Opportunities",""]
        for v in reportable[:20]:
            target,walk=negotiation_lookup(v)
            lines += [f"### {v.brand} {v.model}{(' — '+v.variant) if v.variant else ''}",f"- **Ask:** ₹{v.price_lakh:.2f}L | **Mfg:** {v.year_manufacture or '—'} | **Reg:** {v.year_registration or '—'} | **Km:** {v.mileage_km or '—'} | **Owners:** {v.owner_count or '—'}",f"- **Source:** {v.source_name} | **Live:** {v.live_verified} | **Opportunity:** {v.opportunity_class} | **Score:** {v.opportunity_score}",f"- **Comparable median:** ₹{v.comparable_median_lakh:.2f}L from {v.comparable_count} comparable observations" if v.comparable_median_lakh else "- **Comparable market:** insufficient evidence yet",f"- **Discount vs comparable median:** {v.discount_vs_comparable_pct:.1f}%" if v.discount_vs_comparable_pct is not None else "- **Discount vs comparable median:** not established",f"- **Negotiation target:** ₹{target:.2f}L | **Walk-away:** ₹{walk:.2f}L" if target is not None else "- Negotiation range: insufficient price data",f"- **Verification notes:** {'; '.join(v.verification_notes) if v.verification_notes else 'none'}",f"- **Listing:** {v.url}",""]
    if new_sources:
        lines += ["## New Sources Discovered",""]+[f"- **{s['domain']}** — {s.get('url','')} — found from: {s.get('query','')}" for s in new_sources]+[""]
    Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text("\n".join(lines),encoding="utf-8")

def write_dashboard_json(path,run_date,vehicles,new_sources,negotiation_lookup,stats=None):
    payload={"run_date":run_date,"generated_at":datetime.now(timezone.utc).isoformat(),"stats":stats or {},"vehicles":[format_car(v,negotiation_lookup)|{"manufacture_date":v.manufacture_date,"registration_date":v.registration_date,"fuel":v.fuel,"transmission":v.transmission,"certification":v.certification,"condition_signal":v.condition_signal,"live_verified":v.live_verified,"sold_signal":v.sold_signal,"data_consistent":v.data_consistent,"verification_notes_list":v.verification_notes,"crawled_at":v.crawled_at,"final_url":v.final_url,"http_status":v.http_status,"price_delta_pct":v.price_delta_pct,"comparable_low_lakh":v.comparable_low_lakh,"comparable_high_lakh":v.comparable_high_lakh,"opportunity_score":v.opportunity_score} for v in vehicles],"new_sources":new_sources}
    Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
