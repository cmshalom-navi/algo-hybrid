"""HTTP client for a single job submitted to the async job API."""

import json
import time
from typing import Any
import urllib.request

import pydantic

# Kept local rather than imported from common.job_store so this client has
# no boto3 dependency.
_TERMINAL_STATUSES = ("SUCCEEDED", "FAILED")


class Request:
    """A job submitted to the API.

    Creating an instance submits the job; `poll` then waits for it to
    finish.

    Attributes:
        base_url: Base URL of the API service.
        job_id: ID of the submitted job.
        status: Last status reported by the API.
    """

    def __init__(self, instance: pydantic.BaseModel, base_url: str) -> None:
        """Submits a new job to the API.

        Args:
            instance: The problem to solve.
            base_url: Base URL of the API service.
        """
        self.base_url = base_url
        created = self._request(
            "POST", f"{base_url}/jobs", instance.model_dump()
        )
        self.job_id: str = created["job_id"]
        self.status: str = created["status"]

    def poll(
        self, timeout_seconds: float = 30.0, interval_seconds: float = 0.5
    ) -> dict[str, Any]:
        """Polls the job until it reaches a terminal state.

        Args:
            timeout_seconds: Maximum time to wait.
            interval_seconds: Delay between polls.

        Returns:
            The final job status payload.

        Raises:
            TimeoutError: If the job does not finish within
                `timeout_seconds`.
        """
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            job = self._request("GET", f"{self.base_url}/jobs/{self.job_id}")
            self.status = job["status"]
            if self.status in _TERMINAL_STATUSES:
                return job
            time.sleep(interval_seconds)
        raise TimeoutError(
            f"job {self.job_id} did not finish within {timeout_seconds}s"
        )

    @staticmethod
    def _request(
        method: str, url: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        http_request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        with urllib.request.urlopen(http_request) as response:
            return json.loads(response.read())
