"""Bounded catalogue smoke client honoring the same warming contract as the UI."""
import json
import time
from urllib.error import HTTPError
from urllib.request import Request,urlopen


def get_catalog(base,path,*,opener=urlopen,sleep=time.sleep,clock=time.monotonic):
    deadline=clock()+12
    for attempt in range(6):
        remaining=deadline-clock()
        if remaining<=0:break
        req=Request(base+path,headers={'Cache-Control':'no-cache'})
        try:
            with opener(req,timeout=min(5,remaining)) as response:
                if response.status!=200:raise RuntimeError('Catalogue did not return HTTP 200')
                return json.load(response)
        except HTTPError as exc:
            try:delay=float(exc.headers.get('Retry-After',''))
            except (ValueError,TypeError):delay=0
            retry=exc.code==503 and 0<delay<=2 and attempt<5 and clock()+delay<deadline
            if not retry:raise
            exc.close()
            sleep(delay)
    raise RuntimeError('Catalogue did not finish warming within its bounded smoke budget')
