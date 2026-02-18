"""Service-layer job state transition validator."""

from __future__ import annotations

from src.contracts.result import Result, failure, success

ALLOWED_STATES = {"queued", "running", "paused", "failed", "completed"}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "failed"},
    "running": {"paused", "failed", "completed"},
    "paused": {"running", "failed"},
    "failed": {"running"},  # Allow retry from failed state
    "completed": set(),
}


def validate_job_state_transition(current_state: str, next_state: str) -> Result[None]:
    if current_state not in ALLOWED_STATES:
        return failure(
            code="invalid_job_state",
            message="Current job state is invalid",
            details={"current_state": current_state},
            retryable=False,
        )

    if next_state not in ALLOWED_STATES:
        return failure(
            code="invalid_job_state",
            message="Target job state is invalid",
            details={"next_state": next_state},
            retryable=False,
        )

    if next_state not in ALLOWED_TRANSITIONS[current_state]:
        return failure(
            code="invalid_job_transition",
            message="Job state transition is not allowed",
            details={"current_state": current_state, "next_state": next_state},
            retryable=False,
        )

    return success(None)
