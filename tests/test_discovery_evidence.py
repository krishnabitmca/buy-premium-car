"""Discovery intent cannot become inventory-condition evidence."""

from src.discovery import _classify


def test_demo_query_does_not_label_an_ordinary_dealer_directory_demo():
    source_type, condition, confidence = _classify(
        'Land Rover Car Dealers - Showrooms in India',
        'Find authorised dealers, addresses and phone numbers.',
        '"Land Rover" demo cars India dealer',
        'Land Rover',
        'https://example.test/landrover-cars/dealers',
    )
    assert source_type == 'dealer_network'
    assert condition == 'both'
    assert confidence < 1


def test_demo_query_does_not_override_explicit_used_catalogue_evidence():
    _, condition, _ = _classify(
        'Buy verified used cars',
        'Browse second hand cars for sale.',
        '"BMW" demo cars India dealer',
        'BMW',
        'https://example.test/used-cars/',
    )
    assert condition == 'used'


def test_page_level_demo_evidence_is_retained():
    source_type, condition, confidence = _classify(
        'Skoda Demo Cars for Sale',
        'Individually listed demonstrator vehicles from our dealership.',
        '"Skoda" demo cars India dealer',
        'Skoda',
        'https://dealer.example/demo-cars/',
    )
    assert source_type == 'dealer_network'
    assert condition == 'demo'
    assert confidence >= .8


def test_url_path_is_page_evidence_but_query_text_is_not():
    assert _classify('', '', '"Honda" demo cars India', 'Honda',
                     'https://dealer.example/demo-cars/')[1] == 'demo'
    assert _classify('', '', '"Honda" demo cars India', 'Honda',
                     'https://dealer.example/showrooms/')[1] == 'both'
