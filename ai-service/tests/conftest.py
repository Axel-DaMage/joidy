"""Shared pytest fixtures for ai-service tests.

Sets safe environment defaults BEFORE any service module is imported so tests
never require a real database or API keys:

- ``DATABASE_URL`` points at an in-memory SQLite database so ``database.py``
  can build its engine without psycopg2/PostgreSQL (engine creation does not
  connect anyway; all DB-touching functions are mocked in tests).
- Provider API keys are cleared so ``settings.is_ai_enabled`` is deterministic
  unless a test explicitly configures a provider.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# Make the service root importable when pytest is invoked from the repo root
# (pyproject.toml already covers this via pythonpath, but this keeps the tests
# runnable with a bare `pytest` from inside ai-service/ too).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import rate_limiter
from circuit_breaker import CircuitState, emb_circuit_breaker, llm_circuit_breaker
from clients.factory import ClientFactory
from response_cache import get_cache


def _reset_health_probe() -> None:
    """Clear the /health provider-reachability probe cache (#1460).

    Cached in ``main`` with a TTL — importing lazily so non-endpoint test
    files don't pay for the FastAPI import.
    """
    try:
        import main

        main.reset_health_probe_cache()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _reset_shared_state():
    """Reset module-level singletons so tests never leak state.

    The circuit breakers, client factory cache, response cache and named
    rate limiters are global singletons in the service; a failure recorded
    by one test would otherwise poison the next (and a reused limiter's
    asyncio.Lock could be bound to another test's event loop).
    """
    ClientFactory.reset()
    _reset_health_probe()
    for breaker in (llm_circuit_breaker, emb_circuit_breaker):
        breaker.state = CircuitState.CLOSED
        breaker.failures = 0
        breaker.last_failure_time = 0.0
        breaker.last_success_time = 0.0
    get_cache().clear()
    rate_limiter._limiters.clear()
    rate_limiter._local_limiters.clear()
    yield
    ClientFactory.reset()
    _reset_health_probe()
    for breaker in (llm_circuit_breaker, emb_circuit_breaker):
        breaker.state = CircuitState.CLOSED
        breaker.failures = 0
        breaker.last_failure_time = 0.0
        breaker.last_success_time = 0.0
    get_cache().clear()
    rate_limiter._limiters.clear()
    rate_limiter._local_limiters.clear()
