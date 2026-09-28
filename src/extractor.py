from __future__ import annotations
import json,re
from urllib.parse import urljoin,urlparse
from bs4 import BeautifulSoup
from .models import Vehicle
from .normalize import clean_text,extract_fuel,extract_labelled_date,extract_mileage,extract_owner,extract_price_lakh,extract_status,extract_transmission,extract_years,fingerprint,normalize_model

def extract_image_urls(html,base_url,limit=8):
    if not html:return []
    soup=BeautifulSoup(html,"html.parser");candidates=[];seen=set()
    def add(raw,score=0):
        if not raw or str(raw).startswith("data:"):return
        u=urljoin(base_url,str(raw).strip());p=urlparse(u)
        if p.scheme not in {"http","https"}:return
        low=u.lower()
        if any(x in low for x in ("logo","icon","avatar","favicon","placeholder","spinner","loader","youtube","playstore","apple-store")):return
        if any(x in low for x in (".jpg",".jpeg",".png",".webp",".avif")):score+=2
        key=u.split("#",1)[0]
        if key in seen:return
        seen.add(key);candidates.append((score,key))
    for tag in soup.find_all("meta",attrs={"property":"og:image"}):add(tag.get("content"),10)
    for tag in soup.find_all("meta",attrs={"name":"twitter:image"}):add(tag.get("content"),9)
    for node in soup.find_all("script",type="application/ld+json"):
        try:data=json.loads(node.string or node.get_text())
        except Exception:continue
        for obj in (data if isinstance(data,list) else [data]):
            if not isinstance(obj,dict):continue
            imgs=obj.get("image")
            if isinstance(imgs,str):add(imgs,9)
            elif isinstance(imgs,list):
                for img in imgs:
                    if isinstance(img,str):add(img,9)
                    elif isinstance(img,dict):add(img.get("url") or img.get("contentUrl"),9)
    for img in soup.find_all("img"):
        attrs=" ".join(str(img.get(k) or "") for k in ("alt","class","id","data-testid","aria-label")).lower();score=4
        if any(k in attrs for k in ("car","vehicle","gallery","photo","stock","listing")):score+=5
        if any(k in attrs for k in ("logo","icon","avatar","dealer")):score-=7
        for k in ("width","height"):
            try:
                if img.get(k) and int(str(img.get(k)))<160:score-=4
            except Exception:pass
        raw=img.get("data-src") or img.get("data-lazy-src") or img.get("data-original") or img.get("src")
        if raw:add(raw,score)
        srcset=img.get("data-srcset") or img.get("srcset")
        if srcset:add(srcset.split(",")[-1].strip().split(" ")[0],score-1)
    candidates.sort(key=lambda x:x[0],reverse=True)
    return [u for score,u in candidates if score>0][:limit]

def extract_links(html,base_url,allowed_pattern=None):
    if not html:return []
    soup=BeautifulSoup(html,"html.parser");host=urlparse(base_url).netloc.lower();rx=re.compile(allowed_pattern,re.I) if allowed_pattern else None;out=[]
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
    html=getattr(result,"html","") or "";markdown=getattr(result,"markdown","") or "";final_url=getattr(result,"redirected_url",None) or url;status=getattr(result,"status_code",None);body=clean_text(markdown or BeautifulSoup(html,"html.parser").get_text(" ",strip=True));title=""
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
    sold_signal,sold_reason=extract_status(f"{title} {body}");years=extract_years(body);year_m=years[0] if years else None
    for label in ["manufactur(?:ing)? year","year of manufacturing","mfg","built"]:
        m=re.search(label+r"[^0-9]{0,25}(20\d{2})",body,re.I)
        if m:year_m=int(m.group(1));break
    year_r=None
    for label in ["registration year","date of registration","registered"]:
        m=re.search(label+r"[^0-9]{0,25}(20\d{2})",body,re.I)
        if m:year_r=int(m.group(1));break
    manufacture_date=extract_labelled_date(body,["year of manufacturing","manufacturing year","manufactured","mfg","built"]);registration_date=extract_labelled_date(body,["date of registration","registration year","registered"])
    brand,model,variant=normalize_model(title,body);km=extract_mileage(body);price=extract_price_lakh(body);owners=extract_owner(body);fuel=extract_fuel(body);transmission=extract_transmission(body);location=None
    m=re.search(r"(?:location|car available at)\s*[:\-]?\s*([A-Za-z][A-Za-z .,&/-]{2,60})",body,re.I)
    if m:location=clean_text(m.group(1))
    if not brand or not model or (km is None and price is None):return None
    notes=[]
    if sold_reason:notes.append(sold_reason)
    if year_m and year_r and abs(year_m-year_r)>2:notes.append(f"manufacture/registration year gap looks unusual: {year_m} vs {year_r}")
    if not owners:notes.append("owner count not found on page")
    if not km:notes.append("mileage not found on page")
    if not price:notes.append("asking price not found on page")
    images=extract_image_urls(html,final_url)
    if not images:notes.append("listing photos not captured from page")
    return Vehicle(source_name=source_name,source_tier=source_tier,url=url,title=title or url,brand=brand,model=model,variant=variant,year_manufacture=year_m,year_registration=year_r,manufacture_date=manufacture_date,registration_date=registration_date,mileage_km=km,owner_count=owners,price_lakh=price,fuel=fuel,transmission=transmission,location=location,status_text=sold_reason or None,crawled_at=getattr(result,"crawled_at",None) or __import__("datetime").datetime.utcnow().isoformat(),final_url=final_url,http_status=status,live_verified=bool(getattr(result,"success",False) and not sold_signal),sold_signal=sold_signal,data_consistent=not any("gap looks unusual" in x for x in notes),fingerprint=fingerprint(url,title,brand,model,year_m,km,price),verification_notes=notes,image_urls=images)
