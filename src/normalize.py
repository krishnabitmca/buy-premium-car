from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit, urlunsplit

from .car_catalog import BRAND_ALIASES, CAR_MAKES, MODEL_STOP_WORDS

# Backward-compatible export for existing callers.
BRANDS = CAR_MAKES

def canonical_url(url: str) -> str:
    p=urlsplit(url)
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path.rstrip("/"),"",""))

def clean_text(s: str) -> str:
    return re.sub(r"\s+"," ",s or "").strip()

def normalize_brand(text: str):
    low=(text or "").lower()
    for alias, canonical in sorted(BRAND_ALIASES, key=lambda x: len(x[0]), reverse=True):
        if re.search(r"(?<![a-z0-9])"+re.escape(alias)+r"(?![a-z0-9])", low):
            return canonical
    return None

def extract_years(text: str):
    years=[int(y) for y in re.findall(r"(?<!\d)(20\d{2})(?!\d)",text or "")]
    return sorted(set(y for y in years if 2015<=y<=2030))

def _int_clean(value: str)->int: return int(re.sub(r"[^0-9]","",value))

def extract_mileage(text: str):
    if not text: return None
    patterns=[
        r"(\d{1,3}(?:,\d{3})+|\d{3,6})\s*(?:km|kms|kilomet(?:er|res))\b",
        r"(?:mileage|odometer|digital odometer)\D{0,20}(\d{1,3}(?:,\d{3})+|\d{3,6})\b",
    ]
    for pattern in patterns:
        m=re.search(pattern,text,re.I)
        if m:
            value=_int_clean(m.group(1))
            if 500<=value<=500_000: return value
    return None

def _rupee_to_lakh(raw: str):
    value=float(re.sub(r"[^0-9.]","",raw).replace(",",""))
    if value>=200_000: value/=100_000
    return value if 2<=value<=200 else None

def extract_price_lakh(text: str):
    if not text: return None
    candidates=[]
    for m in re.finditer(r"(?:₹|rs\.?|inr\s*)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:lakh|lac|lacs|l)?\b",text,re.I):
        val=float(m.group(1))
        if 2<=val<=200:
            window=text[max(0,m.start()-35):m.end()+35].lower()
            if "reservation" not in window and "10% of" not in window and "emi" not in window: candidates.append((val,m.start()))
    for m in re.finditer(r"([0-9]+(?:\.[0-9]+)?)\s*(?:lakh|lac|lacs)\b",text,re.I):
        val=float(m.group(1)); window=text[max(0,m.start()-35):m.end()+35].lower()
        if 2<=val<=200 and "reservation" not in window and "emi" not in window: candidates.append((val,m.start()))
    for m in re.finditer(r"10%\s*of\s*₹\s*([0-9][0-9,]{5,})\b",text,re.I):
        val=_rupee_to_lakh(m.group(1))
        if val is not None: candidates.append((val,m.start()))
    for m in re.finditer(r"₹\s*([0-9][0-9,]{5,})\b",text):
        window=text[max(0,m.start()-45):m.end()+45].lower()
        if "reservation amount" in window or "emi" in window: continue
        val=_rupee_to_lakh(m.group(1))
        if val is not None: candidates.append((val,m.start()))
    if not candidates: return None
    scored=[]
    for val,pos in candidates:
        window=text[max(0,pos-45):pos+45].lower()
        score=sum(3 for k in ("price","asking","offer","selling","sale") if k in window)
        scored.append((score,-abs(val-35),val))
    scored.sort(reverse=True); return scored[0][2]

def extract_owner(text: str):
    if not text: return None
    patterns=[
        r"\b(\d+)(?:st|nd|rd|th)?\s*(?:owner|owners|ownership)\b",
        r"(?:no\.?\s*of\s*owners|number\s*of\s*owners)\D{0,12}(first|second|third|fourth|\d+)",
        r"\b(first|second|third|fourth)\s*(?:owner|owners)\b",
        r"(?:owner|ownership)\D{0,12}(\d+)\b",
    ]
    words={"first":1,"second":2,"third":3,"fourth":4}
    for pattern in patterns:
        m=re.search(pattern,text,re.I)
        if m:
            token=m.group(1).lower(); return words.get(token,int(token) if token.isdigit() else None)
    return None

def extract_fuel(text: str):
    low=(text or "").lower()
    for fuel in ["diesel","petrol","electric","hybrid"]:
        if fuel in low: return fuel
    return None

def extract_transmission(text: str):
    low=(text or "").lower()
    for tr in ["automatic","dct","dsg","9g-tronic","8-speed","7-speed","manual"]:
        if tr in low: return tr
    return None

def extract_status(text: str):
    low=(text or "").lower()
    sold=any(k in low for k in ["sold out","already sold","vehicle sold","no longer available","not available","booked","soldout"])
    return sold,("sold/unavailable marker detected" if sold else "")

def extract_labelled_date(text: str, labels: list[str]):
    if not text: return None
    months="jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    mmap={'jan':1,'january':1,'feb':2,'february':2,'mar':3,'march':3,'apr':4,'april':4,'may':5,'jun':6,'june':6,'jul':7,'july':7,'aug':8,'august':8,'sep':9,'sept':9,'september':9,'oct':10,'october':10,'nov':11,'november':11,'dec':12,'december':12}
    for label in labels:
        m=re.search(label+rf"[^0-9A-Za-z]{{0,30}}({months})[^0-9]{{0,8}}(20\d{{2}})|"+label+rf"[^0-9A-Za-z]{{0,30}}(20\d{{2}})[^0-9A-Za-z]{{0,8}}({months})",text,re.I)
        if m:
            mon=(m.group(1) or m.group(4)).lower(); year=int(m.group(2) or m.group(3))
            for k,v in mmap.items():
                if mon.startswith(k): return f"{year:04d}-{v:02d}"
        m=re.search(label+r"[^0-9]{0,20}(20\d{2})",text,re.I)
        if m: return m.group(1)
    return None

def _fallback_model(title: str, brand: str):
    if not title or not brand:return None
    value=re.sub(r"\b20\d{2}\b|\b\d{1,2}[,.]?\d{3,6}\s*km?s?\b", " ", title, flags=re.I)
    value=re.sub(re.escape(brand), " ", value, flags=re.I)
    value=re.sub(r"[|:/,·()\[\],]+", " ", value)
    tokens=[t.strip(".-") for t in clean_text(value).split() if t.strip(".-")]
    candidates=[]
    for token in tokens:
        low=token.lower()
        if low in MODEL_STOP_WORDS:break
        if re.fullmatch(r"(?:rs|inr|₹)?\d+(?:\.\d+)?[lL]?", token, re.I):continue
        if re.search(r"[A-Za-z]", token) or re.search(r"\d", token):
            candidates.append(token)
        if len(candidates)>=3:break
    return " ".join(candidates) if candidates else None

def normalize_model(title: str, body: str):
    s=clean_text(f"{title} {body}"); brand=normalize_brand(s)
    if not brand: return None,None,None
    low=s.lower()
    known_models=[
        "c-class","c 220d","c220d","gla","glc","a-class","a 200","e-class","e 200",
        "x1","x3","x5","2 series","3 series","5 series","q3","q5","a4","a6",
        "xc40","xc60","s60","ex40","ex30","countryman","q8","evoque","f-pace",
        "discovery sport","es 300h","nx","macan","cayenne","compass"
    ]
    model=next((m for m in known_models if re.search(r"(?<![a-z0-9])"+re.escape(m)+r"(?![a-z0-9])",low)),None)
    if model: model=model.upper() if model in {"x1","x3","x5","q3","q5","q8","a4","a6","nx"} else model.title()
    if not model:model=_fallback_model(title,brand)
    variant=None
    m=re.search(r"\b(progressive|avantgarde(?: edition)?|amg line|m sport|premium plus|technology|ultimate|inscription|jcw|quattro|4matic|shadow edition|prime|vxi|zxi|sxi|sx\(o\)|sportz|asta|alpha|delta|gtx?|ax[357])\b",s,re.I)
    if m: variant=m.group(1)
    return brand,model,variant

def fingerprint(url,title,brand,model,year,km,price):
    if brand and model and year and km: basis=f"{brand}|{model}|{year}|{round(km/500)*500}"
    else: basis=canonical_url(url)
    return hashlib.sha256(basis.lower().encode()).hexdigest()[:24]
