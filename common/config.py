import os

AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

JOBS_BUCKET = os.environ.get("JOBS_BUCKET", "algo-hybrid-jobs")
JOBS_TABLE = os.environ.get("JOBS_TABLE", "algo-hybrid-jobs")
JOBS_QUEUE = os.environ.get("JOBS_QUEUE", "algo-hybrid-jobs")
