from src.reviewed_inventory import parse_autohangar_cards
from src.source_adapters import AdapterRequest,BuiltinMarketplaceAdapter


HTML = '''
<div class="cars-box">
  <img src="images/cars/1.png">
  <p class="carName">Mercedes-Benz E220d Exclusive MY22</p>
  <p class="carYear">2022</p>
  <div class="carDetails">42,000 Kms Diesel Polar White Sedan</div>
  <p class="carPrice">INR 52.52 Lakhs</p>
</div>
<div class="cars-box">
  <p class="carName">BMW X3 XDRIVE 20D LUXURY LINE</p>
  <p class="carYear">2020</p>
  <div class="carDetails">58,000 Kms Diesel Phytonic Blue Compact SUV</div>
  <p class="carPrice">INR 40.40 Lakhs</p>
</div>
<div class="cars-box">
  <p class="carName">Range Rover Sport 3.0D HSE</p>
  <p class="carYear">2018</p>
  <div class="carDetails">53,500 Kms Diesel Fuji White SUV</div>
  <p class="carPrice">INR 63.63 Lakhs</p>
</div>
'''


def test_autohangar_catalogue_cards_are_distinct_current_used_offers():
    rows=parse_autohangar_cards(HTML,'AutoHangar Used Cars','https://autohangar.net/usedcars/')
    assert len(rows)==3
    assert len({row['source_listing_id'] for row in rows})==3
    mercedes=rows[0]
    assert mercedes['brand']=='Mercedes-Benz'
    assert mercedes['model']=='E-Class'
    assert mercedes['price_lakh']==52.52
    assert mercedes['km']==42000
    assert mercedes['registration_year'] is None
    assert mercedes['metadata']['source_year']==2022
    assert mercedes['metadata']['source_year_semantics']=='unclassified'
    assert mercedes['condition_signal']=='used'
    assert mercedes['url']=='https://autohangar.net/usedcars/'
    assert mercedes['images']==['https://autohangar.net/usedcars/images/cars/1.png']
    assert rows[2]['brand']=='Land Rover'


def test_autohangar_query_filter_and_invalid_cards_fail_closed():
    html=HTML+'''<div class="cars-box"><p class="carName">Audi Q5 Premium</p>
      <p class="carYear">2021</p><div>Sold</div></div>'''
    rows=parse_autohangar_cards(html,'AutoHangar Used Cars','https://autohangar.net/usedcars/','BMW X3')
    assert [row['brand'] for row in rows]==['BMW']
    try:
        parse_autohangar_cards('<div class="cars-box">no price</div>',
            'AutoHangar Used Cars','https://autohangar.net/usedcars/')
    except ValueError as exc:
        assert str(exc)=='AutoHangar catalogue cards yielded no valid evidence'
    else:
        raise AssertionError('expected drift failure')


def test_autohangar_explicit_sold_card_uses_same_identity_as_previous_offer():
    initial=parse_autohangar_cards(HTML,'AutoHangar Used Cars','https://autohangar.net/usedcars/')
    sold_html=HTML.replace(
        '<p class="carPrice">INR 52.52 Lakhs</p>',
        '<p class="carPrice">INR 52.52 Lakhs</p><strong>Sold</strong>',1)
    sold=parse_autohangar_cards(sold_html,'AutoHangar Used Cars','https://autohangar.net/usedcars/')
    assert sold[0]['sold_signal'] is True
    assert sold[0]['live_verified'] is False
    assert sold[0]['source_listing_id']==initial[0]['source_listing_id']


def test_autohangar_rejects_unknown_brand_and_unsafe_image():
    bad='''<div class="cars-box"><img src="javascript:alert(1)">
      <p class="carName">Finance Calculator</p><p class="carYear">2024</p>
      <div class="carDetails">10,000 Kms Petrol</div>
      <p class="carPrice">INR 10 Lakhs</p></div>'''
    try:
        parse_autohangar_cards(bad,'AutoHangar Used Cars','https://autohangar.net/usedcars/')
    except ValueError:
        pass
    else:
        raise AssertionError('unknown brands must fail closed')


def test_autohangar_empty_catalogue_does_not_use_generic_fallback(monkeypatch):
    source={'name':'AutoHangar Used Cars','url':'https://autohangar.net/usedcars/',
            'adapter_status':'live','parser_strategy':'autohangar_cards'}
    monkeypatch.setattr('src.source_adapters.adapter_execution_allowed',lambda _:True)
    monkeypatch.setattr('src.source_adapters.record_adapter_execution',lambda *args,**kwargs:None)
    monkeypatch.setattr('src.source_adapters.fetch_text',lambda _: '<html><p>No inventory</p></html>')
    monkeypatch.setattr('src.source_adapters.parse_live_listings',
                        lambda *args: (_ for _ in ()).throw(AssertionError('generic fallback')))
    result=BuiltinMarketplaceAdapter(source).fetch(AdapterRequest(continuation={}))
    assert result.status=='live'
    assert result.listings==[]


def test_autohangar_price_change_preserves_source_identity():
    initial=parse_autohangar_cards(HTML,'AutoHangar Used Cars','https://autohangar.net/usedcars/')
    changed=parse_autohangar_cards(HTML.replace('52.52','50.00'),'AutoHangar Used Cars',
                                   'https://autohangar.net/usedcars/')
    assert initial[0]['source_listing_id']==changed[0]['source_listing_id']
    assert changed[0]['price_lakh']==50
    changed_again=parse_autohangar_cards(
        HTML.replace('42,000','43,000').replace('images/cars/1.png','images/cars/new.png'),
        'AutoHangar Used Cars','https://autohangar.net/usedcars/')
    assert initial[0]['source_listing_id']==changed_again[0]['source_listing_id']
    assert initial[0]['location'] is None


def test_autohangar_parser_rejects_unreviewed_host():
    try:
        parse_autohangar_cards(HTML,'AutoHangar Used Cars','https://example.com/usedcars/')
    except ValueError as exc:
        assert str(exc)=='Unreviewed AutoHangar host'
    else:
        raise AssertionError('expected host rejection')
