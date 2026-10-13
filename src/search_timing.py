"""Request-local timings; never record queries, URLs or credentials."""
from contextvars import ContextVar
from functools import wraps
from time import perf_counter

_timings = ContextVar('carscanner_search_timings', default=None)


def record_duration(stage, seconds):
    state = _timings.get()
    if state is not None:
        state['stages'][stage] = state['stages'].get(stage, 0) + seconds * 1000


def measure_call(stage, function, *args, **kwargs):
    started = perf_counter()
    try:
        return function(*args, **kwargs)
    finally:
        record_duration(stage, perf_counter() - started)


def timed_request(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        token = _timings.set({'started': perf_counter(), 'stages': {}})
        try:
            return function(*args, **kwargs)
        finally:
            _timings.reset(token)
    return wrapped


def server_timing():
    state = _timings.get()
    if state is None:
        return None
    stages = dict(state['stages'])
    stages['total'] = (perf_counter() - state['started']) * 1000
    return ', '.join(f'{name};dur={duration:.2f}' for name, duration in stages.items())
