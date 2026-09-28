from src.normalize import extract_mileage, extract_price_lakh, extract_owner, normalize_model

def test_extractors():
    text="2024 BMW X1 M Sport | 14,400 km | 1st owner | ₹39.00 lakh"
    assert extract_mileage(text)==14400
    assert extract_price_lakh(text)==39.0
    assert extract_owner(text)==1
    brand,model,variant=normalize_model("BMW X1 M Sport",text)
    assert brand=="BMW"
    assert model=="X1"

def test_mainstream_make_and_unlisted_model_are_supported():
    brand,model,variant=normalize_model(
        "2024 Hyundai Creta SX(O)",
        "2024 Hyundai Creta SX(O) Petrol Automatic 12,000 km ₹18.5 lakh Bengaluru"
    )
    assert brand=="Hyundai"
    assert model=="Creta"

    brand,model,variant=normalize_model(
        "2023 Maruti Suzuki Fronx Delta",
        "2023 Maruti Suzuki Fronx Delta Petrol 9,000 km ₹10.25 lakh Pune"
    )
    assert brand=="Maruti Suzuki"
    assert model=="Fronx"

    brand,model,variant=normalize_model(
        "2022 Tata Harrier XZA",
        "2022 Tata Harrier XZA Diesel 32,000 km ₹17 lakh Jaipur"
    )
    assert brand=="Tata"
    assert model=="Harrier"
