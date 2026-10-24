"""Small-instance defaults; scale only after measuring memory and DB budgets."""
import os


def bounded_int(name, default, minimum, maximum):
    value = int(os.getenv(name, str(default)))
    if not minimum <= value <= maximum:
        raise ValueError(f'{name} must be between {minimum} and {maximum}')
    return value


bind = os.getenv('HOST', '0.0.0.0') + ':' + str(bounded_int('PORT', 10000, 1, 65535))
workers = bounded_int('CARSCANNER_WEB_WORKERS', 1, 1, 4)
threads = bounded_int('CARSCANNER_WEB_THREADS', 4, 1, 16)
worker_class = 'gthread'
worker_connections = 32
backlog = 128
timeout = 45  # Worker heartbeat timeout; not a per-request wall-clock deadline.
graceful_timeout = 25
keepalive = 2
max_requests = 2000
max_requests_jitter = 200
preload_app = False  # Database pools and background executors must be worker-local.
accesslog = '-'
access_log_format = '%(m)s status=%(s)s duration_ms=%(M)s'
errorlog = '-'
loglevel = 'info'


def worker_exit(server, worker):
    from src.source_registry_db import close_connection_pool
    close_connection_pool()


def on_starting(server):
    """One bounded recovery batch on web deployment, independent of cron timing.

    Run as a child process so a slow source cannot block the web server startup.
    Production database configuration is inherited; failures appear in Render logs.
    """
    import subprocess
    import sys
    if not (os.getenv('CARSCANNER_FREE_TEST_DATABASE_URL') or os.getenv('SOURCE_INTELLIGENCE_DATABASE_URL')):
        server.log.warning('Skipping startup crawler: database connection not configured')
        return
    env = os.environ.copy()
    if not env.get('SOURCE_INTELLIGENCE_DATABASE_URL'):
        env['SOURCE_INTELLIGENCE_DATABASE_URL'] = env['CARSCANNER_FREE_TEST_DATABASE_URL']
    env.setdefault('CARSCANNER_MAX_PAGES_PER_SOURCE', '10')
    server.log.info('Launching immediate bounded inventory refresh on deployment')
    subprocess.Popen(
        [sys.executable, '-m', 'src.inventory_refresh_worker', '--limit', '10'],
        env=env, stdout=None, stderr=None, start_new_session=True,
    )
