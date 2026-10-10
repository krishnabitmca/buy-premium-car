from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from scripts import process_alerts as alerts
from src import main as acquisition
from src.inventory_db import iter_inventory
from tests.test_car_watch import listing, watch


def active_watch(**changes):
    value=watch(status='active',frequency='instant',user_id='user-1',name='BMW Watch',
                deal_watch_users={'status':'active','email':'fixture@example.invalid'},
                watch_channel_preferences=[{'channel':'email','enabled':True,
                     'frequency':'instant','consent_at':datetime.now(timezone.utc).isoformat()}])
    value.update(changes)
    return value


def test_background_reader_pages_past_one_batch_and_requires_persistence(monkeypatch):
    monkeypatch.setenv('SOURCE_INTELLIGENCE_DATABASE_URL','postgresql://fixture.invalid/test')
    monkeypatch.setenv('CARSCANNER_INVENTORY_FIRST','false')
    calls=[]
    def read(**kwargs):
        calls.append(kwargs)
        return ([{'vehicle_id':str(i)} for i in range(kwargs['offset'],min(3,kwargs['offset']+2))],[])
    monkeypatch.setattr('src.inventory_db.search_inventory',read)
    assert [len(p) for p in iter_inventory(page_size=2)]==[2,1]
    assert [c['offset'] for c in calls]==[0,2]
    assert all(c['require_persistence'] for c in calls)


def test_watch_reader_pages_without_default_rest_row_limit(monkeypatch):
    paths=[]
    def request(method,path):
        paths.append(path)
        return [{'watch_id':'1'},{'watch_id':'2'}] if 'offset=0' in path else [{'watch_id':'3'}]
    monkeypatch.setattr(alerts,'sb_request',request)
    assert len(list(alerts.active_watches(page_size=2)))==3
    assert 'offset=2' in paths[-1] and 'deal_watch_users.status=eq.active' in paths[0]


def test_database_failure_propagates_without_flat_file_fallback(monkeypatch):
    monkeypatch.setenv('SOURCE_INTELLIGENCE_DATABASE_URL','postgresql://fixture.invalid/test')
    def unavailable(**kwargs):
        raise RuntimeError('database unavailable')
    monkeypatch.setattr(alerts,'iter_inventory',unavailable)
    monkeypatch.setattr(alerts,'active_watches',lambda:iter([active_watch()]))
    with pytest.raises(RuntimeError,match='database unavailable'):
        alerts.process_alerts(dry_run=True)


def test_alert_dry_run_reads_inventory_but_never_writes_or_sends(monkeypatch):
    monkeypatch.setenv('SOURCE_INTELLIGENCE_DATABASE_URL','postgresql://fixture.invalid/test')
    monkeypatch.setattr(alerts,'active_watches',lambda:iter([active_watch()]))
    reader=Mock(return_value=iter([[listing()]]))
    monkeypatch.setattr(alerts,'iter_inventory',reader)
    request=Mock(side_effect=AssertionError('event mutation forbidden in dry run'))
    provider=Mock(side_effect=AssertionError('provider call forbidden in dry run'))
    monkeypatch.setattr(alerts,'sb_request',request)
    monkeypatch.setattr(alerts,'send_resend',provider)
    assert alerts.process_alerts(dry_run=True)=={'matched':1,'sent':0,'failed':0,'dry_run':True}
    assert reader.call_args.kwargs=={'query':'BMW X3','condition':'both'}
    request.assert_not_called()
    provider.assert_not_called()


@pytest.mark.parametrize('change',[
    {'status':'paused'}, {'frequency':'daily'},
    {'deal_watch_users':{'status':'unsubscribed'}},
    {'watch_channel_preferences':[{'enabled':False,'channel':'email','consent_at':'2026-10-10'}]},
    {'watch_channel_preferences':[{'enabled':True,'channel':'email','consent_at':None}]},
    {'watch_channel_preferences':[{'enabled':True,'channel':'email','frequency':'daily','consent_at':'2026-10-10'}]},
])
def test_ineligible_watch_user_or_channel_never_sends(monkeypatch,change):
    monkeypatch.setenv('SOURCE_INTELLIGENCE_DATABASE_URL','postgresql://fixture.invalid/test')
    monkeypatch.setattr(alerts,'active_watches',lambda:iter([active_watch(**change)]))
    monkeypatch.setattr(alerts,'iter_inventory',lambda **kwargs:iter([[listing()]]))
    request=Mock(side_effect=AssertionError('no eligible delivery'))
    monkeypatch.setattr(alerts,'sb_request',request)
    assert alerts.process_alerts()['sent']==0
    request.assert_not_called()


def test_event_identity_changes_on_price_not_observation_timestamp():
    first=listing(price_lakh=30)
    assert alerts.event_type_for(first)==alerts.event_type_for({**first,'observed_at':'later'})
    assert alerts.event_type_for(first)!=alerts.event_type_for({**first,'price_lakh':29})


def test_daily_command_uses_database_cycle_and_streams_optional_export(monkeypatch,tmp_path):
    monkeypatch.setenv('SOURCE_INTELLIGENCE_DATABASE_URL','postgresql://fixture.invalid/test')
    path=tmp_path/'diagnostic.json'
    monkeypatch.setattr('sys.argv',['src.main','--limit','4','--export-json',str(path)])
    runner=Mock(return_value={'scheduled':1,'completed':1,'failed':0})
    monkeypatch.setattr(acquisition,'run_cycle',runner)
    monkeypatch.setattr(acquisition,'iter_inventory',lambda:iter([[listing()]]))
    acquisition.main()
    runner.assert_called_once_with(4)
    assert 'postgres_export' in path.read_text(encoding='utf-8')


@pytest.mark.parametrize('module',['src.main','scripts.process_alerts'])
def test_production_commands_fail_without_database(monkeypatch,module):
    import os,subprocess,sys
    env={k:v for k,v in os.environ.items() if k not in {'SOURCE_INTELLIGENCE_DATABASE_URL','DATABASE_URL'}}
    result=subprocess.run([sys.executable,'-m',module],env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode!=0 and 'Set SOURCE_INTELLIGENCE_DATABASE_URL' in result.stderr
