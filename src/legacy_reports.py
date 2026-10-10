from __future__ import annotations
import argparse,asyncio,csv
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
from .config import load_settings,load_yaml
from .crawler import crawl_urls
from .db import connect,get_latest_for_fingerprint,insert_vehicle,record_source,known_domains,comparables
from .dedupe import dedupe
from .discovery import discover
from .reporting import render_report,write_csv,write_dashboard_json
from .scoring import enrich_and_score,negotiation_band
from .source_registry_db import enabled as source_db_enabled, sync_registry, record_discoveries, record_health, promote_discovery

def load_known_sources(path):return load_yaml(path).get("known_sources",[])
def domain(url):return urlparse(url).netloc.lower().removeprefix("www.")

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--config",default="config/settings.yaml");ap.add_argument("--sources",default="config/sources.yaml");ap.add_argument("--no-discovery",action="store_true");args=ap.parse_args()
    settings=load_settings(args.config);known_sources=load_known_sources(args.sources)
    if source_db_enabled():
        sync_registry(known_sources)
    conn=connect(settings.output["database_path"]);now=datetime.now(timezone.utc).isoformat();run_id=now
    conn.execute("INSERT INTO run_history(run_id,started_at) VALUES(?,?)",(run_id,now))
    for s in known_sources:record_source(conn,domain(s["url"]),s["url"],s["name"],True,now,"known")
    conn.commit()
    from .source_monitoring import crawl_queue
    queue=crawl_queue(known_sources);new_sources=[]
    if not args.no_discovery:
        found=discover(settings,known_domains(conn));cap=int(settings.market.get("max_discovered_sources_per_run",20))
        for r in found[:cap]:record_source(conn,r.domain,r.url,r.domain,False,now,"discovered");new_sources.append({"domain":r.domain,"url":r.url,"title":r.title,"snippet":r.snippet,"query":r.query,"source_type":r.source_type,"condition":r.condition,"segment":r.segment,"brand_hint":r.brand_hint or "","candidate_confidence":r.candidate_confidence});queue.append((r.domain,r.url,3))
    conn.commit()
    if source_db_enabled() and new_sources:
        record_discoveries(new_sources)
    vehicles=dedupe(asyncio.run(crawl_urls(queue,settings)))
    ref_year=int(settings.market["reference_date"][:4]);min_year=ref_year-int(settings.market["default_dashboard_age_years"])+1;filtered=[]
    for v in vehicles:
        # Collection is intentionally broader than any one customer's watch.
        # Budget/age are user-level intent constraints, not ingestion filters.
        if not v.live_verified or v.sold_signal:continue
        if v.price_lakh is None:continue
        filtered.append(v)
    promoted_sources={}
    if source_db_enabled():
        source_counts={}
        for v in filtered:
            source_name=str(v.source_name or "unknown")
            source_counts[source_name]=source_counts.get(source_name,0)+1

        # A discovery becomes eligible for adapter work only after the crawler proves
        # that the discovered page contains multiple extractable live listings.
        # Promotion deliberately stages the source as a candidate; customer search
        # cannot execute it until a verified adapter exists.
        for item in new_sources:
            source_name=str(item.get("domain") or "")
            count=source_counts.get(source_name,0)
            if count >= 2:
                promoted_name=promote_discovery(item, listings_found=count)
                if promoted_name:
                    promoted_sources[source_name]=promoted_name
                    print(f"source staged for adapter verification: {source_name} -> {promoted_name} ({count} listings)")

        for source_name in [s[0] for s in queue]:
            count=source_counts.get(source_name,0)
            health_name=promoted_sources.get(source_name,source_name)
            record_health(
                health_name,
                status="healthy" if count else "unknown",
                listings_found=count,
                parser_ok=bool(count),
                inventory_verified=bool(count),
            )

    changed=[]
    for v in filtered:
        prev=get_latest_for_fingerprint(conn,v.fingerprint)
        if prev and prev["price_lakh"] and v.price_lakh:v.price_delta_pct=100*(v.price_lakh-prev["price_lakh"])/prev["price_lakh"]
        comp_min_year=max(2015,(v.year_manufacture or ref_year)-1)
        comp_max_year=min(ref_year,(v.year_manufacture or ref_year)+1)
        comps=comparables(conn,v,comp_min_year,comp_max_year);enrich_and_score(v,comps,settings);insert_vehicle(conn,v)
        if prev is None or (v.price_delta_pct is not None and abs(v.price_delta_pct)>=float(settings.market["material_price_change_pct"])):changed.append(v)
    conn.commit()
    discovered_path=Path(settings.output["discovered_sources_path"]);discovered_path.parent.mkdir(parents=True,exist_ok=True);write_header=not discovered_path.exists()
    with discovered_path.open("a",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["run_date","domain","url","query","source_type","condition","segment","brand_hint","candidate_confidence"])
        if write_header:w.writeheader()
        for s in new_sources:w.writerow({"run_date":settings.market["reference_date"],**s})
    report_path=settings.output["latest_report_path"];dated_path=str(Path(settings.output["run_report_dir"])/f"run-{settings.market['reference_date']}.md")
    render_report(dated_path,settings.market["reference_date"],changed,new_sources,negotiation_band);render_report(report_path,settings.market["reference_date"],changed,new_sources,negotiation_band)
    write_csv(settings.output["candidates_csv"],changed,negotiation_band)
    default_under_budget=sum(v.price_lakh is not None and v.price_lakh<=float(settings.market["default_dashboard_budget_lakh"]) for v in filtered)
    default_within_age=sum(v.year_manufacture is not None and v.year_manufacture>=min_year for v in filtered)
    current_opportunities=sum(v.opportunity_class in {"exceptional","bargain"} for v in filtered)
    write_dashboard_json(
        settings.output.get("dashboard_json_path","data/latest.json"),
        settings.market["reference_date"],filtered,new_sources,negotiation_band,
        stats={
            "vehicles_seen":len(vehicles),
            "live_listings":len(filtered),
            "default_under_budget":default_under_budget,
            "default_within_age":default_within_age,
            "changed":len(changed),
            "opportunities":current_opportunities,
            "new_sources":len(new_sources),
            "default_budget_lakh":float(settings.market["default_dashboard_budget_lakh"]),
            "default_age_years":float(settings.market["default_dashboard_age_years"])
        }
    )
    opportunities=current_opportunities;conn.execute("UPDATE run_history SET finished_at=?,vehicles_seen=?,live_vehicles=?,opportunities=?,new_sources=? WHERE run_id=?",(datetime.now(timezone.utc).isoformat(),len(vehicles),len(filtered),opportunities,len(new_sources),run_id));conn.commit();conn.close()
    print(f"vehicles={len(vehicles)} live_listings={len(filtered)} default_under_budget={default_under_budget} changed={len(changed)} new_sources={len(new_sources)} opportunities={opportunities}")

if __name__=="__main__":main()
