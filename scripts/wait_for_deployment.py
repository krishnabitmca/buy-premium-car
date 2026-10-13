"""Wait for the released commit before running hosted checks during a rollout."""
import json
import os
import re
import time
import urllib.request


def wait(base, expected, timeout=480):
    if not re.fullmatch(r'[0-9a-f]{40}', expected):
        raise ValueError('Expected deployment SHA must be a full commit hash')
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(base.rstrip('/') + '/api/version', headers={'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=15) as response:
                payload = json.load(response)
            if payload.get('ok') and payload.get('commit') == expected:
                print('Expected release is serving traffic')
                return
        except Exception:
            pass
        time.sleep(10)
    raise RuntimeError('The expected release did not become available before the deployment deadline')


if __name__ == '__main__':
    expected = os.getenv('EXPECTED_DEPLOYMENT_SHA', '')
    if expected:
        wait(os.getenv('CARSCANNER_BASE_URL', 'https://buy-premium-car1.onrender.com'), expected)
    else:
        print('No release SHA requested; checking the current hosted application')
