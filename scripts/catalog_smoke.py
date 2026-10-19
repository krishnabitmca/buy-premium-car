"""Bounded public catalogue/search smoke clients using the UI retry contract."""
import json
import time
from urllib.error import HTTPError
from urllib.request import Request,urlopen


def get_catalog(base,path,*,opener=urlopen,sleep=time.sleep,clock=time.monotonic):
    req=Request(base+path,headers={'Cache-Control':'no-cache'})
    return _read_json(req,opener=opener,sleep=sleep,clock=clock,budget=12,transport=5)


def post_search(base,body,*,opener=urlopen,sleep=time.sleep,clock=time.monotonic):
    # Only this documented read-only POST may be replayed, never watch or AI.
    req=Request(base+'/api/search',data=json.dumps(body).encode(),method='POST',
        headers={'Cache-Control':'no-cache','Content-Type':'application/json'})
    return _read_json(req,opener=opener,sleep=sleep,clock=clock,budget=30,transport=10)


def _read_json(req,*,opener,sleep,clock,budget,transport):
    deadline=clock()+budget
    for attempt in range(6):
        remaining=deadline-clock()
        if remaining<=0:break
        try:
            with opener(req,timeout=min(transport,remaining)) as response:
                if response.status!=200:raise RuntimeError('Read-only inventory request did not return HTTP 200')
                return json.load(response)
        except HTTPError as exc:
            try:delay=float(exc.headers.get('Retry-After',''))
            except (ValueError,TypeError):delay=0
            retry=exc.code==503 and 0<delay<=2 and attempt<5 and clock()+delay<deadline
            if not retry:raise
            exc.close()
            sleep(delay)
    raise RuntimeError('Read-only inventory request exceeded its bounded smoke budget')
