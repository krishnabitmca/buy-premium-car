"""Public OEM inventory acquisition; session state never leaves the adapter."""
from __future__ import annotations

import http.cookiejar
import json
import re
import urllib.parse
import urllib.request
import urllib.error
from html.parser import HTMLParser

from . import live_marketplaces as lm


class MercedesCards(HTMLParser):
    VOID = {"img", "input", "br", "hr", "meta", "link", "source", "wbr", "area", "base", "embed", "param", "track", "col"}
    FIELDS = {"main-heading": "title", "mb-certified": "condition", "car-price": "price", "car-spec": "specs"}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.card = None
        self.cards = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article":
            self.card = {"title": [], "condition": [], "price": [], "specs": [], "images": [], "url": None}
        field = next((self.FIELDS[c] for c in str(attrs.get("class") or "").split() if c in self.FIELDS), None)
        if self.card is not None:
            if tag == "a" and "/buy-used-cars/" in str(attrs.get("href") or ""):
                self.card["url"] = self.card["url"] or attrs["href"]
            if tag == "img":
                image = attrs.get("data-original") or attrs.get("data-src") or attrs.get("src")
                if image and not image.startswith("data:"):
                    self.card["images"].append(image)
        if tag not in self.VOID:
            self.stack.append((tag, field))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_data(self, value):
        if self.card is None or not value.strip():
            return
        field = next((field for _, field in reversed(self.stack) if field), None)
        if field:
            self.card[field].append(" ".join(value.split()))

    def handle_endtag(self, tag):
        if tag == "article" and self.card is not None:
            self.cards.append(self.card)
            self.card = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def parse_mercedes_cards(html, source, base_url, query=""):
    parser = MercedesCards()
    parser.feed(html)
    rows = []
    seen = set()
    for card in parser.cards:
        title = " ".join(card["title"])
        price = re.search(r"₹\s*([0-9][0-9,]*(?:\.[0-9]+)?)", " ".join(card["price"]))
        specs = card["specs"]
        km = next((re.search(r"([\d,]+)\s*km\b", s, re.I) for s in specs if re.search(r"([\d,]+)\s*km\b", s, re.I)), None)
        year = next((int(s) for s in specs if re.fullmatch(r"(?:19|20)\d{2}", s)), None)
        if not (title and price and card["url"] and year and km):
            continue
        url = urllib.parse.urljoin(base_url, card["url"])
        if url in seen:
            continue
        seen.add(url)
        model_slug = urllib.parse.urlparse(url).path.split("/")[-2]
        model = "-".join(p.capitalize() for p in model_slug.split("-"))
        # Prefer the displayed model spelling when it agrees with the URL.
        words = title.split()
        for count in range(1, len(words) + 1):
            candidate = " ".join(words[:count])
            if lm._identity_tokens(candidate) == lm._identity_tokens(model_slug):
                model = candidate
                break
        images = list(dict.fromkeys(urllib.parse.urljoin(base_url, x) for x in card["images"]))
        row = {"brand": "Mercedes-Benz", "model": model, "listing_name": title, "variant": title,
               "price_lakh": float(price.group(1).replace(",", "")) / 100000,
               "url": url, "source": source, "images": images, "image": images[0] if images else None,
               "condition_signal": lm._infer_condition({"condition": " ".join(card["condition"])}),
               "mfg_year": year, "km": float(km.group(1).replace(",", "")),
               "fuel": specs[1] if len(specs) >= 2 else None,
               "location": specs[-1], "seller_city": specs[-1], "seller_state": None,
               "live_verified": True, "data_consistent": True,
               "provenance": {"source_url": base_url, "original_url": url,
                              "extraction": "mercedes_inventory_article", "condition_evidence": " ".join(card["condition"])}}
        if not query or lm._identity_matches_query(row, query):
            rows.append(row)
    return rows


def fetch_mercedes_inventory(url, query, condition, source):
    """Perform the same read-only inventory request as the public showroom UI."""
    origin = urllib.parse.urlsplit(url)
    if origin.scheme != "https" or origin.hostname != "www.mercedes-benzusedcar.in":
        raise ValueError("Mercedes adapter requires the verified OEM host")
    base = f"https://{origin.netloc}"
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    headers = {"User-Agent": lm.USER_AGENT, "Referer": url, "X-Requested-With": "XMLHttpRequest"}

    def read(request):
        for attempt in range(lm.FETCH_RETRIES):
            try:
                with opener.open(request, timeout=lm.TIMEOUT) as response:
                    raw = response.read(lm.MAX_BODY_BYTES + 1)
                    if len(raw) > lm.MAX_BODY_BYTES:
                        raise ValueError("OEM inventory response exceeds body limit")
                    return raw.decode("utf-8", "replace")
            except urllib.error.HTTPError as exc:
                if exc.code not in lm.RETRYABLE_STATUS or attempt + 1 == lm.FETCH_RETRIES:
                    raise RuntimeError(f"OEM inventory HTTP {exc.code}") from None
            except (urllib.error.URLError, TimeoutError):
                if attempt + 1 == lm.FETCH_RETRIES:
                    raise RuntimeError("OEM inventory transport unavailable") from None

    tokens = json.loads(read(urllib.request.Request(base + "/?action=get_tokens&ajax_type=json", headers=headers))).get("details") or {}
    fields = {key: tokens[key] for key in ("security_token1", "security_token2", "security_token2_rand")}
    fields.update(action="get_inventory", ajax_type="json", ctype={"demo": "demonstrator", "used": "pre-owned"}.get(condition, "all"))
    _, model = lm._query_parts(query)
    if model:
        fields["model"] = model.replace("-", " ")
    html = read(urllib.request.Request(url, data=urllib.parse.urlencode(fields).encode(), headers=headers))
    return parse_mercedes_cards(html, source, url, query)
