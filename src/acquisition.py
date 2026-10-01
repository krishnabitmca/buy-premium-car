from __future__ import annotations
from .india_geo import infer_state

def purchase_context(vehicle:dict, destination_city:str|None):
    destination_city=(destination_city or "").strip()
    destination_state=infer_state(destination_city,destination_city)
    seller_state=(vehicle.get("seller_state") or vehicle.get("registration_state") or infer_state(vehicle.get("location"),vehicle.get("location")) or "").strip()
    seller_city=(vehicle.get("seller_city") or vehicle.get("location") or "").strip()
    if destination_state and seller_state and destination_state.lower()==seller_state.lower():
        mode="same_state"
        note=f"Seller is in {seller_city or seller_state}; same-state purchase context."
    elif seller_state and destination_state:
        mode="interstate"
        note=f"Seller is in {seller_city or seller_state}; interstate transfer/tax/transport should be checked."
    elif seller_city and destination_city and seller_city.lower()==destination_city.lower():
        mode="local"
        note="Seller location matches your destination city."
    else:
        mode="location_unknown"
        note="Seller/registration state is not sufficiently verified."
    return {
        "destination_city":destination_city or None,
        "destination_state":destination_state or None,
        "seller_city":seller_city or None,
        "seller_state":seller_state or None,
        "mode":mode,
        "observed_listing_price_lakh":vehicle.get("price_lakh"),
        "additional_cost_status":"not separately estimated" if mode=="interstate" else "no additional interstate estimate needed",
        "note":note
    }
