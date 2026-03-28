from vk_openclaw_service.services.replay_guard import InMemoryReplayStore, ReplayGuard


def test_replay_guard_allows_first_claim_and_blocks_duplicate() -> None:
    guard = ReplayGuard(store=InMemoryReplayStore(), ttl_seconds=300)

    assert guard.claim(peer_id=42, message_id=8) is True
    assert guard.claim(peer_id=42, message_id=8) is False


def test_replay_guard_isolated_by_peer_and_message() -> None:
    guard = ReplayGuard(store=InMemoryReplayStore(), ttl_seconds=300)

    assert guard.claim(peer_id=42, message_id=8) is True
    assert guard.claim(peer_id=42, message_id=9) is True
    assert guard.claim(peer_id=43, message_id=8) is True
