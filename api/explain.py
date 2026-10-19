"""Opt-in, server-grounded public buyer evidence endpoint."""
from http.server import BaseHTTPRequestHandler
import logging
from api.search import _read_json,_response
from src.buyer_ai import AIUnavailable,ai_slot
from src.buyer_evidence import explain_vehicle


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            body=_read_json(self)
            if not isinstance(body,dict):raise ValueError('Expected a JSON object')
            with ai_slot():
                result=explain_vehicle(body.get('vehicle_id'),body.get('price_basis'),body.get('question'),consent=body.get('consent'))
            return _response(self,200,{'ok':True,**result})
        except ValueError as exc:
            return _response(self,400,{'ok':False,'error':str(exc)})
        except LookupError as exc:
            return _response(self,409,{'ok':False,'error':str(exc)})
        except AIUnavailable as exc:
            return _response(self,503,{'ok':False,'error':str(exc)})
        except Exception as exc:
            logging.getLogger(__name__).warning('buyer_evidence_failed type=%s',type(exc).__name__)
            return _response(self,503,{'ok':False,'error':'Evidence could not be retrieved. Refresh search or read the original offers.'})
