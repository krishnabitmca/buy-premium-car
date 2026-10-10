"""Start the local preview with server-only settings from the ignored .env file."""
from pathlib import Path
import os
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {
    'SOURCE_INTELLIGENCE_DATABASE_URL', 'SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY',
    'CARSCANNER_INVENTORY_FIRST', 'CARSCANNER_ALLOW_LIVE_COVERAGE_FALLBACK',
    'CARSCANNER_MAX_PAGES_PER_SOURCE', 'HOST', 'PORT',
}

def load_env():
    env_file = ROOT / '.env'
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8-sig').splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            key, separator, value = line.partition('=')
            if separator and key.strip() in ALLOWED:
                os.environ.setdefault(key.strip(), value.strip().strip('\"\''))
def main():
    load_env()
    os.environ.setdefault('HOST', '127.0.0.1')
    os.environ.setdefault('PORT', '8000')
    os.environ.setdefault('CARSCANNER_ALLOW_LIVE_COVERAGE_FALLBACK', 'false')
    if not os.environ.get('SOURCE_INTELLIGENCE_DATABASE_URL'):
        raise SystemExit('Set SOURCE_INTELLIGENCE_DATABASE_URL in .env before starting.')
    sys.path.insert(0, str(ROOT))
    runpy.run_path(str(ROOT / 'render_server.py'), run_name='__main__')

if __name__ == '__main__':
    main()
