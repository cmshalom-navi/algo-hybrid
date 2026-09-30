"""Manual test client for the async job API.

Submits a job with parameters a, b and polls until it finishes.

Usage:
    python client_demo.py [a] [b] [base_url]
"""

import json
import sys
import time
from typing import Any
import urllib.request

# Kept local rather than imported from common.job_store so this client has
# no boto3 dependency.
_TERMINAL_STATUSES = ("SUCCEEDED", "FAILED")


def _request(
    method: str, url: str, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def submit(a: float, b: float, base_url: str) -> str:
    """Submits a new job to the API.

    Args:
        a: Objective coefficient of x.
        b: Objective coefficient of y.
        base_url: Base URL of the API service.

    Returns:
        The ID of the created job.
    """
    created = _request("POST", f"{base_url}/jobs", {"a": a, "b": b})
    print(f"submitted job {created['job_id']} (status={created['status']})")
    return created["job_id"]


def poll(
    job_id: str,
    base_url: str,
    timeout_seconds: float = 30.0,
    interval_seconds: float = 0.5,
) -> dict[str, Any]:
    """Polls a job until it reaches a terminal state.

    Args:
        job_id: ID returned by `submit`.
        base_url: Base URL of the API service.
        timeout_seconds: Maximum time to wait.
        interval_seconds: Delay between polls.

    Returns:
        The final job status payload.

    Raises:
        TimeoutError: If the job does not finish within `timeout_seconds`.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status = _request("GET", f"{base_url}/jobs/{job_id}")
        if status["status"] in _TERMINAL_STATUSES:
            return status
        time.sleep(interval_seconds)
    raise TimeoutError(f"job {job_id} did not finish within {timeout_seconds}s")


def main() -> None:
    """Submits a job built from the command-line arguments and prints it."""
    a = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    b = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    base_url = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8000"

    job_id = submit(a, b, base_url)
    print(poll(job_id, base_url))


if __name__ == "__main__":
    main()
