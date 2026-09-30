"""Creates the toy service's AWS resources in LocalStack.

Creates the S3 bucket, DynamoDB table, and SQS queue used by the toy service,
for local development against LocalStack.

Runs as the `bootstrap` service in docker/docker-compose.yml before the api
and worker start. It is idempotent: resources that already exist are left
as-is, so `docker compose run --rm bootstrap` can be used to re-create them.

In real AWS environments these resources are created by the infra/ IaC,
not by application code -- this script only exists for local bootstrapping.
"""

from typing import Any, Callable

import boto3
from botocore import exceptions

from common import config


def _ignore_already_exists(
    func: Callable[[], object], *, already_exists_codes: set[str]
) -> None:
    try:
        func()
    except exceptions.ClientError as exc:
        if exc.response["Error"]["Code"] not in already_exists_codes:
            raise


def _client(service_name: str) -> Any:
    return boto3.client(
        service_name,
        endpoint_url=config.AWS_ENDPOINT_URL,
        region_name=config.AWS_REGION,
    )


def main() -> None:
    """Creates the bucket, table and queue, skipping any that exist."""
    s3 = _client("s3")
    dynamodb = _client("dynamodb")
    sqs = _client("sqs")

    _ignore_already_exists(
        lambda: s3.create_bucket(Bucket=config.JOBS_BUCKET),
        already_exists_codes={"BucketAlreadyOwnedByYou", "BucketAlreadyExists"},
    )

    _ignore_already_exists(
        lambda: dynamodb.create_table(
            TableName=config.JOBS_TABLE,
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "job_id", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        ),
        already_exists_codes={"ResourceInUseException"},
    )

    _ignore_already_exists(
        lambda: sqs.create_queue(QueueName=config.JOBS_QUEUE),
        already_exists_codes={"QueueAlreadyExists"},
    )

    print(
        f"bucket={config.JOBS_BUCKET} table={config.JOBS_TABLE} "
        f"queue={config.JOBS_QUEUE} ready"
    )


if __name__ == "__main__":
    main()
