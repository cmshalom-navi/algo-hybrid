import json
import time

import botocore.exceptions

from common import job_store
from domain.toy_solver import solve


def process_message(body: dict) -> None:
    job_id = body["job_id"]
    item = job_store.get_job(job_id)
    if item is None:
        return

    job_store.mark_running(job_id)
    try:
        request = job_store.get_request(item["request_s3_key"])
        result = solve(request["a"], request["b"])
        job_store.mark_succeeded(
            job_id,
            {
                "status": result.status,
                "x": result.x,
                "y": result.y,
                "objective": result.objective,
            },
        )
    except Exception as exc:
        job_store.mark_failed(job_id, str(exc))


def run_once() -> int:
    """Poll SQS once and process whatever is available. Returns count processed."""
    messages = job_store.receive_jobs()
    for message in messages:
        process_message(json.loads(message["Body"]))
        job_store.delete_job_message(message["ReceiptHandle"])
    return len(messages)


def wait_for_queue(max_wait_seconds: float = 60.0, retry_interval_seconds: float = 2.0) -> None:
    """Retry until the SQS queue is reachable, instead of crashing on startup
    if the infra (queue/table/bucket) isn't created yet -- e.g. the worker
    container starts before the queue exists, or LocalStack is still coming
    up.
    """
    deadline = time.monotonic() + max_wait_seconds
    last_error: botocore.exceptions.ClientError | None = None
    while time.monotonic() < deadline:
        try:
            job_store.receive_jobs(max_messages=1, wait_time_seconds=0)
            return
        except botocore.exceptions.ClientError as exc:
            last_error = exc
            print(f"queue not ready yet ({exc}), retrying...")
            time.sleep(retry_interval_seconds)
    raise RuntimeError(f"queue not reachable after {max_wait_seconds}s") from last_error


def run_forever(idle_sleep_seconds: float = 1.0) -> None:
    wait_for_queue()
    print("worker started, polling for jobs...")
    while True:
        try:
            processed = run_once()
        except botocore.exceptions.ClientError as exc:
            print(f"poll failed ({exc}), retrying...")
            time.sleep(idle_sleep_seconds)
            continue
        if processed == 0:
            time.sleep(idle_sleep_seconds)


if __name__ == "__main__":
    run_forever()
