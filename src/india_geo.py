from __future__ import annotations
import re

CITY_STATE_PAIRS = {
    "bengaluru":"Karnataka","bangalore":"Karnataka","mysuru":"Karnataka","mangalore":"Karnataka","mangaluru":"Karnataka",
    "hyderabad":"Telangana","chennai":"Tamil Nadu","coimbatore":"Tamil Nadu","mumbai":"Maharashtra","pune":"Maharashtra",
    "nagpur":"Maharashtra","nashik":"Maharashtra","thane":"Maharashtra","navi mumbai":"Maharashtra",
    "delhi":"Delhi","new delhi":"Delhi","gurgaon":"Haryana","gurugram":"Haryana","noida":"Uttar Pradesh",
    "ghaziabad":"Uttar Pradesh","faridabad":"Haryana","jaipur":"Rajasthan","ahmedabad":"Gujarat","surat":"Gujarat",
    "vadodara":"Gujarat","chandigarh":"Chandigarh","lucknow":"Uttar Pradesh","kanpur":"Uttar Pradesh","agra":"Uttar Pradesh",
    "varanasi":"Uttar Pradesh","bhopal":"Madhya Pradesh","indore":"Madhya Pradesh","raipur":"Chhattisgarh",
    "kochi":"Kerala","cochin":"Kerala","thiruvananthapuram":"Kerala","kolkata":"West Bengal","bhubaneswar":"Odisha",
    "patna":"Bihar","ranchi":"Jharkhand","guwahati":"Assam","visakhapatnam":"Andhra Pradesh","vijayawada":"Andhra Pradesh",
    "dehradun":"Uttarakhand","amritsar":"Punjab","ludhiana":"Punjab","jodhpur":"Rajasthan","udaipur":"Rajasthan",
    "goa":"Goa","mysore":"Karnataka"
}
STATE_PATTERNS = [
    ("Karnataka", r"\bkarnataka\b"),
    ("Tamil Nadu", r"\btamil\s+nadu\b"),
    ("Telangana", r"\btelangana\b"),
    ("Maharashtra", r"\bmaharashtra\b"),
    ("Delhi", r"\bnew\s+delhi\b|\bdelhi\b|\bncr\b"),
    ("Haryana", r"\bharyana\b"),
    ("Uttar Pradesh", r"\buttar\s+pradesh\b"),
    ("Rajasthan", r"\brajasthan\b"),
    ("Gujarat", r"\bgujarat\b"),
    ("Kerala", r"\bkerala\b"),
    ("West Bengal", r"\bwest\s+bengal\b"),
    ("Odisha", r"\bodisha\b|\borissa\b"),
    ("Bihar", r"\bbihar\b"),
    ("Jharkhand", r"\bjharkhand\b"),
    ("Assam", r"\bassam\b"),
    ("Andhra Pradesh", r"\bandhra\s+pradesh\b"),
    ("Madhya Pradesh", r"\bmadhya\s+pradesh\b"),
    ("Chhattisgarh", r"\bchhattisgarh\b"),
    ("Punjab", r"\bpunjab\b"),
    ("Uttarakhand", r"\buttarakhand\b"),
    ("Himachal Pradesh", r"\bhimachal\s+pradesh\b"),
    ("Goa", r"\bgoa\b"),
    ("Chandigarh", r"\bchandigarh\b"),
]

def infer_state(location: str|None, text: str=""):
    blob=(f"{location or ''} {text or ''}").lower()
    for state,pattern in STATE_PATTERNS:
        if re.search(pattern,blob,re.I):
            return state
    for city,state in sorted(CITY_STATE_PAIRS.items(), key=lambda x:len(x[0]), reverse=True):
        if re.search(r"(?<![a-z])"+re.escape(city)+r"(?![a-z])",blob,re.I):
            return state
    return None

def infer_city(location: str|None, text: str=""):
    blob=(f"{location or ''} {text or ''}").lower()
    for city in sorted(CITY_STATE_PAIRS,key=len,reverse=True):
        if re.search(r"(?<![a-z])"+re.escape(city)+r"(?![a-z])",blob,re.I):
            return city.title().replace("Bangalore","Bengaluru").replace("Mangalore","Mangaluru").replace("Mysore","Mysuru")
    if location:
        return str(location).strip()
    return None


def normalize_seller_location(location):
    """Conservative operational city identity; never a buyer inventory filter.

    Only a known city label, optionally followed by its matching state, is
    accepted. Addresses, regions and multiple cities retain unknown identity.
    Existing permissive purchase-context inference remains independent.
    """
    label = ' '.join(str(location or '').split())
    parts = [part.strip().casefold() for part in label.split(',')]
    city = parts[0]
    state = CITY_STATE_PAIRS.get(city)
    # Goa is a state/region label, not evidence of a specific city.
    if not state or city == 'goa' or len(parts)>2 or (len(parts)==2 and parts[1]!=state.casefold()):
        return dict(canonical_city=None,canonical_state=None,
                    location_status='missing' if not label else 'unresolved')
    aliases = {'bangalore':'Bengaluru','mangalore':'Mangaluru','mysore':'Mysuru',
               'gurgaon':'Gurugram','cochin':'Kochi','new delhi':'Delhi'}
    return dict(canonical_city=aliases.get(city,city.title()),canonical_state=state,
                location_status='recognized_label')
