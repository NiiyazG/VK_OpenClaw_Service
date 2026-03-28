from vk_openclaw_service.infra.vk.transport import VkDeliveryOutcome
from vk_openclaw_service.services.delivery_service import deliver_reply


class FakeSender:
    def __init__(self, fail: Exception | None = None) -> None:
        self.fail = fail
        self.sent: list[tuple[int, str]] = []

    def send_text(self, peer_id: int, text: str) -> int:
        if self.fail is not None:
            raise self.fail
        self.sent.append((peer_id, text))
        return 1


def test_deliver_reply_sends_message_and_returns_none_on_success() -> None:
    sender = FakeSender()

    outcome = deliver_reply(
        sender=sender,
        peer_id=42,
        text="hello",
        classify_failure=lambda exc: VkDeliveryOutcome.REJECT,
    )

    assert outcome is None
    assert sender.sent == [(42, "hello")]


def test_deliver_reply_returns_retry_outcome_on_retryable_failure() -> None:
    sender = FakeSender(fail=TimeoutError("timed out"))

    outcome = deliver_reply(
        sender=sender,
        peer_id=42,
        text="hello",
        classify_failure=lambda exc: VkDeliveryOutcome.RETRY,
    )

    assert outcome is VkDeliveryOutcome.RETRY
