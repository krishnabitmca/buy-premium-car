import io
import json
import pytest
from src import buyer_ai


def test_no_consent_does_not_contact_provider_or_consume_quota(monkeypatch):
    monkeypatch.setattr(buyer_ai,'reserve_call',lambda:pytest.fail('No quota without consent'))
    with pytest.raises(ValueError,match='Opt in'):
        buyer_ai.interpret('BMW under 40 lakh')


@pytest.mark.parametrize('prompt',['Call me 9876543210 for BMW','BMW contact buyer@example.com','BMW https://private.invalid'])
def test_contact_or_private_links_are_not_sent(prompt,monkeypatch):
    monkeypatch.setattr(buyer_ai,'reserve_call',lambda:pytest.fail('Private input was submitted'))
    with pytest.raises(ValueError,match='Remove'):
        buyer_ai.interpret(prompt,consent=True)


def configured(monkeypatch):
    monkeypatch.setenv('CARSCANNER_AI_ENABLED','true')
    monkeypatch.setenv('GEMINI_API_KEY','synthetic-key-not-a-credential')
    monkeypatch.setattr(buyer_ai,'reserve_call',lambda:None)


def test_generated_intent_is_validated_and_requires_buyer_review(monkeypatch):
    configured(monkeypatch)
    output={'intent':{'query':'BMW','fuels':['petrol'],'max_mileage_km':40000,'budget_max':40,
                      'destination':'Bengaluru'},'unverified_criteria':['accident history'],'clarifications':[]}
    def provider(request,timeout):
        assert timeout==8
        assert 'key=' not in request.full_url
        assert request.get_header('X-goog-api-key')=='synthetic-key-not-a-credential'
        return io.BytesIO(json.dumps({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(output)}]}}]}).encode())
    monkeypatch.setattr(buyer_ai,'urlopen',provider)
    result=buyer_ai.interpret('Petrol BMW under 40 lakh, less than 40000 km, registering in Bengaluru, accident-free',consent=True)
    assert result['intent']['seller_city']==''
    assert result['intent']['max_mileage_km']==40000
    assert result['requires_review'] and not result['inventory_facts_generated']
    assert result['unverified_criteria']==['accident history']


def test_provider_failure_never_exposes_key_or_prompt(monkeypatch):
    configured(monkeypatch)
    def fail(*args,**kwargs):
        raise RuntimeError('synthetic-key-not-a-credential private prompt')
    monkeypatch.setattr(buyer_ai,'urlopen',fail)
    with pytest.raises(buyer_ai.AIUnavailable) as error:
        buyer_ai.interpret('BMW under 40 lakh',consent=True)
    assert 'synthetic-key' not in str(error.value) and 'private prompt' not in str(error.value)


def test_model_cannot_supply_inventory_or_unbounded_parameters(monkeypatch):
    configured(monkeypatch)
    output={'intent':{'query':'BMW','inventory':[{'price':1}]}}
    monkeypatch.setattr(buyer_ai,'urlopen',lambda *a,**k:io.BytesIO(json.dumps({'candidates':[
        {'finishReason':'STOP','content':{'parts':[{'text':json.dumps(output)}]}}]}).encode()))
    with pytest.raises(buyer_ai.AIUnavailable):
        buyer_ai.interpret('BMW under 40 lakh',consent=True)
