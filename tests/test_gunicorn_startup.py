"""Regression tests for low-resource web startup behavior."""
import importlib.util
from pathlib import Path
from unittest.mock import Mock, patch


def load_config():
    spec = importlib.util.spec_from_file_location(
        "carscanner_gunicorn_config", Path(__file__).resolve().parents[1] / "gunicorn.conf.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_web_startup_does_not_launch_crawler_by_default():
    config = load_config()
    server = Mock()
    with patch.dict("os.environ", {"SOURCE_INTELLIGENCE_DATABASE_URL": "postgresql://example"}, clear=True):
        with patch("subprocess.Popen") as popen:
            config.on_starting(server)
    popen.assert_not_called()


def test_explicit_startup_refresh_remains_available():
    config = load_config()
    server = Mock()
    with patch.dict("os.environ", {
        "SOURCE_INTELLIGENCE_DATABASE_URL": "postgresql://example",
        "CARSCANNER_STARTUP_REFRESH": "true",
    }, clear=True):
        with patch("subprocess.Popen") as popen:
            config.on_starting(server)
    popen.assert_called_once()
    assert popen.call_args.args[0][-2:] == ["--limit", "10"]
