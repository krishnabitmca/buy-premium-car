from pathlib import Path
import pytest

from src.catalog_traversal import advertised_scopes, advertised_total
from src.dealer_inventory import parse_dealer_cards, _price
from src.live_marketplaces import _next_page_url


def test_repeated_first_page_cannot_exhaust_dealer_catalogue():
    from src.catalog_traversal import validate_paged_response
    with pytest.raises(ValueError, match='pagination stalled'):
        validate_paged_response('<span class="page-numbers current">1</span>', 'https://example.com/catalog?paged=2')
    validate_paged_response('<span class="page-numbers current">2</span>', 'https://example.com/catalog?paged=2')


def test_only_reviewed_same_host_advertised_city_links_are_followed():
    source = {'city_catalog_path_pattern': '/used/[a-z0-9-]+/?',
              'city_catalog_title_pattern': 'Second Hand Cars in (.+)'}
    html = '''<a href="/used/pune/" title="Second Hand Cars in Pune">Pune</a>
      <a href="https://other.example/used/delhi/" title="Second Hand Cars in Delhi">Delhi</a>
      <a href="/used/bmw/">BMW</a>
      <a href="/used/mumbai/?tracking=x" title="Second Hand Cars in Mumbai">Mumbai</a>'''
    scopes = advertised_scopes(html, source, 'https://example.com/used/')
    assert [(s['url'], s['label']) for s in scopes] == [('https://example.com/used/pune', 'Pune')]
    assert advertised_total('<h1>108,211 Second Hand Cars in India</h1>') == 108211
    assert advertised_total('<h1>Find used cars</h1>') is None


def test_icon_only_dealer_next_page_is_followed():
    assert _next_page_url('<a class="next page-numbers" href="?paged=2"><i></i></a>',
                          'https://luxuryrideofficial.com/listing-default/') == 'https://luxuryrideofficial.com/listing-default?paged=2'


def test_dealer_pager_uses_public_filter_and_advertised_next():
    import json
    from urllib.parse import urlsplit,parse_qs
    from src.dealer_inventory import fetch_luxuryride_catalog_page
    calls=[]
    def fetch(url):
        calls.append(url)
        return json.dumps({'html':'<span class="page-numbers current">2</span><a class="next page-numbers" href="?paged=3&amp;action=filter_archive_listing_ajax&amp;queryData=page%3D2">Next</a>'})
    html=fetch_luxuryride_catalog_page('https://luxuryrideofficial.com/listing-default?paged=2',fetch)
    params=parse_qs(urlsplit(calls[0]).query)
    assert params['queryData']==['page=2']
    assert params['action']==['filter_archive_listing_ajax']
    assert _next_page_url(html,'https://luxuryrideofficial.com/listing-default?paged=2')=='https://luxuryrideofficial.com/listing-default?paged=3'


def test_real_full_dealer_catalog_cards_and_compound_prices():
    html = Path('tests/fixtures/dealer_luxuryride_catalog.html').read_text(encoding='utf-8')
    rows = parse_dealer_cards(html, 'Luxury Ride', 'https://luxuryrideofficial.com/listing-default/', 'luxuryride_cards')
    assert rows and rows[0]['price_lakh'] == 195
    assert rows[0]['location'] == 'Luxury Ride Karnal'
    assert all(row['images'] and row['source_listing_id'] for row in rows)
    assert all(row['condition_signal'] == 'used' for row in rows)
    assert len(parse_dealer_cards(html + html, 'Luxury Ride', 'https://luxuryrideofficial.com/', 'luxuryride_cards')) == len(rows)
    assert _price('₹1 Crore 95 Lakhs') == 195


def test_background_city_frontier_resumes_without_revisiting_root(monkeypatch):
    from src.source_adapters import BuiltinMarketplaceAdapter, AdapterRequest
    monkeypatch.setenv('CARSCANNER_MAX_PAGES_PER_SOURCE', '1')
    monkeypatch.setattr('src.source_adapters.adapter_execution_allowed', lambda _: True)
    monkeypatch.setattr('src.source_adapters.record_adapter_execution', lambda *a, **kw: None)
    monkeypatch.setattr('src.source_adapters.parse_live_listings', lambda *a: [])
    monkeypatch.setattr('src.source_adapters.parse_visible_listing_links', lambda *a: [])
    pages = {'https://example.com/used/': '<a href="/used/pune/" title="Second Hand Cars in Pune">Pune</a>',
             'https://example.com/used/pune': '<a rel="next" href="?page=2">Next</a>'}
    visited = []
    def fetch(url):
        visited.append(url)
        return pages[url]
    monkeypatch.setattr('src.source_adapters.fetch_text', fetch)
    adapter = BuiltinMarketplaceAdapter({'name': 'Example', 'url': 'https://example.com/used/',
        'city_catalog_path_pattern': '/used/[a-z0-9-]+/?', 'city_catalog_title_pattern': 'Second Hand Cars in (.+)'})
    first = adapter.fetch(AdapterRequest(continuation={}))
    assert first.continuation['pending_urls'] == ['https://example.com/used/pune']
    second = adapter.fetch(AdapterRequest(continuation=first.continuation))
    assert visited == list(pages)
    assert second.continuation['pending_urls'] == ['https://example.com/used/pune?page=2']
    assert second.scan_evidence['scope_count'] == 1
    assert second.scan_evidence['coverage_state'] == 'partial_traversal'

