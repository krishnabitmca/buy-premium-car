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

def _is_current_model_link(selected: dict[str,str], href: str) -> bool:
    """Accept only canonical CarDekho model landing pages, never variants/dealers/offers."""
    parsed=urllib.parse.urlparse(href)
    host=parsed.netloc.lower()
    path=parsed.path.rstrip("/").lower()
    if host and "cardekho.com" not in host:
        return False
    parts=[p for p in path.split("/") if p]
    brand_slug=_slug(selected["name"])
    if len(parts)==2 and parts[0]==brand_slug:
        return True
    if len(parts)==3 and parts[0]=="carmodels" and parts[1]==brand_slug:
        return True
    return False

def live_models(brand: str) -> list[dict[str,str]]:
    brands=live_brands()
    wanted=_canonical_brand(brand).lower()
    selected=next((x for x in brands if x["name"].lower()==wanted),None)
    if not selected or not selected["url"]:
        return []
    html=fetch_text(selected["url"])
    parser=_LinkParser();parser.feed(html)
    models=[]
    seen_urls=set()
    for text,href in parser.links:
        clean=" ".join(text.split())
        absolute=_absolute(selected["url"],href)
        if not clean or not _is_current_model_link(selected,absolute):
            continue
        canonical=absolute.split("#",1)[0].rstrip("/")
        if canonical in seen_urls:
            continue
        seen_urls.add(canonical)
        models.append({"name":clean,"slug":_slug(clean),"url":canonical})
    return sorted(models,key=lambda x:x["name"].lower())

def _identity_tokens(value: Any) -> list[str]:
    return re.findall(r"[a-z0-9]+",str(value or "").lower())

def _model_identity_matches(requested: str, *candidates: Any) -> bool:
    wanted=_identity_tokens(requested)
    if not wanted:
        return False
    for candidate in candidates:
        tokens=_identity_tokens(candidate)
        for i in range(0,len(tokens)-len(wanted)+1):
            if tokens[i:i+len(wanted)]==wanted:
                return True
    return False

def _identity_matches_query(row: dict, query: str) -> bool:
    brand,model=_query_parts(query)
    if brand and not _model_identity_matches(brand,row.get("brand"),row.get("listing_name"),row.get("url")):
        return False
    if model and not _model_identity_matches(model,row.get("model"),row.get("listing_name"),row.get("variant"),row.get("url")):
        return False
    return True

def _json_objects(html: str) -> list[Any]:
    # Marketplace pages are inconsistent about attribute order, quoting and
    # whitespace around the JSON-LD script type. Keep extraction tolerant so
    # valid structured-data blocks are not silently discarded.
    values=[]
    pattern = r'<script[^>]*?type\s*=\s*["\']application/ld\+json(?:;[^"\']*)?["\'][^>]*>(.*?)</script>'
    for match in re.finditer(pattern,html,re.I|re.S):
        raw=re.sub(r"<!--|-->","",match.group(1)).strip()
        try:
            values.append(json.loads(raw))
        except Exception:
            continue
    return values
def _walk(value: Any):
    if isinstance(value,dict):
        yield value
        for v in value.values(): yield from _walk(v)
    elif isinstance(value,list):
        for v in value: yield from _walk(v)

def _number(text: Any) -> float | None:
    if text is None:
        return None
    s=str(text).replace(",", "").replace("₹", "").strip()
    m=re.search(r"(\d+(?:\.\d+)?)",s)
    return float(m.group(1)) if m else None

def _first_value(obj: dict, *keys: str):
    for key in keys:
        value=obj.get(key)
        if value not in (None,"",[],{}):
            if isinstance(value,dict):
                value=value.get("name") or value.get("value") or value.get("addressLocality")
            return value
    return None

def _text_blob(obj: dict) -> str:
    values=[]
    for key in ("name","description","vehicleConfiguration","fuelType","bodyType","itemCondition",
                "vehicleCondition","seller","address","location","category"):
        value=obj.get(key)
        if isinstance(value,dict):
            value=" ".join(str(v) for v in value.values())
        elif isinstance(value,list):
            value=" ".join(str(v) for v in value)
        if value:
            values.append(str(value))
    return " ".join(values)

def _infer_condition(obj: dict, source: str) -> str:
    explicit=_first_value(obj,"itemCondition","vehicleCondition","condition_signal","condition")
    text=f"{explicit or ''} {_text_blob(obj)} {source}".lower()
    if any(x in text for x in ("demonstrator","demo car","demo vehicle","demo")):
        return "demo"
    return "used"

def _infer_location(obj: dict) -> tuple[str|None,str|None,str|None]:
    candidates=[]
    for key in ("seller","location","address","availableAtOrFrom"):
        value=obj.get(key)
        if isinstance(value,dict):
            candidates.append(value)
            nested=value.get("address")
            if isinstance(nested,dict): candidates.append(nested)
        elif value:
            candidates.append({"value":value})
    city=state=None
    for item in candidates:
        if not isinstance(item,dict): continue
        city=city or item.get("addressLocality") or item.get("city")
        state=state or item.get("addressRegion") or item.get("state")
    raw=" ".join(str(x) for x in candidates)
    if not city:
        m=re.search(r"(?:seller|location|city)[:\s-]+([A-Za-z .-]{3,40})",raw,re.I)
        city=m.group(1).strip(" .-") if m else None
    return (str(city).strip() if city else None,
            str(state).strip() if state else None,
            raw or None)

def _infer_year(obj: dict) -> int|None:
    value=_first_value(obj,"vehicleModelDate","modelDate","productionDate","dateCreated","mfg_year","year")
    if value:
        m=re.search(r"\b(19\d{2}|20\d{2})\b",str(value))
        if m:return int(m.group(1))
    m=re.search(r"\b(19\d{2}|20\d{2})\b",_text_blob(obj))
    return int(m.group(1)) if m else None

def _infer_mileage(obj: dict) -> float|None:
    value=_first_value(obj,"mileageFromOdometer","mileage","odometer")
    if isinstance(value,dict):
        value=value.get("value") or value.get("name")
    if value is not None:
        n=_number(value)
        if n is not None:
            text=str(value).lower()
            if "km" in text or "kilomet" in text:return n
            if "mile" in text:return round(n*1.60934)
            return n
    text=_text_blob(obj)
    m=re.search(r"([\d,]+(?:\.\d+)?)\s*(?:km|kms|kilometers|kilometres)\b",text,re.I)
    return _number(m.group(1)) if m else None

def _infer_text_attribute(obj: dict, *keys: str) -> str|None:
    value=_first_value(obj,*keys)
    if value is None:return None
    return str(value).strip() or None

def _infer_brand_model(name: str, brand: Any, model: Any) -> tuple[str|None,str]:
    if isinstance(brand,dict): brand=brand.get("name")
    b=str(brand).strip() if brand else ""
    m=str(model).strip() if model else ""
    if b and m: return b,m
    clean=" ".join(str(name or "").split())
    for candidate in sorted(CURRENT_BRANDS,key=len,reverse=True):
        if clean.lower().startswith(candidate.lower()+" "):
            return candidate,clean[len(candidate):].strip()
    parts=clean.split(" ",1)
    return (parts[0] if parts else None),(parts[1] if len(parts)>1 else clean)

def _query_parts(query: str) -> tuple[str|None,str|None]:
    q=" ".join(str(query or "").split()).strip()
    low=q.lower()
    for brand in sorted(CURRENT_BRANDS,key=len,reverse=True):
        if brand.lower() in low:
            model=q[:low.find(brand.lower())]+q[low.find(brand.lower())+len(brand):]
            model=re.sub(r"\\s+"," ",model).strip()
            # The UI may send brand twice when the selected model includes the brand.
            model=re.sub(re.escape(brand), "", model, count=1, flags=re.I).strip()
            return brand, model or None
    return None, q or None

def _targeted_source_urls(query: str) -> dict[str,str]:
    brand,model=_query_parts(query)
    if not brand or not model:
        return {}
    brand_slug=_slug(_canonical_brand(brand))
    model_slug=_slug(model)
    if not model_slug:
        return {}
    # These routes are verified marketplace model pages and keep the live query
    # India-wide rather than constraining it to the user's destination.
    return {
        "CarDekho Used": f"https://www.cardekho.com/used-{brand_slug}-{model_slug}+cars",
        "CarWale Used": f"https://www.carwale.com/used/{brand_slug}-{model_slug}/",
    }

def parse_visible_listing_links(html: str, source: str, base_url: str, query: str="") -> list[dict]:
    parser=_LinkParser()
    parser.feed(html)
    brand,model=_query_parts(query)
    rows=[]
    for text,href in parser.links:
        clean=" ".join(text.split())
        if not re.search(r"\b(?:19\d{2}|20\d{2})\b",clean):
            continue
        price_match=re.search(r"(?:₹|Rs\.?)[ ]*([\d,.]+)[ ]*(Lakh|Crore)",clean,re.I)
        km_match=re.search(r"([\d,]+(?:\.\d+)?)\s*km\b",clean,re.I)
        if not price_match or not km_match:
            continue
        year_match=re.search(r"\b(19\d{2}|20\d{2})\b",clean)
        if not year_match:
            continue
        price=float(price_match.group(1).replace(",",""))
        price_lakh=price*100 if price_match.group(2).lower()=="crore" else price
        parts=[p.strip() for p in clean.split("|")]
        fuel=parts[1] if len(parts)>1 and parts[1] else None
        location=parts[2] if len(parts)>2 else None
        transmission=None
        tm=re.search(r"\b(Automatic|Manual|Clutchless Manual)\b",clean,re.I)
        if tm: transmission=tm.group(1)
        variant=clean[year_match.end():km_match.start()].strip(" -|•") or clean
        display_model=model
        if not display_model:
            _,display_model=_infer_brand_model(variant,None,None)
        rows.append({
            "brand":brand,
            "model":display_model,
            "listing_name":clean,
            "variant":variant,
            "price_lakh":price_lakh,
            "url":_absolute(base_url,href),
            "source":source,
            "live_verified":True,
            "data_consistent":bool(href and price_lakh and variant),
            "condition_signal":"used" if "used" in source.lower() else _infer_condition({},source),
            "seller_city":location,
            "seller_state":None,
            "location":location,
            "location_raw":location,
            "mfg_year":int(year_match.group(1)),
            "km":float(km_match.group(1).replace(",","")),
            "fuel":fuel,
            "transmission":transmission,
            "body_type":None,
        })
    seen=set();out=[]
    for row in rows:
        key=(row["url"],row["price_lakh"],row["model"],row["condition_signal"])
        if key in seen: continue
        seen.add(key);out.append(row)
    return out
def parse_live_listings(html: str, source: str, base_url: str) -> list[dict]:
    rows=[]
    for root in _json_objects(html):
        for obj in _walk(root):
            if not isinstance(obj,dict): continue
            typ=obj.get("@type")
            if isinstance(typ,list):
                is_vehicle=any(str(t).lower() in {"product","vehicle","car","offer"} for t in typ)
            else:
                is_vehicle=str(typ).lower() in {"product","vehicle","car","offer"}
            if not is_vehicle and not any(k in obj for k in ("vehicleIdentificationNumber","vehicleConfiguration")):
                continue
            name=obj.get("name") or obj.get("model")
            if not name: continue
            offers=obj.get("offers") if isinstance(obj.get("offers"),dict) else {}
            price_raw=offers.get("price") or obj.get("price")
            price=_number(price_raw)
            price_text=str(price_raw or "")
            price_lakh=(price/100000 if price and price>100000 else price)
            url=obj.get("url") or offers.get("url") or base_url
            brand,model=_infer_brand_model(str(name),obj.get("brand"),obj.get("model"))
            seller_city,seller_state,location_raw=_infer_location(obj)
            location=seller_city or seller_state
            row={
                "brand":brand,
                "model":model,
                "listing_name":str(name),
                "variant":obj.get("vehicleConfiguration") or obj.get("vehicleVariant") or obj.get("name") or "",
                "price_lakh":price_lakh,
                "url":_absolute(base_url,str(url)),
                "source":source,
                "live_verified":True,
                "data_consistent":bool(name and price is not None and url),
                "condition_signal":_infer_condition(obj,source),
                "seller_city":seller_city,
                "seller_state":seller_state,
                "location":location,
                "location_raw":location_raw,
                "mfg_year":_infer_year(obj),
                "km":_infer_mileage(obj),
                "fuel":_infer_text_attribute(obj,"fuelType","fuel","fuel_type"),
                "transmission":_infer_text_attribute(obj,"vehicleTransmission","transmission","gearbox"),
                "body_type":_infer_text_attribute(obj,"bodyType","body_type"),
            }
            if price_text and price_lakh is None:
                continue
            rows.append(row)
    seen=set();out=[]
    for row in rows:
        key=(row.get("url"),row.get("price_lakh"),row.get("model"),row.get("condition_signal"))
        if key in seen: continue
        seen.add(key);out.append(row)
    return out

LIVE_SOURCES=[
    ("Motozite Demo","https://motozite.com/demo-cars"),
    ("CarDekho Used","https://www.cardekho.com/used-cars"),
    ("CarWale Used","https://www.carwale.com/used/"),
    ("Cars24 Luxury Used","https://www.cars24.com/buy-used-luxury-cars/"),
    ("Spinny Luxury Used","https://www.spinny.com/used-luxury-cars/s/"),
]

def live_inventory(query: str="") -> tuple[list[dict],list[dict]]:
    vehicles=[];source_status=[]
    targeted=_targeted_source_urls(query)
    for name,default_url in LIVE_SOURCES:
        url=targeted.get(name,default_url)
        try:
            html=fetch_text(url)
            parsed=parse_live_listings(html,name,url)
            # Some marketplace pages expose cards as rendered links rather than
            # JSON-LD. Use the visible listing representation as a second parser.
            if not parsed and query:
                parsed=parse_visible_listing_links(html,name,url,query)
            if query:
                parsed=[row for row in parsed if _identity_matches_query(row,query)]
            vehicles.extend(parsed)
            source_status.append({"source":name,"status":"live","listings_found":len(parsed),"query_url":url})
        except Exception as exc:
            source_status.append({"source":name,"status":"unavailable","listings_found":0,"error":str(exc)[:160],"query_url":url})
    return vehicles,source_status
