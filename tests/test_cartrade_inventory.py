from pathlib import Path
from src.marketplace_cards import parse_marketplace_cards


def fixture():
    return Path('tests/fixtures/marketplace_cartrade.html').read_text(encoding='utf-8')


def test_real_cartrade_cards_preserve_family_asking_price_and_national_location():
    rows=parse_marketplace_cards(fixture(),'CarTrade','https://www.cartrade.com/second-hand/tata/','cartrade_cards','Tata')
    assert [(r['model'],r['price_lakh'],r['km'],r['seller_city']) for r in rows]==[
        ('Harrier',11.9,54000,'Ahmedabad'),('Nexon',7.5,37000,'Mumbai')]
    assert all(r['images'] and r['source_listing_id'] and r['condition_signal']=='used' for r in rows)
    assert all('/second-hand/' in r['url'] and r['provenance']['extraction']=='cartrade_cards' for r in rows)
    assert parse_marketplace_cards(fixture(),'CarTrade','https://www.cartrade.com/second-hand/tata/','cartrade_cards','Honda')==[]


def test_cartrade_rejects_sold_wrong_host_and_missing_odometer():
    for html in [fixture().replace('54,000','unknown').replace('37,000','unknown'),
                 fixture().replace('href="/second-hand/','href="https://evil.example/second-hand/'),
                 fixture().replace('2021 Tata Harrier','Sold 2021 Tata Harrier').replace('2022 Tata Nexon','Sold 2022 Tata Nexon')]:
        assert parse_marketplace_cards(html,'CarTrade','https://www.cartrade.com/second-hand/tata/','cartrade_cards','Tata')==[]
