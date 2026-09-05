import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app import middleware, ratelimit
    middleware.reset()
    ratelimit._buckets.clear()
    yield
    middleware.reset()
    ratelimit._buckets.clear()
