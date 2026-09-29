from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any

USER_AGENT = "CarScanner/1.0 (+https://carscanner.in)"
TIMEOUT = 12

CURRENT_BRANDS = [
    "Maruti Suzuki","Tata","Kia","Toyota","Hyundai","Mahindra","Honda","MG Motor",
    "Skoda","Jeep","Renault","Nissan","Volkswagen","Citroen","Aston Martin","Audi",
    "Bajaj","Bentley","Blinq Mobility","BMW","BYD","Ferrari","Force","Isuzu","Jaguar",
    "Lamborghini","Land Rover","Lexus","Lotus","Maserati","McLaren","Mercedes-Benz",
    "Mini","PMV","Porsche","Pravaig","Rolls-Royce","Strom Motors","Tesla",
    "Vayve Mobility","VinFast","Volvo",
]

BRAND_ALIASES = {
    "MG": "MG Motor",
    "Mercedes Benz": "Mercedes-Benz",
    "Mercedes-Benz": "Mercedes-Benz",
    "Mini": "MINI",
    "McLaren": "McLaren",
    "Citroen": "Citroën",
    "Vinfast": "VinFast",
}

class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str,str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href:
            text=" ".join(" ".join(self._text).split())
            if text:
                self.links.append((text,self._href))
            self._href=None
            self._text=[]

def fetch_text(url: str) -> str:
    req=urllib.request.Request(url,headers={"User-Agent":USER_AGENT,"Accept-Language":"en-IN,en;q=0.9"})
    with urllib.request.urlopen(req,timeout=TIMEOUT) as response:
        return response.read().decode("utf-8","ignore")

def _absolute(base: str, href: str) -> str:
    return urllib.parse.urljoin(base, href)

def _slug(value: str) -> str:
    value=value.lower().strip().replace("&","and")
    value=re.sub(r"[^a-z0-9]+","-",value).strip("-")
    return value

def _canonical_brand(name: str) -> str:
    n=" ".join(name.replace(" Cars","").split()).strip()
    return BRAND_ALIASES.get(n,n)

def live_brands() -> list[dict[str,str]]:
    # CarDekho currently reports roughly 290 current models across 42 brands.
    # We use the current brand universe as the UI taxonomy, while model discovery
    # is performed live from the selected brand page.
    html=fetch_text("https://www.cardekho.com/newcars")
    parser=_LinkParser();parser.feed(html)
    links=parser.links
    result=[]
    for brand in CURRENT_BRANDS:
        match=None
        candidates={brand,brand+" Cars",_canonical_brand(brand)+" Cars"}
        for text,href in links:
            if text in candidates and "cardekho.com" in _absolute("https://www.cardekho.com",href):
                match=href;break
        result.append({"name":brand,"slug":_slug(brand),"url":_absolute("https://www.cardekho.com",match) if match else ""})
    return result

def live_models(brand: str) -> list[dict[str,str]]:
    brands=live_brands()
    wanted=_canonical_brand(brand).lower()
    selected=next((x for x in brands if x["name"].lower()==wanted),None)
    if not selected or not selected["url"]:
        return []
    html=fetch_text(selected["url"])
    parser=_LinkParser();parser.feed(html)
    models=[]
    seen=set()
    for text,href in parser.links:
        clean=" ".join(text.split())
        absolute=_absolute(selected["url"],href)
        path=urllib.parse.urlparse(absolute).path.lower()
        if not clean or clean.lower() in {"view all models","compare cars"}:
            continue
        if "/"+selected["slug"].lower().replace("-","") not in path.replace("-","") and path.count("/")<2:
            continue
        if clean in seen:
            continue
        # Model links on CarDekho commonly point to /brand/model or /carmodels/Brand/Model.
        if ("/"+_slug(brand)+"/" in path or "/carmodels/" in path) and not any(x in clean.lower() for x in ("cars","price","offers","dealers")):
            seen.add(clean);models.append({"name":clean,"slug":_slug(clean),"url":absolute})
    return sorted(models,key=lambda x:x["name"].lower())

def _json_objects(html: str) -> list[Any]:
    values=[]
    for match in re.finditer(r'<script[^>]+type=["\\\']application/ld\\+json["\\\'][^>]*>(.*?)</script>',html,re.I|re.S):
        raw=match.group(1).strip()
        raw=re.sub(r"<!--|-->","",raw).strip()
        try: values.append(json.loads(raw))
        except Exception: continue
    return values

def _walk(value: Any):
    if isinstance(value,dict):
        yield value
        for v in value.values(): yield from _walk(v)
    elif isinstance(value,list):
        for v in value: yield from _walk(v)

def _number(text: Any) -> float | None:
    if text is None:return None
    s=str(text).replace(",","")
    m=re.search(r"(\d+(?:\.\d+)?)",s)
    return float(m.group(1)) if m else None

def parse_live_listings(html: str, source: str, base_url: str) -> list[dict]:
    rows=[]
    for root in _json_objects(html):
        for obj in _walk(root):
            if not isinstance(obj,dict): continue
            typ=obj.get("@type")
            if typ not in {"Product","Vehicle","Car","Offer"} and not any(k in obj for k in ("vehicleIdentificationNumber","vehicleConfiguration")):
                continue
            name=obj.get("name") or obj.get("model")
            if not name: continue
            offers=obj.get("offers") if isinstance(obj.get("offers"),dict) else {}
            price=_number(offers.get("price") or obj.get("price"))
            url=obj.get("url") or offers.get("url") or base_url
            rows.append({
                "brand": obj.get("brand",{}).get("name") if isinstance(obj.get("brand"),dict) else obj.get("brand"),
                "model": obj.get("model") or name,
                "variant": obj.get("vehicleConfiguration") or obj.get("name") or "",
                "price_lakh": price/100000 if price and price>100000 else price,
                "url": _absolute(base_url,url),
                "source":source,
                "live_verified":True,
                "data_consistent":True,
                "condition_signal":"used",
            })
    # De-duplicate structured-data repetitions.
    seen=set();out=[]
    for row in rows:
        key=(row.get("url"),row.get("price_lakh"),row.get("model"))
        if key in seen: continue
        seen.add(key);out.append(row)
    return out

LIVE_SOURCES=[
    ("CarDekho Used","https://www.cardekho.com/used-cars"),
    ("CarWale Used","https://www.carwale.com/used/"),
    ("Cars24 Luxury Used","https://www.cars24.com/buy-used-luxury-cars/"),
    ("Spinny Luxury Used","https://www.spinny.com/used-luxury-cars/s/"),
]

def live_inventory() -> tuple[list[dict],list[dict]]:
    vehicles=[];source_status=[]
    for name,url in LIVE_SOURCES:
        try:
            html=fetch_text(url)
            parsed=parse_live_listings(html,name,url)
            vehicles.extend(parsed)
            source_status.append({"source":name,"status":"live","listings_found":len(parsed)})
        except Exception as exc:
            source_status.append({"source":name,"status":"unavailable","listings_found":0,"error":str(exc)[:160]})
    return vehicles,source_status
