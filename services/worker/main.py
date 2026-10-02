"""Worker that pulls jobs from SQS, solves them, and records the results."""

import json
import logging
import time
from typing import Any

import botocore.exceptions

from common import job_store
from domain import toy_solver


def process_message(body: dict[str, Any]) -> None:
    """Solves the job a queue message points to and records the outcome.

    Messages for unknown jobs are ignored.

    Args:
        body: Decoded message body; must contain "job_id".
    """
    job_id = body["job_id"]
    item = job_store.get_job(job_id)
    if item is None:
        return

    job_store.mark_running(job_id)
    try:
        request = job_store.get_request(item["request_s3_key"])
        job_store.mark_succeeded(job_id, toy_solver.solve(request))
    # Isolation point: any failure is recorded on the job instead of
    # crashing the worker loop.
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logging.exception("job %s failed", job_id)
        job_store.mark_failed(job_id, str(exc))


def run_once() -> int:
    """Polls SQS once and processes whatever is available.

    Returns:
        The number of messages processed.
    """
    messages = job_store.receive_jobs()
    for message in messages:
        process_message(json.loads(message["Body"]))
        job_store.delete_job_message(message["ReceiptHandle"])
    return len(messages)


def wait_for_queue(
    max_wait_seconds: float = 60.0, retry_interval_seconds: float = 2.0
) -> None:
    """Blocks until the SQS queue is reachable.

    Retrying avoids crashing on startup if the infra (queue/table/bucket)
    isn't created yet -- e.g. the worker container starts before the queue
    exists, or LocalStack is still coming up.

    Args:
        max_wait_seconds: How long to keep retrying.
        retry_interval_seconds: Delay between attempts.

    Raises:
        RuntimeError: If the queue is still unreachable after
            `max_wait_seconds`.
    """
    deadline = time.monotonic() + max_wait_seconds
    last_error: botocore.exceptions.ClientError | None = None
    while time.monotonic() < deadline:
        try:
            job_store.receive_jobs(max_messages=1, wait_time_seconds=0)
            return
        except botocore.exceptions.ClientError as exc:
            last_error = exc
            logging.warning("queue not ready yet (%s), retrying...", exc)
            time.sleep(retry_interval_seconds)
    raise RuntimeError(
        f"queue not reachable after {max_wait_seconds}s"
    ) from last_error


def run_forever(idle_sleep_seconds: float = 1.0) -> None:
    """Runs the worker loop until the process is stopped.

    Args:
        idle_sleep_seconds: Delay after an empty or failed poll.
    """
    wait_for_queue()
    logging.info("worker started, polling for jobs...")
    while True:
        try:
            processed = run_once()
        except botocore.exceptions.ClientError as exc:
            logging.warning("poll failed (%s), retrying...", exc)
            time.sleep(idle_sleep_seconds)
            continue
        if processed == 0:
            time.sleep(idle_sleep_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_forever()
