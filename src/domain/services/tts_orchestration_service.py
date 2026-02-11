"""Stub orchestration service consuming transition validation."""

from __future__ import annotations

from contracts.result import Result
from domain.services.job_state_validator import validate_job_state_transition


class TtsOrchestrationService:
    """Minimal service stub for Story 1.1 state validation boundary."""

    @staticmethod
    def validate_transition(current_state: str, next_state: str) -> Result[None]:
        return validate_job_state_transition(current_state, next_state)
