import unittest

from contracts.errors import AppError
from contracts.result import failure, success


class TestContracts(unittest.TestCase):
    def test_result_success_contract_shape(self) -> None:
        result = success({"value": 1})
        payload = result.to_dict()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"], {"value": 1})
        self.assertIsNone(payload["error"])

    def test_result_failure_contract_shape(self) -> None:
        result = failure(
            code="invalid_input",
            message="Input is invalid",
            details={"field": "state"},
            retryable=False,
        )
        payload = result.to_dict()

        self.assertFalse(payload["ok"])
        self.assertIsNone(payload["data"])
        self.assertEqual(
            payload["error"],
            {
                "code": "invalid_input",
                "message": "Input is invalid",
                "details": {"field": "state"},
                "retryable": False,
            },
        )

    def test_app_error_to_dict_shape(self) -> None:
        error = AppError(
            code="job_failed",
            message="Job failed",
            details={"job_id": "123"},
            retryable=True,
        )
        self.assertEqual(
            error.to_dict(),
            {
                "code": "job_failed",
                "message": "Job failed",
                "details": {"job_id": "123"},
                "retryable": True,
            },
        )
