from src.normalize import extract_mileage, extract_price_lakh, extract_owner, normalize_model

def test_extractors():
    text="2024 BMW X1 M Sport | 14,400 km | 1st owner | ₹39.00 lakh"
    assert extract_mileage(text)==14400
    assert extract_price_lakh(text)==39.0
    assert extract_owner(text)==1
    brand,model,variant=normalize_model("BMW X1 M Sport",text)
    assert brand=="BMW"
    assert model=="X1"
