"""Purge all messages (queued and in-flight) from the jobs SQS queue.

Useful during local development now that LocalStack persists state across
restarts -- messages left over from a previous run don't just disappear on
their own anymore.

Note: this only clears the queue, not the S3 request objects or DynamoDB
job records already written for those messages -- their status will simply
stay whatever it was (e.g. QUEUED) since no worker will ever pick them up.
"""

import boto3

from common import config


def main() -> None:
    sqs = boto3.client("sqs", endpoint_url=config.AWS_ENDPOINT_URL, region_name=config.AWS_REGION)
    queue_url = sqs.get_queue_url(QueueName=config.JOBS_QUEUE)["QueueUrl"]
    sqs.purge_queue(QueueUrl=queue_url)
    print(f"purged queue {config.JOBS_QUEUE}")


if __name__ == "__main__":
    main()
