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
    """Only an explicit operator opt-in launches recovery work on web startup.

    Gunicorn also starts on instance restarts and cold wakes, not only deployments.
    The scheduled worker owns normal refresh cadence; spawning a second crawler
    on every web start competes for domain leases and database ingestion locks.
    """
    if os.getenv('CARSCANNER_STARTUP_REFRESH', '').strip().lower() not in {'1', 'true', 'yes'}:
        server.log.info('Skipping startup crawler; scheduled refresh owns inventory cadence')
        return
    if not os.getenv('SOURCE_INTELLIGENCE_DATABASE_URL'):
        server.log.warning('Skipping startup crawler: production database connection not configured')
        return

    import subprocess
    import sys
    env = os.environ.copy()
    env.setdefault('CARSCANNER_MAX_PAGES_PER_SOURCE', '10')
    server.log.info('Launching explicitly enabled bounded inventory refresh')
    subprocess.Popen(
        [sys.executable, '-m', 'src.inventory_refresh_worker', '--limit', '10'],
        env=env, stdout=None, stderr=None, start_new_session=True,
    )
