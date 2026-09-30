"""Create the S3 bucket, DynamoDB table, and SQS queue used by the toy
service, for local development against LocalStack or a moto server.

In real AWS environments these resources are created by the infra/ IaC,
not by application code -- this script only exists for local bootstrapping.
"""

import boto3
from botocore.exceptions import ClientError

from common import config


def _ignore_already_exists(func, *, already_exists_codes: set[str]) -> None:
    try:
        func()
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in already_exists_codes:
            raise


def main() -> None:
    s3 = boto3.client("s3", endpoint_url=config.AWS_ENDPOINT_URL, region_name=config.AWS_REGION)
    dynamodb = boto3.client(
        "dynamodb", endpoint_url=config.AWS_ENDPOINT_URL, region_name=config.AWS_REGION
    )
    sqs = boto3.client("sqs", endpoint_url=config.AWS_ENDPOINT_URL, region_name=config.AWS_REGION)

    _ignore_already_exists(
        lambda: s3.create_bucket(Bucket=config.JOBS_BUCKET),
        already_exists_codes={"BucketAlreadyOwnedByYou", "BucketAlreadyExists"},
    )

    _ignore_already_exists(
        lambda: dynamodb.create_table(
            TableName=config.JOBS_TABLE,
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        ),
        already_exists_codes={"ResourceInUseException"},
    )

    _ignore_already_exists(
        lambda: sqs.create_queue(QueueName=config.JOBS_QUEUE),
        already_exists_codes={"QueueAlreadyExists"},
    )

    print(f"bucket={config.JOBS_BUCKET} table={config.JOBS_TABLE} queue={config.JOBS_QUEUE} ready")


if __name__ == "__main__":
    main()
