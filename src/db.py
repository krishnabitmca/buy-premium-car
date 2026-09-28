from __future__ import annotations
import json, sqlite3
from pathlib import Path

SCHEMA="""
CREATE TABLE IF NOT EXISTS vehicles(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 fingerprint TEXT NOT NULL, source_name TEXT NOT NULL, url TEXT NOT NULL, final_url TEXT, title TEXT,
 brand TEXT, model TEXT, variant TEXT, year_manufacture INTEGER, year_registration INTEGER,
 manufacture_date TEXT, registration_date TEXT, mileage_km INTEGER, owner_count INTEGER, price_lakh REAL,
 fuel TEXT, transmission TEXT, location TEXT, certification TEXT, condition_signal TEXT, status_text TEXT,
 crawled_at TEXT NOT NULL, http_status INTEGER, live_verified INTEGER NOT NULL, sold_signal INTEGER NOT NULL,
 data_consistent INTEGER NOT NULL, duplicate_key TEXT, raw_notes TEXT);
CREATE INDEX IF NOT EXISTS idx_vehicle_fingerprint ON vehicles(fingerprint);
CREATE INDEX IF NOT EXISTS idx_vehicle_model ON vehicles(brand,model,year_manufacture);
CREATE TABLE IF NOT EXISTS source_history(domain TEXT PRIMARY KEY,first_seen TEXT NOT NULL,last_seen TEXT NOT NULL,sample_url TEXT,source_name TEXT,known_source INTEGER NOT NULL DEFAULT 0,status TEXT);
CREATE TABLE IF NOT EXISTS run_history(run_id TEXT PRIMARY KEY,started_at TEXT NOT NULL,finished_at TEXT,vehicles_seen INTEGER DEFAULT 0,live_vehicles INTEGER DEFAULT 0,opportunities INTEGER DEFAULT 0,new_sources INTEGER DEFAULT 0,notes TEXT);
"""
def connect(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(path); c.row_factory=sqlite3.Row; c.executescript(SCHEMA); return c
def get_latest_for_fingerprint(c,f):return c.execute("SELECT * FROM vehicles WHERE fingerprint=? ORDER BY id DESC LIMIT 1",(f,)).fetchone()
def insert_vehicle(c,v):
    c.execute("INSERT INTO vehicles(fingerprint,source_name,url,final_url,title,brand,model,variant,year_manufacture,year_registration,manufacture_date,registration_date,mileage_km,owner_count,price_lakh,fuel,transmission,location,certification,condition_signal,status_text,crawled_at,http_status,live_verified,sold_signal,data_consistent,duplicate_key,raw_notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
      (v.fingerprint,v.source_name,v.url,v.final_url,v.title,v.brand,v.model,v.variant,v.year_manufacture,v.year_registration,v.manufacture_date,v.registration_date,v.mileage_km,v.owner_count,v.price_lakh,v.fuel,v.transmission,v.location,v.certification,v.condition_signal,v.status_text,v.crawled_at,v.http_status,int(v.live_verified),int(v.sold_signal),int(v.data_consistent),v.duplicate_key,json.dumps(v.verification_notes,ensure_ascii=False)))
def comparables(c,v,min_year,max_year):
    if not v.brand or not v.model:return []
    rows=c.execute("SELECT * FROM vehicles WHERE live_verified=1 AND sold_signal=0 AND brand=? AND model=? AND year_manufacture BETWEEN ? AND ? AND price_lakh IS NOT NULL AND mileage_km IS NOT NULL AND price_lakh>0 ORDER BY id DESC",(v.brand,v.model,min_year,max_year)).fetchall()
    seen=set();out=[]
    for r in rows:
        if r["fingerprint"] in seen:continue
        seen.add(r["fingerprint"]);out.append(r)
    return out
def record_source(c,domain,url,source_name,known,now,status="seen"):
    c.execute("INSERT INTO source_history(domain,first_seen,last_seen,sample_url,source_name,known_source,status) VALUES(?,?,?,?,?,?,?) ON CONFLICT(domain) DO UPDATE SET last_seen=excluded.last_seen,sample_url=excluded.sample_url,source_name=excluded.source_name,known_source=MAX(source_history.known_source,excluded.known_source),status=excluded.status",(domain,now,now,url,source_name,int(known),status))
def known_domains(c):return {r[0] for r in c.execute("SELECT domain FROM source_history WHERE known_source=1")}
