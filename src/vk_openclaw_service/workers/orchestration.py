"""Worker-level mapping from processing outcomes to checkpoint transitions."""

from __future__ import annotations

from vk_openclaw_service.domain.checkpoints import (
    MessageDisposition,
    ProcessingDecision,
    CheckpointState,
    apply_message_result,
)
from vk_openclaw_service.infra.vk.transport import VkDeliveryOutcome


def finalize_message_processing(
    state: CheckpointState,
    *,
    handler_failed: bool,
    delivery_outcome: VkDeliveryOutcome | None,
    dead_letter_persisted: bool,
) -> CheckpointState:
    if not handler_failed:
        return apply_message_result(
            state,
            ProcessingDecision(disposition=MessageDisposition.PROCESSED),
        )

    if delivery_outcome is VkDeliveryOutcome.RETRY:
        return apply_message_result(
            state,
            ProcessingDecision(
                disposition=MessageDisposition.RETRY,
                reason="delivery_retry_required",
                degrade_worker=True,
            ),
        )

    if dead_letter_persisted or delivery_outcome is VkDeliveryOutcome.REJECT:
        return apply_message_result(
            state,
            ProcessingDecision(
                disposition=MessageDisposition.DEAD_LETTERED,
                reason="message_handling_failed",
                dead_letter_persisted=True if delivery_outcome is VkDeliveryOutcome.REJECT else dead_letter_persisted,
            ),
        )

    return apply_message_result(
        state,
        ProcessingDecision(
            disposition=MessageDisposition.RETRY,
            reason="message_retry_required",
            degrade_worker=False,
        ),
    )
