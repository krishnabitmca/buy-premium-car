from http.server import BaseHTTPRequestHandler
from api.search import _read_json, _response
from src.buyer_ai import interpret, AIUnavailable


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            body=_read_json(self)
            if not isinstance(body,dict):
                raise ValueError('Expected a JSON object')
            result=interpret(body.get('prompt'),consent=body.get('consent'))
            return _response(self,200,{'ok':True,**result})
        except ValueError as exc:
            return _response(self,400,{'ok':False,'error':str(exc)})
        except AIUnavailable as exc:
            return _response(self,503,{'ok':False,'error':str(exc)})

    def do_OPTIONS(self):
        return _response(self,204,{})
