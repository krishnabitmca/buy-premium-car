from __future__ import annotations
import json,re
from bs4 import BeautifulSoup
from .models import Vehicle
from .normalize import clean_text,extract_fuel,extract_labelled_date,extract_mileage,extract_owner,extract_price_lakh,extract_status,extract_transmission,extract_years,fingerprint,normalize_model

def extract_links(html,base_url,allowed_pattern=None):
    from urllib.parse import urljoin,urlparse
    if not html:return []
    soup=BeautifulSoup(html,"html.parser");host=urlparse(base_url).netloc.lower();rx=re.compile(allowed_pattern,re.I) if allowed_pattern else None
    out=[]
    for a in soup.find_all("a",href=True):
        href=urljoin(base_url,a.get("href"));p=urlparse(href)
        if p.scheme not in {"http","https"} or p.netloc.lower()!=host:continue
        text=clean_text(a.get_text(" ",strip=True));candidate=f"{href} {text}"
        if rx and not rx.search(candidate):continue
        if any(x in href.lower() for x in ["login","contact","privacy","terms","about","sell","insurance","calculator"]):continue
        out.append(href)
    seen=set();result=[]
    from .normalize import canonical_url
    for u in out:
        cu=canonical_url(u)
        if cu not in seen:seen.add(cu);result.append(u)
    return result

def _title_and_body(source_name,url,result):
    html=getattr(result,"html","") or "";markdown=getattr(result,"markdown","") or "";final_url=getattr(result,"redirected_url",None) or url;status=getattr(result,"status_code",None)
    body=clean_text(markdown or BeautifulSoup(html,"html.parser").get_text(" ",strip=True));title=""
    if html:
        soup=BeautifulSoup(html,"html.parser")
        if soup.title:title=clean_text(soup.title.get_text(" ",strip=True))
        h1=soup.find("h1")
        if h1 and clean_text(h1.get_text(" ",strip=True)):title=clean_text(h1.get_text(" ",strip=True))
        for node in soup.find_all("script",type="application/ld+json"):
            try:data=json.loads(node.string or node.get_text())
            except Exception:continue
            for obj in (data if isinstance(data,list) else [data]):
                if isinstance(obj,dict) and obj.get("name"):title=clean_text(str(obj["name"]));break
            if title:break
    return html,body,title,final_url,status

def extract_page(source_name,source_tier,url,result):
    html,body,title,final_url,status=_title_and_body(source_name,url,result)
    if len(body)<80:return None
    sold_signal,sold_reason=extract_status(f"{title} {body}")
    years=extract_years(body);year_m=years[0] if years else None
    for label in ["manufactur(?:ing)? year","year of manufacturing","mfg","built"]:
        m=re.search(label+r"[^0-9]{0,25}(20\d{2})",body,re.I)
        if m:year_m=int(m.group(1));break
    year_r=None
    for label in ["registration year","date of registration","registered"]:
        m=re.search(label+r"[^0-9]{0,25}(20\d{2})",body,re.I)
        if m:year_r=int(m.group(1));break
    manufacture_date=extract_labelled_date(body,["year of manufacturing","manufacturing year","manufactured","mfg","built"])
    registration_date=extract_labelled_date(body,["date of registration","registration year","registered"])
    brand,model,variant=normalize_model(title,body);km=extract_mileage(body);price=extract_price_lakh(body);owners=extract_owner(body);fuel=extract_fuel(body);transmission=extract_transmission(body)
    location=None
    m=re.search(r"(?:location|car available at)\s*[:\-]?\s*([A-Za-z][A-Za-z .,&/-]{2,60})",body,re.I)
    if m:location=clean_text(m.group(1))
    if not brand or not model or (km is None and price is None):return None
    notes=[]
    if sold_reason:notes.append(sold_reason)
    if year_m and year_r and abs(year_m-year_r)>2:notes.append(f"manufacture/registration year gap looks unusual: {year_m} vs {year_r}")
    if not owners:notes.append("owner count not found on page")
    if not km:notes.append("mileage not found on page")
    if not price:notes.append("asking price not found on page")
    return Vehicle(source_name=source_name,source_tier=source_tier,url=url,title=title or url,brand=brand,model=model,variant=variant,year_manufacture=year_m,year_registration=year_r,manufacture_date=manufacture_date,registration_date=registration_date,mileage_km=km,owner_count=owners,price_lakh=price,fuel=fuel,transmission=transmission,location=location,status_text=sold_reason or None,crawled_at=getattr(result,"crawled_at",None) or __import__("datetime").datetime.utcnow().isoformat(),final_url=final_url,http_status=status,live_verified=bool(getattr(result,"success",False) and not sold_signal),sold_signal=sold_signal,data_consistent=not any("gap looks unusual" in x for x in notes),fingerprint=fingerprint(url,title,brand,model,year_m,km,price),verification_notes=notes)