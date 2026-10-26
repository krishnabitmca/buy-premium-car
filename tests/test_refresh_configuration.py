import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from src.source_registry_db import database_url


def test_scheduled_refresh_exports_the_database_variable_read_by_runtime(monkeypatch):
    workflow=yaml.safe_load(Path('.github/workflows/inventory-refresh-scheduler.yml').read_text(encoding='utf-8'))
    steps=workflow['jobs']['schedule']['steps']
    refresh_steps=[s for s in steps if s.get('name') in {'Schedule refresh work','Process refresh work'}]
    assert len(refresh_steps)==2
    for step in refresh_steps:
        monkeypatch.delenv('SOURCE_INTELLIGENCE_DATABASE_URL',raising=False)
        monkeypatch.delenv('DATABASE_URL',raising=False)
        for key in step['env']:
            if 'DATABASE_URL' in key:
                monkeypatch.setenv(key,'postgresql://example.invalid/test')
        assert database_url()=='postgresql://example.invalid/test'


@pytest.mark.parametrize('module',['src.inventory_refresh_planner','src.inventory_refresh_worker','src.inventory_service'])
def test_refresh_command_fails_when_database_configuration_is_missing(module):
    env={k:v for k,v in os.environ.items() if k not in {'SOURCE_INTELLIGENCE_DATABASE_URL','DATABASE_URL','CARSCANNER_DATABASE_URL'}}
    result=subprocess.run([sys.executable,'-m',module,'--limit','1'],env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode!=0
    assert 'Set SOURCE_INTELLIGENCE_DATABASE_URL or DATABASE_URL' in result.stderr


class _RecordingConnection:
    """Minimal DB stub for asserting the production SQL claim contract."""

    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self

    def execute(self, sql, params):
        self.statements.append((sql, params))

    def fetchall(self):
        return []

    def commit(self):
        pass


def test_inventory_claim_respects_adapter_circuit_cooldown(monkeypatch):
    from src.inventory_refresh_worker import claim_jobs

    conn = _RecordingConnection()
    monkeypatch.setattr('src.inventory_refresh_worker.enabled', lambda: True)
    monkeypatch.setattr('src.inventory_refresh_worker._connect', lambda: conn)
    assert claim_jobs(3) == []
    sql, params = conn.statements[0]
    assert "sa.status='verified'" in sql
    assert "coalesce(sa.circuit_state,'closed') in ('closed','half_open')" in sql
    assert "sa.circuit_state='open' and sa.next_retry_at is not null" in sql
    assert "sa.next_retry_at<=now()" in sql
    assert 'for update of q skip locked' in sql
    assert sql.count('%s') == len(params)


def test_failed_adapter_backoff_is_bounded_and_success_resets_it(monkeypatch):
    from src.source_adapters import record_adapter_execution

    conn = _RecordingConnection()
    monkeypatch.setattr('src.source_adapters.registry_db_enabled', lambda: True)
    monkeypatch.setattr('src.source_adapters.registry_connect', lambda: conn)
    record_adapter_execution('Test Source', success=False, error='HTTP 403')
    sql, params = conn.statements[-1]
    assert 'least(360,' in sql
    assert 'power(2,least(5,greatest(0,' in sql
    assert 'consecutive_failures+1-%s' in sql
    assert sql.count('%s') == len(params)
    assert params[-2:] == (3, 'Test Source')

    record_adapter_execution('Test Source', success=True)
    sql, params = conn.statements[-1]
    assert "circuit_state='closed'" in sql
    assert 'next_retry_at=null' in sql
    assert sql.count('%s') == len(params)


def test_open_circuit_allows_probe_only_after_retry_time(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from src.source_adapters import adapter_execution_allowed

    now = datetime.now(timezone.utc)
    health = {'status': 'verified', 'circuit_state': 'open',
              'next_retry_at': now + timedelta(hours=1)}
    monkeypatch.setattr('src.source_adapters._health_snapshot', lambda _: health)
    assert not adapter_execution_allowed('Test Source')
    health['next_retry_at'] = now - timedelta(minutes=1)
    assert adapter_execution_allowed('Test Source')
    health['circuit_state'] = 'closed'
    assert adapter_execution_allowed('Test Source')


def test_scheduled_refresh_uses_only_canonical_production_inventory_database():
    """Scheduled ingestion, lifecycle, coverage and indexing must never silently target a test DB."""
    workflow_text = Path('.github/workflows/inventory-refresh-scheduler.yml').read_text(encoding='utf-8')
    workflow = yaml.safe_load(workflow_text)
    steps = workflow['jobs']['schedule']['steps']
    db_steps = [step for step in steps if 'SOURCE_INTELLIGENCE_DATABASE_URL' in step.get('env', {})]
    assert len(db_steps) >= 6
    for step in db_steps:
        assert step['env']['SOURCE_INTELLIGENCE_DATABASE_URL'] == '${{ secrets.SOURCE_INTELLIGENCE_DATABASE_URL }}', step['name']
    assert 'secrets.CARSCANNER_FREE_TEST_DATABASE_URL' not in workflow_text
