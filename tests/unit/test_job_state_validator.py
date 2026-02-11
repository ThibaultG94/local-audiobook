import unittest

from domain.services.job_state_validator import validate_job_state_transition


class TestJobStateValidator(unittest.TestCase):
    def test_valid_job_transition(self) -> None:
        result = validate_job_state_transition("queued", "running")
        self.assertTrue(result.ok)
        self.assertIsNone(result.error)

    def test_invalid_source_state_returns_normalized_error(self) -> None:
        result = validate_job_state_transition("unknown", "running")
        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "invalid_job_state")

    def test_invalid_transition_returns_normalized_error(self) -> None:
        result = validate_job_state_transition("completed", "running")
        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "invalid_job_transition")
        self.assertEqual(
            result.error.details,
            {
                "current_state": "completed",
                "next_state": "running",
            },
        )
