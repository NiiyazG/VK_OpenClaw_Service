"""Repository-backed worker message cycle."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from vk_openclaw_service.domain.checkpoints import begin_processing
from vk_openclaw_service.infra.repositories.checkpoints import InMemoryCheckpointRepository
from vk_openclaw_service.infra.vk.transport import VkDeliveryOutcome
from vk_openclaw_service.services.delivery_service import deliver_reply
from vk_openclaw_service.services.message_service import process_message
from vk_openclaw_service.workers.orchestration import finalize_message_processing


class AuditRepository(Protocol):
    def append_event(
        self,
        *,
        event_type: str,
        peer_id: int | None,
        status: str,
        details: dict[str, object],
    ) -> object: ...


class DeadLetterRepository(Protocol):
    def append_dead_letter(
        self,
        *,
        peer_id: int,
        message_id: int,
        reason: str,
        attempt: int,
        priority: str | None = None,
        text: str,
        details: dict[str, object],
    ) -> object: ...


class RateLimiter(Protocol):
    def allow(self, *, peer_id: int, bucket: str) -> bool: ...


class ReplayGuard(Protocol):
    def claim(self, *, peer_id: int, message_id: int) -> bool: ...


class RetryQueue(Protocol):
    def enqueue_message(
        self,
        *,
        peer_id: int,
        message_id: int,
        text: str,
        paired: bool,
        reason: str,
        attempt: int = 1,
    ) -> None: ...


class PairingVerifier(Protocol):
    def __call__(self, peer_id: int, code: str) -> dict: ...


class WorkerService:
    def __init__(
        self,
        *,
        checkpoint_repository: InMemoryCheckpointRepository,
        delivery_classifier: Callable[[Exception], VkDeliveryOutcome],
        openclaw_runner: Callable[[str], str],
        reply_sender: Callable[[int, str], object],
        audit_repository: AuditRepository | None = None,
        dead_letter_repository: DeadLetterRepository | None = None,
        rate_limiter: RateLimiter | None = None,
        replay_guard: ReplayGuard | None = None,
        retry_queue: RetryQueue | None = None,
        pairing_verifier: PairingVerifier | None = None,
        retry_queue_max_attempts: int = 3,
        free_text_ask_enabled: bool = False,
    ) -> None:
        self.checkpoint_repository = checkpoint_repository
        self.delivery_classifier = delivery_classifier
        self.openclaw_runner = openclaw_runner
        self.reply_sender = reply_sender
        self.audit_repository = audit_repository
        self.dead_letter_repository = dead_letter_repository
        self.rate_limiter = rate_limiter
        self.replay_guard = replay_guard
        self.retry_queue = retry_queue
        self.pairing_verifier = pairing_verifier
        self.retry_queue_max_attempts = retry_queue_max_attempts
        self.free_text_ask_enabled = free_text_ask_enabled

    def process_message(
        self,
        *,
        peer_id: int,
        message_id: int,
        text: str,
        paired: bool,
        status_payload: dict,
        skip_replay_guard: bool = False,
        retry_attempt: int = 0,
    ) -> dict:
        if not skip_replay_guard and self.replay_guard is not None and not self.replay_guard.claim(peer_id=peer_id, message_id=message_id):
            self._append_audit_event(
                event_type="message_duplicate_skipped",
                peer_id=peer_id,
                status="ok",
                details={"message_id": message_id},
            )
            return {"action": "ignored", "reason": "duplicate_message"}
        state = self.checkpoint_repository.get_or_create(peer_id)
        state = begin_processing(state, message_id)
        try:
            result = process_message(
                peer_id=peer_id,
                text=text,
                paired=paired,
                status_payload=status_payload,
                openclaw_runner=self.openclaw_runner,
                rate_limiter=self.rate_limiter,
                free_text_ask_enabled=self.free_text_ask_enabled,
            )
            if result["action"] == "pair":
                code = str(result.get("code", "")).strip()
                if not code or self.pairing_verifier is None:
                    result = {"action": "reply", "reply": "Invalid or expired pairing code."}
                    self._append_audit_event(
                        event_type="pairing_failed_via_vk",
                        peer_id=peer_id,
                        status="failed",
                        details={"message_id": message_id, "reason": "invalid_pairing_code"},
                    )
                else:
                    try:
                        self.pairing_verifier(peer_id, code)
                        result = {"action": "reply", "reply": "Pairing successful."}
                        self._append_audit_event(
                            event_type="pairing_verified_via_vk",
                            peer_id=peer_id,
                            status="ok",
                            details={"message_id": message_id},
                        )
                    except Exception:
                        result = {"action": "reply", "reply": "Invalid or expired pairing code."}
                        self._append_audit_event(
                            event_type="pairing_failed_via_vk",
                            peer_id=peer_id,
                            status="failed",
                            details={"message_id": message_id, "reason": "invalid_pairing_code"},
                        )
            if result["action"] == "reply":
                delivery_outcome = deliver_reply(
                    sender=self,
                    peer_id=peer_id,
                    text=result["reply"],
                    classify_failure=self.delivery_classifier,
                )
                if delivery_outcome is not None:
                    state = finalize_message_processing(
                        state,
                        handler_failed=True,
                        delivery_outcome=delivery_outcome,
                        dead_letter_persisted=False,
                    )
                    self.checkpoint_repository.save(state)
                    self._append_audit_event(
                        event_type="message_delivery_retry" if delivery_outcome is VkDeliveryOutcome.RETRY else "message_delivery_rejected",
                        peer_id=peer_id,
                        status="degraded",
                        details={"message_id": message_id, "outcome": delivery_outcome.value},
                    )
                    if delivery_outcome is VkDeliveryOutcome.RETRY:
                        if self._retry_budget_exhausted(retry_attempt):
                            dead_letter_persisted = self._append_dead_letter(
                                peer_id=peer_id,
                                message_id=message_id,
                                reason="retry_budget_exhausted",
                                attempt=retry_attempt,
                                text=text,
                                details={"outcome": delivery_outcome.value},
                            )
                            state = finalize_message_processing(
                                state,
                                handler_failed=True,
                                delivery_outcome=None,
                                dead_letter_persisted=dead_letter_persisted,
                            )
                            self.checkpoint_repository.save(state)
                            self._append_audit_event(
                                event_type="message_dead_lettered",
                                peer_id=peer_id,
                                status="failed",
                                details={
                                    "message_id": message_id,
                                    "reason": "retry_budget_exhausted",
                                    "attempt": retry_attempt,
                                },
                            )
                            return {"action": "dead_letter", "reason": "retry_budget_exhausted"}
                        self._enqueue_retry(
                            peer_id=peer_id,
                            message_id=message_id,
                            text=text,
                            paired=paired,
                            reason="delivery_retry_required",
                            attempt=retry_attempt + 1,
                        )
                        return {"action": "retry", "reason": "delivery_retry_required"}
                    return result
            state = finalize_message_processing(
                state,
                handler_failed=False,
                delivery_outcome=None,
                dead_letter_persisted=False,
            )
            self.checkpoint_repository.save(state)
            self._append_audit_event(
                event_type="message_processed",
                peer_id=peer_id,
                status="ok",
                details={"message_id": message_id, "action": result["action"]},
            )
            return result
        except Exception as exc:
            delivery_outcome = self.delivery_classifier(exc)
            if delivery_outcome is VkDeliveryOutcome.RETRY:
                if self._retry_budget_exhausted(retry_attempt):
                    dead_letter_persisted = self._append_dead_letter(
                        peer_id=peer_id,
                        message_id=message_id,
                        reason="retry_budget_exhausted",
                        attempt=retry_attempt,
                        text=text,
                        details={"outcome": delivery_outcome.value, "error": str(exc)},
                    )
                    state = finalize_message_processing(
                        state,
                        handler_failed=True,
                        delivery_outcome=None,
                        dead_letter_persisted=dead_letter_persisted,
                    )
                    self.checkpoint_repository.save(state)
                    self._append_audit_event(
                        event_type="message_processing_failed",
                        peer_id=peer_id,
                        status="degraded",
                        details={
                            "message_id": message_id,
                            "error": str(exc),
                            "outcome": delivery_outcome.value,
                        },
                    )
                    self._append_audit_event(
                        event_type="message_dead_lettered",
                        peer_id=peer_id,
                        status="failed",
                        details={
                            "message_id": message_id,
                            "reason": "retry_budget_exhausted",
                            "attempt": retry_attempt,
                            "error": str(exc),
                        },
                    )
                    return {"action": "dead_letter", "reason": "retry_budget_exhausted"}
                state = finalize_message_processing(
                    state,
                    handler_failed=True,
                    delivery_outcome=delivery_outcome,
                    dead_letter_persisted=False,
                )
                self.checkpoint_repository.save(state)
                self._append_audit_event(
                    event_type="message_processing_failed",
                    peer_id=peer_id,
                    status="degraded",
                    details={
                        "message_id": message_id,
                        "error": str(exc),
                        "outcome": delivery_outcome.value,
                    },
                )
                self._enqueue_retry(
                    peer_id=peer_id,
                    message_id=message_id,
                    text=text,
                    paired=paired,
                    reason="delivery_retry_required",
                    attempt=retry_attempt + 1,
                )
                return {"action": "retry", "reason": "delivery_retry_required"}
            state = finalize_message_processing(
                state,
                handler_failed=True,
                delivery_outcome=delivery_outcome,
                dead_letter_persisted=False,
            )
            self.checkpoint_repository.save(state)
            self._append_audit_event(
                event_type="message_processing_failed",
                peer_id=peer_id,
                status="degraded",
                details={
                    "message_id": message_id,
                    "error": str(exc),
                    "outcome": delivery_outcome.value,
                },
            )
            return {"action": "reply", "reply": str(exc)}

    def send_text(self, peer_id: int, text: str) -> int:
        result = self.reply_sender(peer_id, text)
        if result is None:
            return 0
        if not isinstance(result, int):
            raise ValueError("reply_sender_returned_non_int_message_id")
        return result

    def _append_audit_event(
        self,
        *,
        event_type: str,
        peer_id: int,
        status: str,
        details: dict[str, object],
    ) -> None:
        if self.audit_repository is None:
            return
        self.audit_repository.append_event(
            event_type=event_type,
            peer_id=peer_id,
            status=status,
            details=details,
        )

    def _enqueue_retry(
        self,
        *,
        peer_id: int,
        message_id: int,
        text: str,
        paired: bool,
        reason: str,
        attempt: int,
    ) -> None:
        if self.retry_queue is None:
            return
        self.retry_queue.enqueue_message(
            peer_id=peer_id,
            message_id=message_id,
            text=text,
            paired=paired,
            reason=reason,
            attempt=attempt,
        )

    def _retry_budget_exhausted(self, retry_attempt: int) -> bool:
        return retry_attempt >= self.retry_queue_max_attempts

    def _append_dead_letter(
        self,
        *,
        peer_id: int,
        message_id: int,
        reason: str,
        attempt: int,
        text: str,
        details: dict[str, object],
    ) -> bool:
        if self.dead_letter_repository is None:
            return False
        self.dead_letter_repository.append_dead_letter(
            peer_id=peer_id,
            message_id=message_id,
            reason=reason,
            attempt=attempt,
            text=text,
            details=details,
        )
        return True
