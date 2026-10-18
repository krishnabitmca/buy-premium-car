"""Public inventory evidence registry; no model-authored facts reach the buyer."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import math
import re
from urllib.parse import urlsplit
from uuid import UUID

from .inventory_db import search_inventory
from .buyer_ai import AIUnavailable, select_evidence

UNKNOWNS = {
    'availability': 'Physical availability must be confirmed with the original seller.',
    'inspection': 'This dossier does not establish inspection or accident history.',
    'warranty': 'Verified warranty and service-record evidence is not supplied here.',
    'identity': 'Grouped listings are not proof of the same physical car; confirm full identity with the seller.',
    'value': 'Asking prices do not establish fair value or the final transaction price.',
    'cost': 'Transport, registration, tax and other destination costs are not established here.',
    'coverage': 'Coverage is partial; these offers do not establish the lowest price across India.',
    'other': 'The retrieved dossier does not establish an answer to this question.',
}


def validate_question(question, consent):
    if consent is not True:
        raise ValueError('Opt in before sending a question to Gemini.')
    if not isinstance(question, str) or not 3 <= len(question.strip()) <= 500:
        raise ValueError('Ask a car question in 3–500 characters.')
    if re.search(r'https?://|\S+@\S+|(?:\+?\d[\s().-]*){10,}', question):
        raise ValueError('Remove links, contact details and personal identifiers; ask about the car only.')
    return question.strip()


def public_url(value):
    try:
        value=str(value or '')
        url=urlsplit(value)
        if url.scheme in {'https','http'} and url.hostname and not url.username and not url.password:
            return value
    except ValueError:
        pass
    return None


def _text(value):
    # Bounded database display values are data, never model instructions or HTML.
    return str(value).strip()[:160]


def evidence_registry(row):
    facts=[];sources=[]
    for index,offer in enumerate((row.get('offers') or [])[:12]):
        link=public_url(offer.get('final_url') or offer.get('url'))
        if not link:
            continue
        source_id=f's{index+1}'
        source={'id':source_id,'name':_text(offer.get('source') or 'Original source'),
                'url':link,'observed_at':offer.get('observed_at')}
        sources.append(source)
        try:
            price=Decimal(str(offer.get('price_lakh')))
            if not price.is_finite() or price <= 0 or price > 100000:
                continue
        except (InvalidOperation,ValueError,TypeError):
            continue
        facts.append({'id':f'{source_id}.price','kind':'source_observation',
            'text':f"Recorded asking price: INR {price:.2f} lakh; price basis: {_text(offer.get('price_basis') or 'unspecified')}.",
            'source_ids':[source_id],'observed_at':offer.get('observed_at')})
    if not sources:
        return [],[]
    source_ids=[source['id'] for source in sources]
    for field,label in [('mfg_year','Manufacture year'),('km','Mileage (km)'),
                        ('fuel','Fuel'),('transmission','Transmission'),('condition','Used/demo classification')]:
        value=row.get(field)
        if value is None or value=='' or str(value).lower() in {'unknown','unspecified'}:
            continue
        if field in {'km','mfg_year'}:
            try:
                number=float(value)
                if not math.isfinite(number) or number<0 or number!=int(number):continue
                value=int(number)
            except (ValueError,TypeError,OverflowError):continue
        facts.append({'id':'record.'+field,'kind':'canonical_record',
            'text':f'Canonical inventory record — {label}: {_text(value)}. Attribute provenance is not independently verified by this guide.',
            'source_ids':source_ids,'observed_at':row.get('observed_at')})
    return facts,sources


def explain_vehicle(vehicle_id, price_basis, question, *, consent=False):
    question=validate_question(question,consent)
    try: vehicle_id=str(UUID(vehicle_id))
    except (ValueError,TypeError,AttributeError):raise ValueError('Invalid vehicle identifier') from None
    if not isinstance(price_basis,str) or not 1<=len(price_basis)<=80:
        raise ValueError('Select the original price basis')
    rows,_=search_inventory(_vehicle_ids=[vehicle_id],limit=2000,require_persistence=True)
    matching=[row for row in rows if row.get('vehicle_id')==vehicle_id and (row.get('price_basis') or 'unspecified')==price_basis]
    if len(matching)!=1:
        raise LookupError('This offer or price basis is no longer eligible. Refresh search before asking about it.')
    checked_at=datetime.now(timezone.utc).isoformat()
    facts,sources=evidence_registry(matching[0])
    if not facts:
        raise LookupError('No source-linked evidence is available for this offer.')
    selected=select_evidence(question,[{'id':fact['id'],'text':fact['text']} for fact in facts],
                             list(UNKNOWNS),consent=True)
    registry={fact['id']:fact for fact in facts}
    # The provider helper validates too; keep the public boundary independent.
    ids=selected.get('fact_ids',[]);unknowns=selected.get('unknowns',[])
    if any(identifier not in registry for identifier in ids) or any(key not in UNKNOWNS for key in unknowns):
        raise AIUnavailable('The AI evidence selection could not be validated. Read the original offers instead.')
    chosen=[registry[identifier] for identifier in ids]
    used={identifier for fact in chosen for identifier in fact['source_ids']}
    return {'vehicle_id':vehicle_id,'price_basis':price_basis,'checked_at':checked_at,
        'answer_mode':'evidence_selection','model_generated_facts':False,'provider':'gemini',
        'facts':chosen,'sources':[source for source in sources if source['id'] in used],
        'abstained':not bool(chosen),
        'unknowns':[UNKNOWNS[key] for key in dict.fromkeys(unknowns+['availability','inspection','warranty','identity','value','cost','coverage'])]}
