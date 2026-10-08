"""Verified visible inventory cards from premium dealers.

Only card-local evidence is used. Navigation, FAQs and registration status
cannot establish demonstrator condition or a vehicle asking price.
"""
from __future__ import annotations

import re
import json
import urllib.parse
from bs4 import BeautifulSoup

from . import live_marketplaces as lm


def _text(node):
    return node.get_text(" ", strip=True) if node else ""


def _price(text):
    match = re.search(r"(?:₹|INR|Rs\.?)\s*([\d,.]+)\s*(crores?|cr|lakhs?|l|thousand)?\b", text, re.I)
    if not match:
        return None
    amount = float(match[1].replace(",", ""))
    unit = (match[2] or "").lower()
    if unit in {"crore", "crores", "cr"}:
        return amount * 100
    if unit in {"l", "lakh", "lakhs"}:
        # Luxury Ride displays e.g. ₹69 Lakhs 75 thousand.
        extra = re.search(r"([\d,.]+)\s*thousand", text[match.end():], re.I)
        return amount + (float(extra[1].replace(",", "")) / 100 if extra else 0)
    return amount / 100000


def _bbt_state(soup):
    """Read JSON carried by Next's public page stream, never execute scripts.

    Only enrich visible cards by their product ID. The embedded model catalog
    supplies family identity (C200 -> C Class) without a baked-in model map.
    """
    products, models = {}, {}
    for script in soup.select("script"):
        match = re.fullmatch(r"\s*self\.__next_f\.push\((.*)\)\s*;?\s*", script.get_text(), re.S)
        if not match:
            continue
        try:
            stream = json.loads(match[1])
            payload = stream[1] if stream[0] == 1 else ""
            if not isinstance(payload, str) or ":" not in payload:
                continue
            data, _ = json.JSONDecoder().raw_decode(payload.split(":", 1)[1])
        except (ValueError, TypeError, IndexError):
            continue
        for obj in lm._walk(data):
            if obj.get("id") and obj.get("modelname") and obj.get("bid"):
                models[(str(obj["bid"]), str(obj["id"]))] = obj["modelname"]
            if obj.get("id") and isinstance(obj.get("brand"), dict) and "price" in obj:
                products[str(obj["id"])] = obj
    return products, models


def parse_dealer_cards(html, source, base_url, strategy, query=""):
    soup = BeautifulSoup(html, "html.parser")
    selectors = {"bbt_cards": "[data-product-id]", "autobest_cards": ".abe__thmb-car-btmtxt", "luxuryride_cards": ".listing-post", "ninthgear_cards": ".main-car"}
    if strategy not in selectors:
        raise ValueError("Unknown dealer card strategy")
    products, models = _bbt_state(soup) if strategy == "bbt_cards" else ({}, {})
    rows, seen = [], set()
    for node in soup.select(selectors[strategy]):
        card = node if strategy != "autobest_cards" else node.find_parent("a")
        if not card:
            continue
        text = _text(card)
        product = products.get(str(card.get("data-product-id")), {})
        if product.get("isSoldOut") is True or product.get("isBooked") is True or product.get("inStock") is False:
            continue
        if re.search(r"\b(?:sold|reserved|booked|just missed)\b", text, re.I):
            continue
        if strategy == "bbt_cards":
            heading = card.select_one("h6")
            link = card.select_one('a[href*="-detail-page"]')
            title = _text(heading)
            price = _price(_text(link.select_one("p"))) if link else None
            year_text = _text(link.select_one("span")) if link else ""
            specs = card.select("ul li span")
            location = _text(specs[-1]) if len(specs) >= 3 else None
            if location and "unreg" in location.lower():
                location = None
        elif strategy == "autobest_cards":
            link = card
            title_node = card.select_one(".abe_car_lfttxt span")
            title = (title_node.get("title") or _text(title_node)) if title_node else ""
            price = _price(_text(card.select_one(".abe_car_rghttxt p")))
            year_text = _text(card.select_one(".abe_car_rghttxt span"))
            location = None
        elif strategy == "ninthgear_cards":
            link = card.select_one("h3 a")
            title = _text(link)
            price = _price(_text(card.select_one(".posted_by")))
            year_text = _text(card.select_one(".comment"))
            location = None
        else:
            link = card.select_one("h3.title a")
            title = _text(link)
            price = _price(_text(card.select_one(".price")))
            year_text = _text(card.select_one(".date-car"))
            location = _text(card.select_one(".location")) or None
        if not link or not link.get("href") or not title or not price:
            continue
        url = lm._canonical_url(base_url, link["href"])
        if urllib.parse.urlsplit(url).hostname != urllib.parse.urlsplit(base_url).hostname or url in seen:
            continue
        km = re.search(r"([\d,]+(?:\.\d+)?)\s*kms?\b", text, re.I)
        year = re.search(r"\b((?:19|20)\d{2})\b", year_text)
        if not km:
            continue
        # Dealers use several spellings for the same brand; do not copy the
        # requested brand/model onto an unrelated vehicle.
        title = re.sub(r"\bMercedes\s*-?\s*Benz\b", "Mercedes-Benz", title, flags=re.I)
        brand, model = lm._infer_brand_model(title, None, None)
        source_brand = product.get("brand") or {}
        source_model = models.get((str(source_brand.get("id")), str((source_brand.get("model") or {}).get("id"))))
        if source_model and source_brand.get("name"):
            catalog_brand = source_brand["name"]
            # Model labels in this source prefix Mercedes rather than Benz.
            catalog_model = re.sub(r"^" + re.escape(catalog_brand) + r"\s+", "", source_model, flags=re.I).strip()
            if catalog_brand == "Mercedes-Benz":
                catalog_model = re.sub(r"^Mercedes(?:[-\s]+Benz)?\s+", "", catalog_model, flags=re.I).strip()
            family = lm._identity_tokens(catalog_model)
            agrees = lm._model_identity_matches(catalog_model, title)
            if len(family) == 2 and family[1] == "class" and len(family[0]) == 1:
                agrees = agrees or bool(re.search(r"\b" + re.escape(family[0]) + r"\s*\d{3}", title, re.I))
            if len(family) == 2 and family[1] == "series" and family[0].isdigit():
                agrees = agrees or bool(re.search(r"\b(?:M\s*)?" + re.escape(family[0]) + r"\d{2}", title, re.I))
            # The source occasionally assigns a GLS to a GLE catalog row.
            # Preserve the title identity rather than introducing a false match.
            if agrees and lm._model_identity_matches(catalog_brand, brand):
                brand, model = catalog_brand, catalog_model
        images = []
        image_selector = "img.car-image" if strategy == "ninthgear_cards" else "a img, .car_thumb_boxs img"
        for img in card.select(image_selector):
            src = img.get("data-src") or img.get("src")
            if src and not src.startswith("data:") and not re.search(r"(?:icon|logo|dummy|placeholder)", src, re.I):
                images.append(urllib.parse.urljoin(base_url, src))
        images = list(dict.fromkeys(images))
        fuel = re.search(r"\b(Petrol|Diesel|Electric|Hybrid|CNG)\b", text, re.I)
        condition = "demo" if product.get("isDemo") is True or re.search(r"\b(?:demo|demonstrator)\b", text, re.I) else "used"
        row = {"brand": brand, "model": model, "listing_name": title, "variant": title,
               "price_lakh": price, "url": url, "source": source, "images": images,
               "source_listing_id": str(card.get("data-product-id")) if strategy == "bbt_cards" else None,
               "image": images[0] if images else None, "condition_signal": condition,
               "mfg_year": int(year[1]) if year and strategy != "bbt_cards" else None,
               "registration_year": int(year[1]) if year and strategy == "bbt_cards" else None,
               "km": float(km[1].replace(",", "")), "fuel": fuel[1] if fuel else None,
               "location": location if strategy != "bbt_cards" else None, "seller_city": None, "seller_state": None,
               "registration_state": location if strategy == "bbt_cards" else None,
               "live_verified": True, "data_consistent": True,
               "provenance": {"source_url": base_url, "original_url": url, "extraction": strategy,
                              "condition_evidence": "product.isDemo=true" if product.get("isDemo") is True else "visible dealer card"}}
        if not query or lm._identity_matches_query(row, query):
            seen.add(url)
            rows.append(row)
    return rows
