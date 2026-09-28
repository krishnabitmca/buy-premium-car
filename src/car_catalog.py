"""India-wide car make taxonomy used for search and normalization.

Model selection is intentionally not hardcoded. This file only provides a
broad make/alias layer; arbitrary model names are accepted from listing text.
"""

CAR_MAKES = [
    "Maruti Suzuki", "Hyundai", "Tata", "Mahindra", "Toyota", "Honda", "Kia",
    "Renault", "Nissan", "Skoda", "Volkswagen", "MG", "Citroen", "Jeep", "BYD",
    "Isuzu", "Force Motors", "Ford", "Chevrolet", "Fiat", "Datsun", "Mitsubishi",
    "SsangYong", "Hindustan Motors", "Premier",
    "Mercedes-Benz", "BMW", "Audi", "Volvo", "Lexus", "Jaguar", "Land Rover",
    "MINI", "Porsche", "Maserati", "Ferrari", "Lamborghini", "Aston Martin",
    "Bentley", "Rolls-Royce", "McLaren", "Lotus", "Alfa Romeo", "DS",
]

BRAND_ALIASES = [
    ("mercedes benz", "Mercedes-Benz"), ("mercedes-benz", "Mercedes-Benz"),
    ("mercedes", "Mercedes-Benz"), ("land rover", "Land Rover"),
    ("maruti suzuki", "Maruti Suzuki"), ("maruti", "Maruti Suzuki"),
    ("tata motors", "Tata"), ("tata", "Tata"), ("force motors", "Force Motors"),
    ("mg motor", "MG"), ("mg motors", "MG"), ("mg", "MG"),
    ("ssangyong", "SsangYong"), ("hindustan", "Hindustan Motors"),
    ("rolls-royce", "Rolls-Royce"), ("rolls royce", "Rolls-Royce"),
    ("alfa romeo", "Alfa Romeo"),
]
BRAND_ALIASES += [(b.lower(), b) for b in CAR_MAKES if b.lower() not in {a for a, _ in BRAND_ALIASES}]

MODEL_STOP_WORDS = {
    "used", "pre-owned", "preowned", "certified", "approved", "demo",
    "petrol", "diesel", "electric", "hybrid", "automatic", "manual",
    "amt", "at", "mt", "cvt", "dct", "dsg", "awd", "fwd", "4wd",
    "first", "second", "third", "owner", "owners", "kms", "km",
    "sport", "sportz", "vxi", "zxi", "sxi", "sxo", "sx(o)", "vx",
    "zx", "zxo", "alpha", "delta", "sigma", "magna", "asta", "nline",
    "gt", "gti", "m", "m-sport", "msport", "amg", "quattro", "xdrive",
    "4matic", "inscription", "ultimate", "prime", "technology",
}
