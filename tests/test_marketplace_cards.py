from src.marketplace_cards import parse_marketplace_cards
from src.source_adapters import BuiltinMarketplaceAdapter,AdapterRequest


def test_cardekho_card_excludes_navigation_and_keeps_vehicle_evidence():
    html='''<a href="/used-bmw+cars">BMW ₹5 Lakh</a>
    <div class="NewUcExCard"><h3><a href="/used-car-details/used-bmw-x1-a.htm" title="2023 BMW X1 sDrive18i">BMW X1 <span>2023</span></a></h3>
    <p>₹38L</p><p>34,000 kms Automatic Petrol</p></div>'''
    rows=parse_marketplace_cards(html,'CarDekho','https://www.cardekho.com/used-bmw+cars','cardekho_cards')
    assert len(rows)==1
    assert (rows[0]['model'],rows[0]['price_lakh'],rows[0]['km'],rows[0]['mfg_year'])==('X1',38,34000,2023)
    assert rows[0]['condition_signal']=='used'
    assert rows[0]['location'] is None


def test_cars24_uses_final_asking_price_not_emi_or_previous_price():
    html='''<a href="/buy-used-bmw-x1-2020-cars-pune-10688396160/">
    <img alt="background" src="frame.png"><img alt="2020 BMW X1 - SUV" src="car.png">
    <p>58,334 km Petrol Auto</p><p>EMI ₹34,899/m</p><p>₹20.55L ₹20.38 lakh</p>
    <div class="styles_hubAddress__hash">Tathawade, Pune</div></a>'''
    row=parse_marketplace_cards(html,'Cars24','https://www.cars24.com/buy-used-bmw-cars/','cars24_cards')[0]
    assert row['price_lakh']==20.38
    assert row['images']==['https://www.cars24.com/buy-used-bmw-cars/car.png']
    assert row['location']=='Tathawade, Pune'
    assert parse_marketplace_cards(html,'Cars24','https://www.cars24.com/','cars24_cards','Mercedes-Benz')==[]


def test_carwale_rejects_category_and_external_links():
    html='''<div class="UsedSearchCard__cardFrame"><a href="/used/mumbai/bmw-x1/judvnm3m/"><h3>2022 BMW X1 sDrive20d xLine</h3><span>27,000 km | Diesel | Mumbai</span></a><p>₹29.5 Lakh</p></div>
    <a href="/used/bmw-x1/"><h3>2022 BMW X1</h3>27,000 km ₹10 Lakh</a>
    <div class="cardFrame"><a href="https://unrelated.example/used/mumbai/bmw-x1/12345678/"><h3>2022 BMW X1</h3>27,000 km</a><p>₹1 Lakh</p></div>'''
    rows=parse_marketplace_cards(html,'CarWale','https://www.carwale.com/used/bmw/','carwale_cards')
    assert len(rows)==1
    assert rows[0]['price_lakh']==29.5
    assert rows[0]['location']=='Mumbai'


def test_standard_carwale_layout_does_not_take_emi_as_asking_price():
    html='<div class="UsedSearchCard__searchCardClasses"><a href="/used/delhi/bmw-x5/ts0ov70t/"><h3>2025 BMW X5 xDrive40i</h3><span>18,000 km | Petrol | Delhi</span></a><p>₹92.75 Lakh EMI at ₹1.67 L</p></div>'
    row=parse_marketplace_cards(html,'CarWale','https://www.carwale.com/used/bmw/','carwale_cards')[0]
    assert row['price_lakh']==92.75 and row['location']=='Delhi'


def test_cars24_mercedes_spelling_matches_canonical_brand():
    html='<a href="/buy-used-mercedes-benz-c-class-2020-cars-delhi-12345678/"><img alt="2020 Mercedes Benz C Class - Sedan" src="car.jpg">20,000 km ₹30 lakh</a>'
    row=parse_marketplace_cards(html,'Cars24','https://www.cars24.com/buy-used-mercedes-benz-cars/','cars24_cards','Mercedes-Benz')[0]
    assert row['brand']=='Mercedes-Benz' and row['model']=='C Class'


def test_inventory_pagination_is_bounded_and_stays_on_source(monkeypatch):
    seen=[]
    def fetch(url):
        seen.append(url)
        return '<a rel="next" href="/page-2">Next</a>' if url.endswith('/stock') else '<a rel="next" href="https://other.example/page-3">Next</a>'
    monkeypatch.setattr('src.source_adapters.fetch_text',fetch)
    monkeypatch.setattr('src.source_adapters.adapter_execution_allowed',lambda _:True)
    monkeypatch.setattr('src.source_adapters.parse_live_listings',lambda *args:[])
    monkeypatch.setattr('src.source_adapters.parse_visible_listing_links',lambda *args:[])
    monkeypatch.setenv('CARSCANNER_MAX_PAGES_PER_SOURCE','2')
    result=BuiltinMarketplaceAdapter({'name':'Test','url':'https://test.example/stock'}).fetch(AdapterRequest())
    assert result.status=='live'
    assert seen==['https://test.example/stock','https://test.example/page-2']
    seen.clear();monkeypatch.setenv('CARSCANNER_MAX_PAGES_PER_SOURCE','1')
    BuiltinMarketplaceAdapter({'name':'Test','url':'https://test.example/stock'}).fetch(AdapterRequest())
    assert seen==['https://test.example/stock']


def test_brand_identity_snapshot_is_bounded_to_each_scan(monkeypatch):
    from src import live_marketplaces as lm
    calls=[]
    monkeypatch.setattr(lm,'_registry_brand_records',lambda:calls.append(1) or [{'name':'BMW'}])
    monkeypatch.setattr(lm,'_configured_brand_records',lambda:[])
    @lm.with_brand_identity
    def scan():
        for _ in range(100):assert lm._known_brand_names()==['BMW']
    scan();assert len(calls)==1
    scan();assert len(calls)==2
    assert lm._brand_identity_snapshot.get() is None
