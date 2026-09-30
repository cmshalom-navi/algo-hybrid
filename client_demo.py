"""Manual test client for the async job API.

Submits a job with parameters a, b and polls until it finishes.

Usage:
    python client_demo.py [a] [b] [base_url]
"""

import json
import sys
import time
import urllib.request


def _request(method: str, url: str, body: dict | None = None) -> dict:
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
    created = _request("POST", f"{base_url}/jobs", {"a": a, "b": b})
    print(f"submitted job {created['job_id']} (status={created['status']})")
    return created["job_id"]


def poll(job_id: str, base_url: str, timeout_seconds: float = 30.0, interval_seconds: float = 0.5) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status = _request("GET", f"{base_url}/jobs/{job_id}")
        if status["status"] in ("SUCCEEDED", "FAILED"):
            return status
        time.sleep(interval_seconds)
    raise TimeoutError(f"job {job_id} did not finish within {timeout_seconds}s")


if __name__ == "__main__":
    a = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    b = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    base_url = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8000"

    job_id = submit(a, b, base_url)
    print(poll(job_id, base_url))
