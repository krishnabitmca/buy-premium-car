"""Revalidate public saved vehicle identifiers; never serves stored client prices."""
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler
import logging
from uuid import UUID
from api.search import _read_json,_response
from src.inventory_db import search_inventory


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            body=_read_json(self)
            ids=body.get('vehicle_ids') if isinstance(body,dict) else None
            if not isinstance(ids,list) or len(ids)>6 or any(not isinstance(value,str) for value in ids):
                raise ValueError('Provide up to six vehicle identifiers')
            try:ids=list(dict.fromkeys(str(UUID(value)) for value in ids))
            except (ValueError,TypeError,AttributeError):raise ValueError('Invalid vehicle identifier') from None
            rows=[]
            if ids:
                rows,_=search_inventory(_vehicle_ids=ids,limit=2000,require_persistence=True)
            present={row['vehicle_id'] for row in rows}
            return _response(self,200,{'ok':True,'results':rows,
                'unavailable_vehicle_ids':[value for value in ids if value not in present],
                'checked_at':datetime.now(timezone.utc).isoformat(),
                'availability_note':'Currently eligible database observations; confirm physical availability with the original seller.'})
        except ValueError as exc:
            return _response(self,400,{'ok':False,'error':str(exc)})
        except Exception as exc:
            logging.getLogger(__name__).warning('shortlist_revalidation_failed type=%s',type(exc).__name__)
            return _response(self,503,{'ok':False,'error':'Saved offers could not be rechecked; retry when connected.'})
