from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
import urllib.error
import time
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from typing import Any

from .source_intelligence import load_source_registry, plan_sources, normalize_condition

USER_AGENT = "CarScanner/1.0 (+https://carscanner.in)"
TIMEOUT = 5
MAX_BODY_BYTES = 3000000
FETCH_RETRIES = 2
MAX_PARALLEL_SOURCES = 5
RETRYABLE_STATUS = {408,425,429,500,502,503,504}

BRAND_ALIASES = {
    "MG": "MG Motor",
    "Mercedes Benz": "Mercedes-Benz",
    "Mercedes-Benz": "Mercedes-Benz",
    "Mini": "MINI",
    "McLaren": "McLaren",
    "Citroen": "Citroën",
    "Vinfast": "VinFast",
}

class _ImageLinkParser(HTMLParser):
    """Collect image URLs nested inside listing anchors."""
    def __init__(self):
        super().__init__()
        self.rows=[]
        self._href=None
        self._images=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag.lower()=="a":
            self._href=attrs.get("href")
            self._images=[]
        elif tag.lower()=="img" and self._href:
            for key in ("src","data-src","data-lazy-src","data-original"):
                value=attrs.get(key)
                if value and not str(value).startswith("data:"):
                    self._images.append(value)
                    break
    def handle_endtag(self, tag):
        if tag.lower()=="a" and self._href:
            self.rows.append((self._href,list(dict.fromkeys(self._images))))
            self._href=None
            self._images=[]

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
    """Fetch a marketplace page defensively; never parse an error page as inventory."""
    last_error = None
    for attempt in range(FETCH_RETRIES):
        req=urllib.request.Request(url,headers={
            "User-Agent":USER_AGENT,
            "Accept-Language":"en-IN,en;q=0.9",
            "Accept":"text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.1",
        })
        try:
            with urllib.request.urlopen(req,timeout=TIMEOUT) as response:
                status=getattr(response,"status",200)
                if status >= 400:
                    raise urllib.error.HTTPError(url,status,"HTTP error",response.headers,None)
                content_type=(response.headers.get("Content-Type") or "").lower()
                if content_type and not any(x in content_type for x in ("text/html","application/xhtml","application/json","text/plain")):
                    raise ValueError(f"unsupported content type: {content_type[:80]}")
                raw=response.read(MAX_BODY_BYTES+1)
                if len(raw)>MAX_BODY_BYTES:
                    raise ValueError(f"response body exceeds {MAX_BODY_BYTES} bytes")
                text=raw.decode(response.headers.get_content_charset() or "utf-8","ignore")
                if not text.strip():
                    raise ValueError("empty response body")
                return text
        except urllib.error.HTTPError as exc:
            last_error=exc
            if exc.code not in RETRYABLE_STATUS: break
        except (urllib.error.URLError, TimeoutError, socket.timeout, ValueError) as exc:
            last_error=exc
        if attempt < FETCH_RETRIES-1:
            time.sleep(0.25 * (2 ** attempt))
    raise RuntimeError(f"fetch failed for {url}: {last_error}")

def _absolute(base: str, href: str) -> str:
    return urllib.parse.urljoin(base, href)

def _slug(value: str) -> str:
    value=value.lower().strip().replace("&","and")
    value=re.sub(r"[^a-z0-9]+","-",value).strip("-")
    return value

def _canonical_brand(name: str) -> str:
    n=" ".join(name.replace(" Cars","").split()).strip()
    return BRAND_ALIASES.get(n,n)

def _catalog_exclude_paths() -> set[str]:
    configured={x.strip().lower().strip("/") for x in os.getenv("CARSCANNER_CATALOG_EXCLUDE_PATHS","").split(",") if x.strip()}
    if configured:
        return configured
    try:
        for source in load_source_registry():
            metadata=source.get("metadata") or {}
            values=source.get("catalog_exclude_paths") or metadata.get("catalog_exclude_paths") or []
            return {str(x).strip().lower().strip("/") for x in values if str(x).strip()}
    except Exception:
        pass
    return set()


def _brand_path_tokens(selected: dict[str,str]) -> set[str]:
    parsed=urllib.parse.urlparse(selected["url"])
    path=parsed.path.strip("/").lower()
    if path.endswith("-cars"):
        path=path[:-5]
    tokens={_slug(selected["name"]),path}
    tokens.update(_identity_tokens(_canonical_brand(selected["name"])))
    return {t for t in tokens if t}

def _is_current_model_link(selected: dict[str,str], href: str) -> bool:
    """Accept only canonical CarDekho model landing pages, never variants/dealers/offers."""
    parsed=urllib.parse.urlparse(href)
    host=parsed.netloc.lower()
    path=parsed.path.rstrip("/").lower()
    if host and "cardekho.com" not in host:
        return False
    parts=[p for p in path.split("/") if p]
    brand_tokens=_brand_path_tokens(selected)
    # CarDekho places gallery/navigation links alongside model links. They
    # share the same /<brand>/<slug> URL shape, so explicitly reject known
    # non-model endpoints before accepting the generic two-segment shape.
    navigation_slugs = {
        "gallery","images","photos","photo","videos","video","reviews",
        "review","news","offers","offer","dealers","dealer","service",
        "new-cars","used-cars","view-all-models","compare","accessories",
    }
    if parts and (parts[-1] in navigation_slugs or
                  parts[-1].endswith(("-offers","-offer","-dealer","-dealers"))):
        return False
    # Reject common navigation labels even when the source exposes them through
    # a query/hash URL or a path variant that otherwise resembles a model page.
    if any(token in parts for token in {"gallery","images","photos","photo","videos","video","reviews","review","offers","offer","dealers","dealer","service","compare","accessories"}):
        return False
    if len(parts)==2 and parts[0] in brand_tokens:
        return True
    if len(parts)==3 and parts[0]=="carmodels" and parts[1] in brand_tokens:
        return True
    return False

def _clean_model_catalog_name(text: str, brand: str = "") -> str | None:
    """Normalize source labels into canonical customer-facing model names.

    Catalog pages often prefix every model link with the selected brand
    (for example, "BMW X5"). The UI contract is brand + model as separate
    fields, so the model value must not repeat the brand. Historical,
    discontinued, upcoming and navigation labels are rejected here.
    """
    clean=" ".join(str(text or "").split()).strip()
    if not clean:
        return None
    if re.search(r"\bdiscontinued\b",clean,re.I):
        return None
    if re.search(r"\b(?:expected launch|upcoming|estimated)\b",clean,re.I):
        return None
    clean=re.sub(
        r"\s+(?:₹|Rs\.?)\s*[\d.,]+(?:\s*(?:Cr|Lakh|Lakhs))?\s*\*?\s*$",
        "",
        clean,
        flags=re.I,
    ).strip()
    clean=re.sub(r"\s+\*+$", "", clean).strip()
    clean=re.sub(r"\s+(?:estimated|expected)$", "", clean, flags=re.I).strip()

    canonical_brand=_canonical_brand(brand).strip()
    if canonical_brand:
        clean=re.sub(
            rf"^{re.escape(canonical_brand)}(?:\s+|[-:])+",
            "",
            clean,
            flags=re.I,
        ).strip()
        # Handle common source spelling without the hyphen in Mercedes-Benz.
        brand_tokens=_identity_tokens(canonical_brand)
        clean_words=clean.split()
        clean_tokens=_identity_tokens(clean)
        if clean_tokens[:len(brand_tokens)]==brand_tokens and len(clean_tokens)>len(brand_tokens):
            clean=" ".join(clean_words[len(brand_tokens):]).strip()
    return clean or None

def _known_brand_names() -> list[str]:
    names=[]
    seen=set()
    for record in _registry_brand_records()+_configured_brand_records():
        name=str(record.get("name") or "").strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    return names

def _catalog_source_url() -> str:
    configured=os.getenv("CARSCANNER_CATALOG_SOURCE_URL", "").strip()
    if configured:
        return configured
    try:
        for source in load_source_registry():
            metadata=source.get("metadata") or {}
            url=str(source.get("catalog_url") or metadata.get("catalog_url") or "").strip()
            if url:
                return url
    except Exception:
        pass
    return ""

def _configured_brand_records() -> list[dict[str,str]]:
    raw=os.getenv("CARSCANNER_CATALOG_BRANDS_JSON", "").strip()
    if not raw:
        return []
    try:
        values=json.loads(raw)
    except json.JSONDecodeError:
        return []
    result=[]
    for item in values if isinstance(values,list) else []:
        if isinstance(item,str):
            name=item.strip()
            if name:
                result.append({"name":name,"slug":_slug(name),"url":"" ,"catalog_verified":"config"})
        elif isinstance(item,dict) and str(item.get("name") or "").strip():
            name=str(item["name"]).strip()
            result.append({
                "name":name,
                "slug":str(item.get("slug") or _slug(name)),
                "url":str(item.get("url") or ""),
                "catalog_verified":"config",
            })
    return result

def _registry_brand_records() -> list[dict[str,str]]:
    """Build brand identity data from the configured registry.

    PostgreSQL is preferred when enabled; the canonical YAML registry remains
    the deterministic bootstrap/local fallback. Brand identity must not depend
    on a database-only path because parser and catalog behavior must remain
    functional before the control-plane DB is provisioned.
    """
    try:
        from .source_intelligence import load_source_registry
        values=[]
        seen=set()
        for source in load_source_registry():
            for brand in source.get("brands") or []:
                name=str(brand or "").strip()
                if not name or name=="*":
                    continue
                key=_canonical_brand(name).lower()
                if key in seen:
                    continue
                seen.add(key)
                values.append({"name":_canonical_brand(name),"slug":_slug(_canonical_brand(name)),"url":"","catalog_verified":"database"})
        return sorted(values,key=lambda x:x["name"].lower())
    except Exception:
        return []

def live_brands() -> list[dict[str,str]]:
    """Return brands from the database/configured catalog, never a baked-in taxonomy."""
    configured=_configured_brand_records()
    database=_registry_brand_records()
    records=database or configured
    catalog_url=_catalog_source_url()

    # When the control-plane does not yet contain a canonical brand taxonomy,
    # derive it from the configured catalog source itself. This is discovery,
    # not a baked-in brand list.
    if not records and catalog_url:
        try:
            html=fetch_text(catalog_url)
            parser=_LinkParser(); parser.feed(html)
            discovered=[]
            seen=set()
            excluded=_catalog_exclude_paths()
            for label,href in parser.links:
                name=" ".join(str(label or "").replace(" Cars","").split()).strip()
                absolute=_absolute(catalog_url,href)
                path=urllib.parse.urlparse(absolute).path.strip("/").lower()
                if path in excluded:
                    continue
                parts=[p for p in path.split("/") if p]
                if not name or name.lower() in {"view all brands","all brands"}:
                    continue
                is_brand_path=(len(parts)==2 and parts[0]=="cars") or (len(parts)==1 and parts[0].endswith("-cars"))
                if not is_brand_path:
                    continue
                key=_canonical_brand(name).lower()
                if key in seen:
                    continue
                seen.add(key)
                discovered.append({"name":_canonical_brand(name),"slug":_slug(_canonical_brand(name)),
                                   "url":absolute,"catalog_verified":"discovered"})
            return sorted(discovered,key=lambda x:x["name"].lower())
        except Exception:
            return []

    # If a catalog source is configured, enrich the DB/config records with its
    # current canonical links. The source itself is configuration, not code data.
    catalog_url=_catalog_source_url()
    if not catalog_url:
        return records

    try:
        html=fetch_text(catalog_url)
        parser=_LinkParser(); parser.feed(html)
        links=parser.links
        enriched=[]
        for record in records:
            wanted={record["name"],record["name"]+" Cars",_canonical_brand(record["name"])+" Cars"}
            match=None
            for text,href in links:
                if text in wanted:
                    absolute=_absolute(catalog_url,href)
                    if urllib.parse.urlparse(absolute).netloc:
                        match=absolute
                        break
            enriched.append({**record,"url":match or record.get("url") or ""})
        return [x for x in enriched if x.get("url")]
    except Exception:
        return records

def live_models(brand: str) -> list[dict[str,str]]:
    wanted=_canonical_brand(brand).lower()
    selected=None
    try:
        brands=live_brands()
        selected=next((x for x in brands if _canonical_brand(x["name"]).lower()==wanted),None)
    except Exception:
        selected=None
    if not selected:
        return []
    if not selected.get("url"):
        template=os.getenv("CARSCANNER_MODEL_CATALOG_URL_TEMPLATE","").strip()
        if template:
            selected={**selected,"url":template.format(brand=_slug(selected["name"]),name=urllib.parse.quote(selected["name"]),slug=_slug(selected["name"]))}
    if not selected.get("url"):
        return []
    try:
        html=fetch_text(selected["url"])
    except Exception:
        return []
    parser=_LinkParser(); parser.feed(html)
    models=[]; seen_urls=set(); seen_model_keys=set()
    for text,href in parser.links:
        clean=_clean_model_catalog_name(text, selected["name"])
        absolute=_absolute(selected["url"],href)
        if not clean or not _is_current_model_link(selected,absolute):
            continue
        if _canonical_brand(clean).lower()==_canonical_brand(selected["name"]).lower():
            continue
        canonical=absolute.split("#",1)[0].rstrip("/")
        if canonical in seen_urls:
            continue
        model_key=_slug(clean)
        if model_key in seen_model_keys:
            continue
        seen_urls.add(canonical); seen_model_keys.add(model_key)
        models.append({"name":clean,"slug":model_key,"url":canonical,"catalog_verified":"true"})
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

def _image_urls(obj: dict, base_url: str) -> list[str]:
    values=[]
    for key in ("image","images","photo","photos"):
        value=obj.get(key)
        if value:
            values.extend(value if isinstance(value,list) else [value])
    urls=[]
    for value in values:
        if isinstance(value,dict):
            value=value.get("url") or value.get("contentUrl") or value.get("thumbnailUrl")
        if isinstance(value,str) and value.strip() and not value.startswith("data:"):
            urls.append(_canonical_url(base_url,value.strip()))
    return list(dict.fromkeys(urls))[:12]

def _linked_images(html: str, base_url: str) -> dict[str,list[str]]:
    parser=_ImageLinkParser()
    parser.feed(html)
    return {_canonical_url(base_url,href): [_canonical_url(base_url,x) for x in images]
            for href,images in parser.rows if images}

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
    for candidate in sorted(_known_brand_names(),key=len,reverse=True):
        if clean.lower().startswith(candidate.lower()+" "):
            return candidate,clean[len(candidate):].strip()
    parts=clean.split(" ",1)
    return (parts[0] if parts else None),(parts[1] if len(parts)>1 else clean)

def _query_parts(query: str) -> tuple[str|None,str|None]:
    q=" ".join(str(query or "").split()).strip()
    low=q.lower()
    for brand in sorted(_known_brand_names(),key=len,reverse=True):
        if brand.lower() in low:
            model=q[:low.find(brand.lower())]+q[low.find(brand.lower())+len(brand):]
            model=re.sub(r"\\s+"," ",model).strip()
            # The UI may send brand twice when the selected model includes the brand.
            model=re.sub(re.escape(brand), "", model, count=1, flags=re.I).strip()
            return brand, model or None
    return None, q or None

def _targeted_source_urls(query: str, condition: str = "both", registry: list[dict] | None = None) -> dict[str,str]:
    """Resolve source routes from the canonical registry.

    URL templates are source configuration, not application taxonomy. A source
    without a query template falls back to its configured base URL and is still
    eligible for adapter-side identity filtering.
    """
    brand, model = _query_parts(query)
    if not brand:
        return {}

    brand_name = _canonical_brand(brand)
    values = {}
    wanted_condition = normalize_condition(condition)
    if registry is None:
        try:
            registry = load_source_registry()
        except Exception:
            registry = []

    for source in registry:
        name = str(source.get("name") or "").strip()
        if not name or source.get("adapter_status") != "live":
            continue
        conditions = {normalize_condition(x) for x in (source.get("conditions") or [])}
        if wanted_condition in {"used", "demo"} and conditions and wanted_condition not in conditions:
            continue
        brands = {str(x).strip().lower() for x in (source.get("brands") or [])}
        if brands and "all" not in brands and brand_name.lower() not in brands:
            continue

        metadata = source.get("metadata") or {}
        if wanted_condition in {"used", "demo"}:
            condition_template_key = (
                f"{wanted_condition}_query_url_template" if model
                else f"brand_{wanted_condition}_query_url_template"
            )
        else:
            condition_template_key = ""
        template_key = "query_url_template" if model else "brand_query_url_template"
        condition_template = (
            source.get(condition_template_key) or metadata.get(condition_template_key)
            if condition_template_key else None
        )
        template = str(condition_template).strip() if condition_template else ""
        if not template:
            template = str(
                source.get(template_key)
                or metadata.get(template_key)
                or source.get("query_url_template")
                or metadata.get("query_url_template")
                or ""
            ).strip()
        base_url = str(source.get("url") or "").strip()
        if template:
            try:
                values[name] = template.format(
                    brand=urllib.parse.quote(brand_name),
                    brand_slug=_slug(brand_name),
                    model=urllib.parse.quote(model or ""),
                    model_slug=_slug(model or ""),
                    condition=wanted_condition,
                )
            except (KeyError, ValueError):
                values[name] = base_url
        elif base_url:
            values[name] = base_url

    return values

def _canonical_url(base_url: str, href: Any) -> str:
    absolute=_absolute(base_url,str(href or "")).split("#",1)[0]
    p=urllib.parse.urlsplit(absolute)
    if not p.scheme or not p.netloc:
        return absolute
    tracking_prefixes=("utm_","gclid","fbclid","ref","referrer","source")
    query=[]
    for key,value in urllib.parse.parse_qsl(p.query,keep_blank_values=True):
        if key.lower().startswith(tracking_prefixes):
            continue
        query.append((key,value))
    return urllib.parse.urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path.rstrip("/") or "/",urllib.parse.urlencode(query),""))

def _listing_identity_from_text(text: str, href: str) -> tuple[str|None,str|None]:
    blob=f"{text} {urllib.parse.urlsplit(href).path.replace('-',' ')}"
    brand=None
    for candidate in sorted(_known_brand_names(),key=len,reverse=True):
        if re.search(r"\b"+re.escape(candidate)+r"\b",blob,re.I):
            brand=_canonical_brand(candidate); break
    if not brand:
        return None,None
    tokens=_identity_tokens(blob)
    brand_tokens=_identity_tokens(brand)
    remainder=[]
    i=0
    while i < len(tokens):
        if tokens[i:i+len(brand_tokens)]==brand_tokens:
            i+=len(brand_tokens); continue
        remainder.append(tokens[i]); i+=1
    return brand, " ".join(remainder[:5]) if remainder else None

def parse_visible_listing_links(html: str, source: str, base_url: str, query: str="") -> list[dict]:
    parser=_LinkParser()
    parser.feed(html)
    requested_brand,requested_model=_query_parts(query)
    linked_images=_linked_images(html, base_url)
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
        location=parts[2].strip() if len(parts)>2 else None
        if location:
            location=re.sub(r"\s*(?:₹|Rs\.?)[ ]*[\d,.]+[ ]*(?:Lakh|Crore)\s*$","",location,flags=re.I).strip()
        transmission=None
        tm=re.search(r"\b(Automatic|Manual|Clutchless Manual)\b",clean,re.I)
        if tm: transmission=tm.group(1)
        variant=clean[year_match.end():km_match.start()].strip(" -|•") or clean
        listing_brand,listing_model=_listing_identity_from_text(clean,_absolute(base_url,href))
        if not listing_brand:
            continue
        if requested_model and _model_identity_matches(requested_model, clean):
            display_model=requested_model
        else:
            display_model=listing_model or _infer_brand_model(variant,listing_brand,None)[1]
        rows.append({
            "brand":listing_brand,
            "model":display_model,
            "listing_name":clean,
            "variant":variant,
            "price_lakh":price_lakh,
            "url":_canonical_url(base_url,href),
            "images": linked_images.get(_canonical_url(base_url,href), []),
            "image": (linked_images.get(_canonical_url(base_url,href), []) or [None])[0],
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
            "provenance":{"source":source,"source_url":base_url,"original_url":_canonical_url(base_url,href),"extraction":"visible_link","raw_listing":clean},
        })
    seen=set();out=[]
    for row in rows:
        if query and not _identity_matches_query(row,query):
            continue
        key=(_canonical_url(base_url,row["url"]),row["price_lakh"],row["model"],row["condition_signal"])
        if key in seen: continue
        seen.add(key);out.append(row)
    return out
class _NextPageParser(HTMLParser):
    """Extract an explicitly advertised next-results link without guessing page parameters."""
    def __init__(self):
        super().__init__()
        self.next_href = None

    def handle_starttag(self, tag, attrs):
        if self.next_href or tag.lower() not in {"a", "link"}:
            return
        attrs = {str(k).lower(): str(v or "") for k, v in attrs}
        rel = set(str(attrs.get("rel") or "").lower().split())
        label = " ".join(v for v in (attrs.get("aria-label"), attrs.get("title"), attrs.get("data-testid")) if v).lower()
        if "next" in rel or re.search(r"\\bnext\\b", label):
            href = attrs.get("href")
            if href:
                self.next_href = href


def _next_page_url(html: str, base_url: str) -> str | None:
    """Find an explicitly advertised next-results URL and canonicalize it."""
    parser = _NextPageParser()
    parser.feed(html)
    if parser.next_href:
        url = _canonical_url(base_url, parser.next_href)
        if url != _canonical_url(base_url, base_url):
            return url

    # Compatibility fallback for malformed markup that the HTML parser cannot
    # interpret cleanly. Still require an explicit rel/aria/title next marker.
    patterns = [
        r'<a[^>]+rel=["\\\'][^"\\\']*\\bnext\\b[^"\\\']*["\\\'][^>]+href=["\\\']([^"\\\']+)',
        r'<a[^>]+href=["\\\']([^"\\\']+)["\\\'][^>]+[^>]*(?:aria-label|title)=["\\\'][^"\\\']*\\bnext\\b',
        r'<link[^>]+rel=["\\\'][^"\\\']*\\bnext\\b[^"\\\']*["\\\'][^>]+href=["\\\']([^"\\\']+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.I | re.S)
        if match:
            url = _canonical_url(base_url, match.group(1))
            if url != _canonical_url(base_url, base_url):
                return url
    return None


def _crawl_paginated_source(url: str, source: str, query: str, condition: str, max_pages: int = 20) -> tuple[list[dict], list[str]]:
    """Collect a bounded sequence of canonical result pages from one source."""
    rows: list[dict] = []
    pages: list[str] = []
    seen_urls: set[str] = set()
    current = _canonical_url(url, url)
    for _ in range(max(1, max_pages)):
        if not current or current in seen_urls:
            break
        seen_urls.add(current)
        html = fetch_text(current)
        parsed = parse_live_listings(html, source, current)
        # Always use visible cards when structured data is absent, including an
        # unscoped All Brands + All Models request.
        if not parsed:
            parsed = parse_visible_listing_links(html, source, current, query)
        rows.extend(parsed)
        pages.append(current)
        nxt = _next_page_url(html, current)
        if not nxt or nxt in seen_urls:
            break
        current = nxt
    return rows, pages

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
            image_urls=_image_urls(obj, base_url)
            brand,model=_infer_brand_model(str(name),obj.get("brand"),obj.get("model"))
            seller_city,seller_state,location_raw=_infer_location(obj)
            location=seller_city or seller_state
            row={
                "brand":brand,
                "model":model,
                "listing_name":str(name),
                "variant":obj.get("vehicleConfiguration") or obj.get("vehicleVariant") or obj.get("name") or "",
                "price_lakh":price_lakh,
                "url":_canonical_url(base_url,url),
                "images":image_urls,
                "image":image_urls[0] if image_urls else None,
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
                "provenance":{"source":source,"source_url":base_url,"original_url":_canonical_url(base_url,url),"extraction":"json_ld","raw_listing":str(name)},
            }
            if price_text and price_lakh is None:
                continue
            rows.append(row)
    seen=set();out=[]
    for row in rows:
        key=(_canonical_url(base_url,row.get("url")),row.get("price_lakh"),row.get("model"),row.get("condition_signal"))
        if key in seen: continue
        seen.add(key);out.append(row)
    return out

def _live_source_entries() -> list[dict]:
    """Return only registry sources whose adapters are verified for live search."""
    return [s for s in load_source_registry() if s.get("adapter_status") == "live"]


def live_inventory(
    query: str = "",
    condition: str = "both",
    budget_min: float | None = None,
    budget_max: float | None = None,
    destination: str | None = None,
) -> tuple[list[dict],list[dict]]:
    """Search selected live sources concurrently; destination never restricts inventory."""
    brand,model=_query_parts(query)
    registry=_live_source_entries()
    plan=plan_sources(
        brand=brand,model=model,condition=condition,budget_min=budget_min,
        budget_max=budget_max,destination=destination,registry=registry,live_only=True,
    )
    # Execute only the sources selected by the intent planner. The planner
    # is the source-of-truth for applicability; executing every live adapter
    # would turn future source expansion into unnecessary customer-path
    # crawling and could query sources that do not support the requested
    # brand/condition/segment.
    by_name={str(s.get("name")):s for s in registry}
    selected_registry=[
        by_name[str(planned["name"])]
        for planned in plan
        if str(planned.get("name") or "") in by_name
    ]

    # Source-isolated adapter execution. Each verified source owns its
    # acquisition/parser boundary; one source failure is converted to a status
    # record and cannot fail the aggregate search.
    from .source_adapters import AdapterRequest, execute_adapters

    return execute_adapters(
        AdapterRequest(
            query=query,
            condition=condition,
            budget_min=budget_min,
            budget_max=budget_max,
            destination=destination,
        ),
        selected_registry,
        max_workers=MAX_PARALLEL_SOURCES,
    )
