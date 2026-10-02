"""Manual test client for the async job API.

Submits a job with parameters a, b and polls until it finishes.

Usage:
    python clients/toy_demo.py [a] [b] [base_url]
"""

import sys

from clients import request
from common import models


def main() -> None:
    """Submits a job built from the command-line arguments and prints it."""
    a = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    b = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    base_url = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8000"

    job = request.Request(models.ToyInstance(a=a, b=b), base_url)
    print(f"submitted job {job.job_id} (status={job.status})")
    print(job.poll())


if __name__ == "__main__":
    main()
