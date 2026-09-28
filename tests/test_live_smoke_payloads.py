from types import SimpleNamespace
from src.extractor import extract_page

def test_carwale_live_payload_parses():
    body="2023 Mercedes-Benz GLA 220d AMG Line 4MATIC 32,500 km Diesel Rockdale Somajiguda Hyderabad ₹ 37.5 Lakh New Car Price Rs. 65.35 Lakh Registration year Aug 2023 Manufacturing Year Apr 2023 No. of owners First Transmission Automatic"
    result=SimpleNamespace(html="",markdown=body,redirected_url="https://example.com",status_code=200,success=True,crawled_at="2026-09-28T00:00:00Z")
    v=extract_page("test",1,"https://example.com/gla",result)
    assert v is not None and v.price_lakh==37.5 and v.mileage_km==32500 and v.owner_count==1

def test_autobest_live_payload_parses_rupee_integer():
    body="Audi Q3 40 TFSI PREMIUM PLUS 2023 Location RAJOURI GARDEN Year 2023 Year Of Manufacturing 2023 Engine Type Petrol Date of registration 2023 OCT Insurance Type Expired Warranty No Reservation Amount: ₹347500 (10% of ₹3475000)"
    result=SimpleNamespace(html="",markdown=body,redirected_url="https://example.com",status_code=200,success=True,crawled_at="2026-09-28T00:00:00Z")
    v=extract_page("test",1,"https://example.com/q3",result)
    assert v is not None and v.price_lakh==34.75 and v.year_manufacture==2023 and v.year_registration==2023
