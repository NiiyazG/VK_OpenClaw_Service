from vk_openclaw_service.infra.vk.transport import (
    VkApiError,
    VkDeliveryOutcome,
    classify_vk_send_failure,
)


def test_timeout_is_retryable() -> None:
    outcome = classify_vk_send_failure(TimeoutError("timed out"))

    assert outcome is VkDeliveryOutcome.RETRY


def test_connection_error_is_retryable() -> None:
    outcome = classify_vk_send_failure(ConnectionError("connection reset"))

    assert outcome is VkDeliveryOutcome.RETRY


def test_rate_limit_is_retryable() -> None:
    outcome = classify_vk_send_failure(VkApiError(code=6, message="too many requests"))

    assert outcome is VkDeliveryOutcome.RETRY


def test_internal_server_error_is_retryable() -> None:
    outcome = classify_vk_send_failure(VkApiError(code=10, message="internal server error"))

    assert outcome is VkDeliveryOutcome.RETRY


def test_permission_error_is_rejected() -> None:
    outcome = classify_vk_send_failure(VkApiError(code=901, message="can't send messages"))

    assert outcome is VkDeliveryOutcome.REJECT


def test_unknown_api_error_defaults_to_reject() -> None:
    outcome = classify_vk_send_failure(VkApiError(code=9999, message="unexpected"))

    assert outcome is VkDeliveryOutcome.REJECT
