from src.catalog_traversal import scoped_advertised_total


def test_cartrade_generic_national_heading_not_used_as_model_inventory_evidence():
    html = '<h1>1,925 Used Cars in India</h1><p>No cars currently listed</p>'
    assert scoped_advertised_total(html, 'CarTrade', 'https://www.cartrade.com/second-hand/mg-m9/') is None


def test_cartrade_matching_model_heading_retains_count_evidence():
    html = '<h1>1,925 Used MG M9 Cars</h1>'
    assert scoped_advertised_total(html, 'CarTrade', 'https://www.cartrade.com/second-hand/mg-m9/') == 1925


def test_cartrade_national_and_other_sources_unchanged():
    html = '<h1>1,925 Used Cars in India</h1>'
    assert scoped_advertised_total(html, 'CarTrade', 'https://www.cartrade.com/second-hand/') == 1925
    assert scoped_advertised_total(html, 'CarWale Used', 'https://www.carwale.com/used/mg-m9/') == 1925
