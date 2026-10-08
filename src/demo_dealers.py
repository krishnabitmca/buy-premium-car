"""Current dealer demo stock; no inferred demos or catalogue prices."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from . import live_marketplaces as lm
from .dealer_inventory import _text, _price


def parse_sundaram(html, source, url):
    rows = []
    for card in BeautifulSoup(html, 'html.parser').select('.listing-list-loop.listing_is_active'):
        title_node = card.select_one('.title a')
        condition = _text(card.select_one('.condition .value')).lower()
        price_node = card.select_one('.sale-price') if condition == 'demo' else card.select_one('.price')
        price = _price(_text(price_node))
        title = _text(title_node)
        if not title_node or not price or condition not in {'demo', 'used'}:
            continue
        href = urljoin(url, title_node.get('href', ''))
        if urlsplit(href).hostname != urlsplit(url).hostname or href.rstrip('/') == url.rstrip('/'):
            continue
        brand, model = lm._infer_brand_model(re.sub(r"\b(?:19|20)\d{2}\b", "", title).strip(), None, None)
        # Source labels E 220d separately; Mercedes numeric variants identify
        # their letter family without confusing GLE/GLS or other brands.
        family = re.search(r'Mercedes[- ]Benz\s+([ACEGS])\s*\d{3}', title, re.I)
        if family:
            model = family[1].upper() + '-Class'
        image = card.select_one('.image img')
        image_url = (image.get('data-src') or image.get('src')) if image else None
        rows.append({'brand': brand, 'model': model, 'listing_name': title, 'variant': title,
                     'price_lakh': price, 'url': href, 'source': source,
                     'condition_signal': condition, 'km': float(card['data-mileage']) if card.get('data-mileage') else None,
                     'registration_year': int(card['data-ca-year']) if card.get('data-ca-year', '').isdigit() else None,
                     'location': _text(card.select_one('.car-location .value')) or None,
                     'fuel': _text(card.select_one('.fuel .value')) or None,
                     'images': [urljoin(url, image_url)] if image_url else [],
                     'live_verified': True, 'data_consistent': True,
                     'provenance': {'source_url': url, 'original_url': href, 'extraction': 'sundaram_cards', 'condition_evidence': condition}})
    return rows


def fetch_sundaram(url, source, fetch):
    first = fetch(url)
    pages = {url}
    # Only enumerate pagination advertised by this inventory, bounded to ten.
    for link in BeautifulSoup(first, 'html.parser').select('a.page-numbers[href]'):
        href = urljoin(url, link['href'])
        match = re.fullmatch(r'/listings/page/(\d+)/', urlsplit(href).path)
        if urlsplit(href).hostname == urlsplit(url).hostname and match:
            pages.update(urljoin(url, f'/listings/page/{i}/') for i in range(2, min(int(match[1]), 10) + 1))
    rows = parse_sundaram(first, source, url)
    errors = []
    def read(page):
        try:
            return parse_sundaram(fetch(page), source, page)
        except Exception as exc:
            errors.append(f'{page}: {type(exc).__name__}')
            return []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(read, sorted(pages - {url})):
            rows.extend(result)
    return rows, '; '.join(errors) or None


def parse_gurudev(body, source, api_url):
    data = json.loads(body)
    if not isinstance(data, dict) or not isinstance(data.get('items'), list):
        raise ValueError('Unexpected Gurudev public stock response')
    rows = []
    page = 'https://gurudevtata.in/demo-cars.html'
    for item in data['items']:
        model, variant = item.get('model'), item.get('variant')
        price = item.get('on_road_price')
        if not model or not variant or not isinstance(price, (int, float)) or price <= 0:
            continue
        rows.append({'brand': 'Tata', 'model': model, 'variant': variant,
                     'listing_name': f'Tata {model} {variant}', 'price_lakh': price / 100000,
                     'price_basis': 'on_road', 'location': 'Chennai', 'source': source, 'url': page,
                     'mfg_year': item.get('year'), 'km': item.get('km') or None,
                     'images': [], 'condition_signal': 'demo', 'live_verified': True, 'data_consistent': True,
                     'provenance': {'source_url': page, 'original_url': page, 'api_url': api_url,
                                    'extraction': 'gurudev_stock', 'condition_evidence': 'public demo-stock API'}})
    return rows
