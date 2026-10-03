"""Environment-driven configuration shared by the api and worker services."""

import os

AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

JOBS_BUCKET = os.environ.get("JOBS_BUCKET", "algo-hybrid-jobs")
JOBS_TABLE = os.environ.get("JOBS_TABLE", "algo-hybrid-jobs")
JOBS_QUEUE = os.environ.get("JOBS_QUEUE", "algo-hybrid-jobs")

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5440"))
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "algo_db")
