"""One validated contract for form refinements and optional model interpretation."""
from dataclasses import asdict, dataclass
import math


def _number(body, key, maximum, *, integer=False):
    value = body.get(key)
    if value in (None, ''):
        return None
    if isinstance(value, bool):
        raise ValueError(f'Invalid {key}')
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'Invalid {key}') from None
    if not math.isfinite(result) or not 0 <= result <= maximum or (integer and not result.is_integer()):
        raise ValueError(f'Invalid {key}')
    return int(result) if integer else result


def _text(body, key, maximum=160):
    value = body.get(key)
    if value is None:
        value = ''
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f'Invalid {key}')
    return ' '.join(value.split())


def _choices(body, key, allowed):
    value = body.get(key)
    if value is None:
        value = []
    if not isinstance(value, list) or len(value) > len(allowed):
        raise ValueError(f'Invalid {key}')
    if any(not isinstance(x, str) or x.lower() not in allowed for x in value):
        raise ValueError(f'Unsupported {key}')
    return sorted({x.lower() for x in value})


@dataclass(frozen=True)
class SearchIntent:
    query: str = ''
    condition: str = 'both'
    destination: str = ''
    budget_min: float | None = None
    budget_max: float | None = None
    max_age_years: float | None = None
    fuels: tuple = ()
    transmissions: tuple = ()
    body_types: tuple = ()
    max_mileage_km: int | None = None
    max_owners: int | None = None
    manufacture_year: int | None = None
    seller_city: str = ''
    sort: str = 'match'

    @classmethod
    def parse(cls, body):
        if not isinstance(body, dict):
            raise ValueError('Search intent must be an object')
        condition = _text(body, 'condition') or 'both'
        sort = _text(body, 'sort') or 'match'
        if condition not in {'both', 'used', 'demo'} or sort not in {'match', 'price', 'gap', 'km', 'year'}:
            raise ValueError('Unsupported condition or sort')
        result = cls(
            query=_text(body, 'query'), condition=condition, sort=sort,
            destination=_text(body, 'destination'), seller_city=_text(body, 'seller_city'),
            budget_min=_number(body, 'budget_min', 10000), budget_max=_number(body, 'budget_max', 10000),
            max_age_years=_number(body, 'max_age_years', 100),
            fuels=tuple(_choices(body, 'fuels', {'petrol', 'diesel', 'electric', 'hybrid', 'cng', 'lpg'})),
            transmissions=tuple(_choices(body, 'transmissions', {'automatic', 'manual'})),
            body_types=tuple(_choices(body, 'body_types', {'suv', 'sedan', 'hatchback', 'coupe', 'convertible', 'mpv', 'wagon', 'pickup'})),
            max_mileage_km=_number(body, 'max_mileage_km', 2000000, integer=True),
            max_owners=_number(body, 'max_owners', 20, integer=True),
            manufacture_year=_number(body, 'manufacture_year', 2100, integer=True),
        )
        if result.budget_min is not None and result.budget_max is not None and result.budget_min > result.budget_max:
            raise ValueError('Minimum budget cannot exceed maximum budget')
        if result.manufacture_year is not None and result.manufacture_year < 1900:
            raise ValueError('Invalid manufacture_year')
        return result

    def public(self):
        return {k:list(v) if isinstance(v,tuple) else v for k,v in asdict(self).items()}

    def refinements(self):
        return {k: v for k, v in self.public().items() if k in {
            'fuels', 'transmissions', 'body_types', 'max_mileage_km', 'max_owners',
            'manufacture_year', 'seller_city', 'sort'}}


def matches_refinements(vehicle, intent):
    """Equivalent constraints for the unpaginated legacy live adapter path."""
    fuel=str(vehicle.get('fuel') or '').strip().lower()
    transmission=str(vehicle.get('transmission') or '').strip().lower()
    if transmission in {'auto','at','dct','cvt','amt','dsg','tiptronic'}:
        transmission='automatic'
    if transmission == 'mt':
        transmission='manual'
    if intent.fuels and fuel not in intent.fuels:
        return False
    if intent.transmissions and transmission not in intent.transmissions:
        return False
    if intent.body_types and str(vehicle.get('body_type') or '').strip().lower() not in intent.body_types:
        return False
    for maximum,key in ((intent.max_mileage_km,'km'),(intent.max_owners,'owners')):
        if maximum is not None and (vehicle.get(key) is None or float(vehicle[key]) > maximum):
            return False
    if intent.manufacture_year is not None and vehicle.get('mfg_year') != intent.manufacture_year:
        return False
    return not intent.seller_city or str(vehicle.get('location') or '').strip().lower() == intent.seller_city.lower()
