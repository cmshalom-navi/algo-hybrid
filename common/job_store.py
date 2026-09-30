"""Shared S3 / DynamoDB / SQS access for the api and worker services.

Job lifecycle:
    create_job()   -> writes the request to S3, a QUEUED item to DynamoDB,
                       and a pointer message to SQS.
    receive_jobs() -> worker long-polls SQS for pointer messages.
    get_request()  -> worker fetches the request payload from S3.
    mark_running / mark_succeeded / mark_failed -> worker updates DynamoDB.
    get_job()      -> api reads current status/result for polling clients.
"""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3

from common import config


def _s3():
    return boto3.client("s3", endpoint_url=config.AWS_ENDPOINT_URL, region_name=config.AWS_REGION)


def _dynamodb():
    return boto3.resource("dynamodb", endpoint_url=config.AWS_ENDPOINT_URL, region_name=config.AWS_REGION)


def _sqs():
    return boto3.client("sqs", endpoint_url=config.AWS_ENDPOINT_URL, region_name=config.AWS_REGION)


def _queue_url() -> str:
    return _sqs().get_queue_url(QueueName=config.JOBS_QUEUE)["QueueUrl"]


def _table():
    return _dynamodb().Table(config.JOBS_TABLE)


def _floats_to_decimals(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _floats_to_decimals(v) for k, v in value.items()}
    return value


def _decimals_to_floats(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _decimals_to_floats(v) for k, v in value.items()}
    return value


def create_job(a: float, b: float) -> str:
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
            "status": "QUEUED",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "request_s3_key": request_key,
        }
    )

    # The queue only ever carries a pointer (job_id) -- never the payload
    # itself -- so large requests don't need to fit in a 256KB SQS message.
    _sqs().send_message(QueueUrl=_queue_url(), MessageBody=json.dumps({"job_id": job_id}))

    return job_id


def get_job(job_id: str) -> dict | None:
    item = _table().get_item(Key={"job_id": job_id}).get("Item")
    return _decimals_to_floats(item) if item is not None else None


def get_request(request_s3_key: str) -> dict:
    obj = _s3().get_object(Bucket=config.JOBS_BUCKET, Key=request_s3_key)
    return json.loads(obj["Body"].read())


def receive_jobs(max_messages: int = 5, wait_time_seconds: int = 10) -> list[dict]:
    response = _sqs().receive_message(
        QueueUrl=_queue_url(),
        MaxNumberOfMessages=max_messages,
        WaitTimeSeconds=wait_time_seconds,
    )
    return response.get("Messages", [])


def delete_job_message(receipt_handle: str) -> None:
    _sqs().delete_message(QueueUrl=_queue_url(), ReceiptHandle=receipt_handle)


def mark_running(job_id: str) -> None:
    _table().update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #status = :status",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": "RUNNING"},
    )


def mark_succeeded(job_id: str, result: dict) -> None:
    _table().update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #status = :status, #result = :result",
        ExpressionAttributeNames={"#status": "status", "#result": "result"},
        ExpressionAttributeValues={":status": "SUCCEEDED", ":result": _floats_to_decimals(result)},
    )


def mark_failed(job_id: str, error: str) -> None:
    _table().update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #status = :status, #error = :error",
        ExpressionAttributeNames={"#status": "status", "#error": "error"},
        ExpressionAttributeValues={":status": "FAILED", ":error": error},
    )
