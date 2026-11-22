"""Regression tests for preventing web restarts from duplicating scheduled crawls."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch


def _load_config():
    path = Path(__file__).resolve().parents[1] / 'gunicorn.conf.py'
    spec = importlib.util.spec_from_file_location('carscanner_gunicorn_config', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_web_start_does_not_spawn_refresh_by_default(monkeypatch):
    monkeypatch.delenv('CARSCANNER_STARTUP_REFRESH', raising=False)
    monkeypatch.setenv('SOURCE_INTELLIGENCE_DATABASE_URL', 'postgresql://unused.example/db')
    with patch('subprocess.Popen') as popen:
        _load_config().on_starting(MagicMock())
    popen.assert_not_called()


def test_explicit_opt_in_requires_production_database(monkeypatch):
    monkeypatch.setenv('CARSCANNER_STARTUP_REFRESH', 'true')
    monkeypatch.delenv('SOURCE_INTELLIGENCE_DATABASE_URL', raising=False)
    monkeypatch.setenv('CARSCANNER_FREE_TEST_DATABASE_URL', 'postgresql://test.example/db')
    with patch('subprocess.Popen') as popen:
        _load_config().on_starting(MagicMock())
    popen.assert_not_called()


def test_explicit_opt_in_runs_one_bounded_refresh(monkeypatch):
    monkeypatch.setenv('CARSCANNER_STARTUP_REFRESH', '1')
    monkeypatch.setenv('SOURCE_INTELLIGENCE_DATABASE_URL', 'postgresql://unused.example/db')
    monkeypatch.delenv('CARSCANNER_MAX_PAGES_PER_SOURCE', raising=False)
    with patch('subprocess.Popen') as popen:
        _load_config().on_starting(MagicMock())
    popen.assert_called_once()
    args, kwargs = popen.call_args
    assert args[0][-3:] == ['src.inventory_refresh_worker', '--limit', '10']
    assert kwargs['env']['CARSCANNER_MAX_PAGES_PER_SOURCE'] == '10'
    assert kwargs['start_new_session'] is True


def test_disabled_string_does_not_enable_refresh(monkeypatch):
    monkeypatch.setenv('CARSCANNER_STARTUP_REFRESH', 'false')
    monkeypatch.setenv('SOURCE_INTELLIGENCE_DATABASE_URL', 'postgresql://unused.example/db')
    with patch('subprocess.Popen') as popen:
        _load_config().on_starting(MagicMock())
    popen.assert_not_called()
