from email.message import Message
from io import BytesIO
from urllib.error import HTTPError
import pytest
from scripts.catalog_smoke import get_catalog,post_search


def warming(code=503,header='1'):
    headers=Message()
    if header is not None:headers['Retry-After']=header
    return HTTPError('https://fixture.invalid/api/catalog',code,'test',headers,BytesIO(b'{}'))


def test_cold_catalogue_must_eventually_return_real_success():
    calls=[];clock=[0]
    def fetch(req,timeout):
        calls.append(req.full_url)
        assert timeout<=5
        if len(calls)==1:raise warming()
        response=BytesIO(b'{"ok":true,"models":[{"name":"Q5"}]}');response.status=200
        return response
    result=get_catalog('https://fixture.invalid','/api/catalog?brand=Audi',opener=fetch,
        sleep=lambda seconds:clock.__setitem__(0,clock[0]+seconds),clock=lambda:clock[0])
    assert result['models'][0]['name']=='Q5' and len(calls)==2 and clock[0]==1


@pytest.mark.parametrize('code,header',[(404,'1'),(503,None),(503,'120'),(503,'nan')])
def test_real_failures_or_unsupported_retry_headers_are_not_hidden(code,header):
    calls=[]
    def fetch(*a,**k):calls.append(1);raise warming(code,header)
    with pytest.raises(HTTPError):get_catalog('https://fixture.invalid','/api/catalog',opener=fetch)
    assert calls==[1]


def test_persistent_warming_fails_after_bounded_attempts():
    calls=[];clock=[0]
    def fetch(*a,**k):calls.append(1);raise warming()
    with pytest.raises(HTTPError):
        get_catalog('https://fixture.invalid','/api/catalog',opener=fetch,
            sleep=lambda seconds:clock.__setitem__(0,clock[0]+seconds),clock=lambda:clock[0])
    assert len(calls)==6 and clock[0]==5


def test_read_only_search_retries_busy_without_losing_body_or_weakening_success():
    import json
    calls=[];clock=[0];body={'query':'BMW','condition':'both','page_size':10}
    def fetch(req,timeout):
        calls.append(req)
        assert req.full_url=='https://fixture.invalid/api/search' and req.method=='POST'
        assert json.loads(req.data)==body and timeout<=10
        if len(calls)==1:raise warming()
        response=BytesIO(b'{"ok":true,"mode":"inventory_partial","results":[]}');response.status=200
        return response
    result=post_search('https://fixture.invalid',body,opener=fetch,
        sleep=lambda seconds:clock.__setitem__(0,clock[0]+seconds),clock=lambda:clock[0])
    assert result['ok'] is True and result['mode']=='inventory_partial'
    assert len(calls)==2 and calls[0].data==calls[1].data


def test_search_failure_without_retry_after_is_not_suppressed():
    calls=[]
    def fetch(*a,**k):calls.append(1);raise warming(503,None)
    with pytest.raises(HTTPError):post_search('https://fixture.invalid',{'query':'BMW'},opener=fetch)
    assert calls==[1]
