from vk_openclaw_service.services.rate_limit import FixedWindowRateLimiter, InMemoryCounterStore


def test_fixed_window_rate_limiter_allows_until_limit() -> None:
    limiter = FixedWindowRateLimiter(store=InMemoryCounterStore(), limit=2)

    assert limiter.allow(peer_id=42, bucket="openclaw") is True
    assert limiter.allow(peer_id=42, bucket="openclaw") is True
    assert limiter.allow(peer_id=42, bucket="openclaw") is False


def test_fixed_window_rate_limiter_isolated_by_bucket_and_peer() -> None:
    limiter = FixedWindowRateLimiter(store=InMemoryCounterStore(), limit=1)

    assert limiter.allow(peer_id=42, bucket="openclaw") is True
    assert limiter.allow(peer_id=43, bucket="openclaw") is True
    assert limiter.allow(peer_id=42, bucket="status") is True
