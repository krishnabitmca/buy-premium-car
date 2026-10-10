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


@pytest.mark.parametrize('module',['src.inventory_refresh_planner','src.inventory_refresh_worker'])
def test_refresh_command_fails_when_database_configuration_is_missing(module):
    env={k:v for k,v in os.environ.items() if k not in {'SOURCE_INTELLIGENCE_DATABASE_URL','DATABASE_URL','CARSCANNER_DATABASE_URL'}}
    result=subprocess.run([sys.executable,'-m',module,'--limit','1'],env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode!=0
    assert 'Set SOURCE_INTELLIGENCE_DATABASE_URL or DATABASE_URL' in result.stderr
