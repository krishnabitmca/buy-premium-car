import shutil
import subprocess
import pytest


@pytest.mark.skipif(shutil.which('node') is None,reason='Node required for service-worker contract checks')
def test_public_shell_cache_boundaries():
    subprocess.run(['node','--test','tests/public_shell.test.js'],check=True,timeout=15)
