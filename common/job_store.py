"""Shared S3 / DynamoDB / SQS access for the api and worker services.

Job lifecycle:
    create_job()   -> writes the request to S3, a QUEUED item to DynamoDB,
                       and a pointer message to SQS.
    receive_jobs() -> worker long-polls SQS for pointer messages.
    get_request()  -> worker fetches the request payload from S3.
    mark_running / mark_succeeded / mark_failed -> worker updates DynamoDB.
    get_job()      -> api reads current status/result for polling clients.
"""

import datetime
import decimal
import json
from typing import Any
import uuid

import boto3

from common import config

STATUS_QUEUED = "QUEUED"
STATUS_RUNNING = "RUNNING"
STATUS_SUCCEEDED = "SUCCEEDED"
STATUS_FAILED = "FAILED"


def _s3() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=config.AWS_ENDPOINT_URL,
        region_name=config.AWS_REGION,
    )


def _dynamodb() -> Any:
    return boto3.resource(
        "dynamodb",
        endpoint_url=config.AWS_ENDPOINT_URL,
        region_name=config.AWS_REGION,
    )


def _sqs() -> Any:
    return boto3.client(
        "sqs",
        endpoint_url=config.AWS_ENDPOINT_URL,
        region_name=config.AWS_REGION,
    )


def _queue_url() -> str:
    return _sqs().get_queue_url(QueueName=config.JOBS_QUEUE)["QueueUrl"]


def _table() -> Any:
    return _dynamodb().Table(config.JOBS_TABLE)


def _floats_to_decimals(value: Any) -> Any:
    """Recursively converts floats to Decimals, as DynamoDB requires."""
    if isinstance(value, float):
        return decimal.Decimal(str(value))
    if isinstance(value, dict):
        return {k: _floats_to_decimals(v) for k, v in value.items()}
    return value


def _decimals_to_floats(value: Any) -> Any:
    """Recursively converts DynamoDB Decimals back to floats."""
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _decimals_to_floats(v) for k, v in value.items()}
    return value


def create_job(a: float, b: float) -> str:
    """Stores a new job request and enqueues it for the worker.

    Args:
        a: Objective coefficient of x.
        b: Objective coefficient of y.

    Returns:
        The ID of the newly created job.
    """
    job_id = str(uuid.uuid4())
    request_key = f"jobs/{job_id}/request.json"

    _s3().put_object(
        Bucket=config.JOBS_BUCKET,
        Key=request_key,
        Body=json.dumps({"a": a, "b": b}).encode(),
        ContentType="application/json",
    )

    _table().put_item(
        Item={
            "job_id": job_id,
            "status": STATUS_QUEUED,
            "created_at": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
            "request_s3_key": request_key,
        }
    )

    # The queue only ever carries a pointer (job_id) -- never the payload
    # itself -- so large requests don't need to fit in a 256KB SQS message.
    _sqs().send_message(
        QueueUrl=_queue_url(), MessageBody=json.dumps({"job_id": job_id})
    )

    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    """Fetches a job record.

    Args:
        job_id: ID of the job to fetch.

    Returns:
        The job record, or None if no such job exists.
    """
    item = _table().get_item(Key={"job_id": job_id}).get("Item")
    return _decimals_to_floats(item) if item is not None else None


def get_request(request_s3_key: str) -> dict[str, Any]:
    """Fetches a job's request payload from S3.

    Args:
        request_s3_key: S3 key of the request, as stored in the job record.

    Returns:
        The decoded request payload.
    """
    obj = _s3().get_object(Bucket=config.JOBS_BUCKET, Key=request_s3_key)
    return json.loads(obj["Body"].read())


def receive_jobs(
    max_messages: int = 5, wait_time_seconds: int = 10
) -> list[dict[str, Any]]:
    """Long-polls SQS for job pointer messages.

    Args:
        max_messages: Maximum number of messages to return.
        wait_time_seconds: How long to wait for messages to arrive.

    Returns:
        The received SQS messages; empty if none arrived in time.
    """
    response = _sqs().receive_message(
        QueueUrl=_queue_url(),
        MaxNumberOfMessages=max_messages,
        WaitTimeSeconds=wait_time_seconds,
    )
    return response.get("Messages", [])


def delete_job_message(receipt_handle: str) -> None:
    """Deletes a processed message from the queue.

    Args:
        receipt_handle: Receipt handle of the received message.
    """
    _sqs().delete_message(QueueUrl=_queue_url(), ReceiptHandle=receipt_handle)


def mark_running(job_id: str) -> None:
    """Sets a job's status to RUNNING.

    Args:
        job_id: ID of the job to update.
    """
    _table().update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #status = :status",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": STATUS_RUNNING},
    )


def mark_succeeded(job_id: str, result: dict[str, Any]) -> None:
    """Sets a job's status to SUCCEEDED and stores its result.

    Args:
        job_id: ID of the job to update.
        result: Result payload to store with the job.
    """
    _table().update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #status = :status, #result = :result",
        ExpressionAttributeNames={"#status": "status", "#result": "result"},
        ExpressionAttributeValues={
            ":status": STATUS_SUCCEEDED,
            ":result": _floats_to_decimals(result),
        },
    )


def mark_failed(job_id: str, error: str) -> None:
    """Sets a job's status to FAILED and stores the error message.

    Args:
        job_id: ID of the job to update.
        error: Description of the failure.
    """
    _table().update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #status = :status, #error = :error",
        ExpressionAttributeNames={"#status": "status", "#error": "error"},
        ExpressionAttributeValues={":status": STATUS_FAILED, ":error": error},
    )
