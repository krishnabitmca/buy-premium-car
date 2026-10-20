import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from scripts import probe_demo_source as probe
from src import live_marketplaces as lm

SUNDARAM='Sundaram Motors Pre-Owned'
GURUDEV='Gurudev Tata Demo'


class Response:
    def __init__(self,source,body,status=200,content_type='text/html'):
        self.url=probe.SOURCES[source][1]
        self.body=body
        self.status=status
        self.headers={'Content-Type':content_type}
        self.read_limits=[]
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def getcode(self):return self.status
    def geturl(self):return self.url
    def read(self,limit):
        self.read_limits.append(limit)
        return self.body[:limit]


class Opener:
    def __init__(self,response=None,error=None):
        self.response=response
        self.error=error
        self.calls=[]
    def open(self,request,timeout):
        self.calls.append((request,timeout))
        if self.error:raise self.error
        return self.response


@pytest.mark.parametrize('source,fixture,content_type',[
    (SUNDARAM,'sundaram_cards.html','text/html'),
    (GURUDEV,'gurudev_stock.json','application/json')])
def test_real_parser_one_request_no_db_and_safe_sample(source,fixture,content_type,monkeypatch):
    body=Path('tests/fixtures',fixture).read_bytes()
    response=Response(source,body,content_type=content_type)
    opener=Opener(response)
    def forbidden(*args,**kwargs):raise AssertionError('Database or additional acquisition forbidden')
    monkeypatch.setattr(lm,'_registry_brand_records',forbidden)
    monkeypatch.setattr('src.demo_dealers.fetch_sundaram',forbidden)
    previous=('Existing context',)
    token=lm._brand_identity_snapshot.set(previous)
    try:
        report=probe.probe(source,opener=opener)
        assert lm._brand_identity_snapshot.get()==previous
    finally:lm._brand_identity_snapshot.reset(token)
    assert report['status']=='retrieved' and report['condition_counts']['demo']>=1
    assert report['samples'] and len(report['samples'])<=5
    assert len(opener.calls)==1 and response.read_limits==[probe.MAX_BYTES+1]
    assert not report['inventory_ingested'] and not report['completeness_verified']
    assert report['sampled_only'] and report['http_status']==200
    assert not report['absence_reconciliation_permitted']
    assert all(set(row)=={'url','price_lakh','condition'} for row in report['samples'])


@pytest.mark.parametrize('status',[301,302,401,403,429,500])
def test_http_error_never_parsed_or_retried(status,monkeypatch):
    def forbidden(*args):raise AssertionError('Must not parse')
    monkeypatch.setattr(probe,'parse_sundaram',forbidden)
    opener=Opener(error=HTTPError(probe.SOURCES[SUNDARAM][1],status,'secret-cookie-body',{},None))
    result=probe.probe(SUNDARAM,opener=opener)
    assert result['status']==('blocked' if status in (401,403,429) else 'unavailable')
    assert result['samples']==[] and len(opener.calls)==1
    assert 'secret-cookie-body' not in json.dumps(result)


def test_non2xx_response_and_oversize_are_not_parsed(monkeypatch):
    def forbidden(*args):raise AssertionError('Must not parse')
    monkeypatch.setattr(probe,'parse_sundaram',forbidden)
    response=Response(SUNDARAM,b'fake priced cards',status=403)
    assert probe.probe(SUNDARAM,opener=Opener(response))['status']=='blocked'
    assert not response.read_limits
    response=Response(SUNDARAM,b'a'*(probe.MAX_BYTES+1))
    assert probe.probe(SUNDARAM,opener=Opener(response))['reason']=='response_too_large'


def test_parser_error_restores_context_and_redacts_exception(monkeypatch):
    def fail(*args):raise ValueError('token=secret session=private')
    monkeypatch.setattr(probe,'parse_sundaram',fail)
    before=lm._brand_identity_snapshot.get()
    result=probe.probe(SUNDARAM,opener=Opener(Response(SUNDARAM,b'body')))
    assert result['status']=='parser_error' and 'secret' not in json.dumps(result)
    assert lm._brand_identity_snapshot.get()==before


def test_redirect_handler_refuses_even_same_origin_redirect():
    assert probe.NoRedirect().redirect_request(None,None,302,'',{},probe.SOURCES[SUNDARAM][1]) is None


def test_no_inventory_not_reported_as_market_zero():
    result=probe.probe(SUNDARAM,opener=Opener(Response(SUNDARAM,b'<h1>No cards</h1>')))
    assert result['status']=='retrieved' and result['parsed_count']==0
    assert result['reason']=='parsed_sample_not_inventory_guarantee'


def test_sample_rejects_credentials_query_fragment_unsafe_origin_and_nan(monkeypatch):
    base=probe.SOURCES[SUNDARAM][1]
    monkeypatch.setattr(probe,'parse_sundaram',lambda *a:[
        dict(url=url,price_lakh=price,condition_signal='demo') for url,price in [
            (base+'one?token=secret',1),(base+'two#private',2),('https://evil.invalid/car',3),
            ('https://user:secret@sundarammotorspoc.com/car',4),(base+'four',float('nan')),
            (base+'five',5),('https://sundarammotorspoc.com/reset/token',6)]])
    result=probe.probe(SUNDARAM,opener=Opener(Response(SUNDARAM,b'body')))
    assert result['samples']==[dict(url=base+'five',price_lakh=5,condition='demo')]
    assert 'secret' not in json.dumps(result,allow_nan=False)


def test_unsupported_source_does_not_request():
    opener=Opener()
    with pytest.raises(ValueError):probe.probe('Unknown',opener=opener)
    assert not opener.calls
