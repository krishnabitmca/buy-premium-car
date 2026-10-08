from pathlib import Path
import json
from src.demo_dealers import parse_sundaram, parse_gurudev, fetch_sundaram
from src.source_adapters import AdapterRequest, BuiltinMarketplaceAdapter

BASE = 'https://sundarammotorspoc.com/listings/'
HTML = Path('tests/fixtures/sundaram_cards.html').read_text()
STOCK = Path('tests/fixtures/gurudev_stock.json').read_text()


def test_sundaram_demo_asking_price_not_new_reference_price():
    row = parse_sundaram(HTML, 'Sundaram', BASE)[0]
    assert row['condition_signal'] == 'demo'
    assert row['price_lakh'] == 70
    assert row['km'] == 4500
    assert row['model'] == 'E-Class'
    assert row['location'] == 'Bangalore'
    assert row['images'] and row['url'] != BASE
    assert not parse_sundaram('<h1>Demo Mercedes E-Class ₹70L</h1>', 'Sundaram', BASE)
    assert not parse_sundaram(HTML.replace('listing_is_active', 'listing_is_sold'), 'Sundaram', BASE)
    assert not parse_sundaram(HTML.replace('sale-price', 'unavailable-price'), 'Sundaram', BASE)


def test_sundaram_pagination_is_bounded_and_partial_failures_preserve_stock():
    urls = []
    def fetch(url):
        urls.append(url)
        if '/page/3/' in url:
            raise TimeoutError()
        return HTML
    rows, error = fetch_sundaram(BASE, 'Sundaram', fetch)
    assert rows and error and 'TimeoutError' in error
    assert len(urls) == 8
    assert all(url.startswith(BASE) for url in urls)


def test_gurudev_current_public_api_keeps_unknown_mileage_and_on_road_price():
    rows = parse_gurudev(STOCK, 'Gurudev', 'api')
    assert len(rows) == 1
    row = rows[0]
    assert row['model'] == 'Altroz' and row['price_lakh'] == 8.50959
    assert row['price_basis'] == 'on_road' and row['km'] is None
    assert row['condition_signal'] == 'demo' and not row['images']
    data = json.loads(STOCK)
    data['items'][0]['on_road_price'] = 0
    assert not parse_gurudev(json.dumps(data), 'Gurudev', 'api')
    assert not parse_gurudev('{"items":[]}', 'Gurudev', 'api')


def test_new_adapter_filters_demo_model_and_budget(monkeypatch):
    monkeypatch.setattr('src.source_adapters.fetch_text', lambda _: STOCK)
    monkeypatch.setattr('src.source_adapters.adapter_execution_allowed', lambda _: True)
    monkeypatch.setattr('src.source_adapters.record_adapter_execution', lambda *a, **kw: None)
    adapter = BuiltinMarketplaceAdapter({'name': 'Gurudev', 'url': 'api', 'parser_strategy': 'gurudev_stock'})
    assert len(adapter.fetch(AdapterRequest(query='Tata Altroz', condition='demo')).listings) == 1
    assert not adapter.fetch(AdapterRequest(query='Tata Punch', condition='demo')).listings
    assert not adapter.fetch(AdapterRequest(condition='used')).listings
    assert not adapter.fetch(AdapterRequest(condition='demo', budget_max=8)).listings


def test_supplemental_demo_endpoint_failure_keeps_primary_inventory(monkeypatch):
    fixture = Path('tests/fixtures/dealer_bbt.html').read_text()
    def fetch(url):
        if url == 'https://example.com/demo':
            raise TimeoutError('offline')
        return fixture
    monkeypatch.setattr('src.source_adapters.fetch_text', fetch)
    monkeypatch.setattr('src.source_adapters.adapter_execution_allowed', lambda _: True)
    monkeypatch.setattr('src.source_adapters.record_adapter_execution', lambda *a, **kw: None)
    adapter = BuiltinMarketplaceAdapter({'name': 'BBT', 'url': 'https://www.bigboytoyz.com/', 'parser_strategy': 'bbt_cards', 'endpoints': [{'url': 'https://example.com/demo', 'condition': 'demo'}]})
    assert len(adapter._urls(AdapterRequest(condition='used'))) == 1
    result = adapter.fetch(AdapterRequest(condition='both'))
    assert result.status == 'live' and len(result.listings) == 2 and 'TimeoutError' in result.error
