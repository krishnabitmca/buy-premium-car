"""Execute the actual browser read-only overload helper with deterministic fetches."""
import shutil
import subprocess
import pytest


@pytest.mark.skipif(shutil.which('node') is None, reason='Node is required for browser helper verification')
def test_read_only_fetch_overload_contract():
    subprocess.run(['node', '--test', 'tests/read_only_fetch.test.js'], check=True, timeout=15)
