# Task runner for algo-hybrid. Run `just` to list recipes.
# Requires uv (https://docs.astral.sh/uv/) and just
# (`uv tool install rust-just`).

set dotenv-load := false

# Env for running services on the host against LocalStack on :4566.
local_env := "AWS_ENDPOINT_URL=http://localhost:4566 " + \
    "AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test " + \
    "AWS_DEFAULT_REGION=us-east-1"

# List available recipes.
default:
    @just --list

# --- Setup ------------------------------------------------------------------

# Create/update .venv from uv.lock (includes dev tools).
sync:
    uv sync

# Re-resolve dependencies and update uv.lock.
lock:
    uv lock

# --- Quality ----------------------------------------------------------------

# Run tests; extra args go to pytest (e.g. `just test -k vertex`).
test *args:
    uv run pytest {{ args }}

# Lint and check formatting.
lint:
    uv run ruff check .
    uv run ruff format --check .

# Auto-fix lint issues and reformat.
fmt:
    uv run ruff check --fix .
    uv run ruff format .

# Static type checking.
typecheck:
    uv run mypy .

# Everything CI should run.
check: lint typecheck test

# --- Local stack (docker compose) -------------------------------------------

# Build images and start the full stack (localstack, api, worker).
up *args:
    docker compose up --build {{ args }}

# Stop the stack.
down:
    docker compose down

# Follow logs, optionally for one service (e.g. `just logs worker`).
logs *service:
    docker compose logs -f {{ service }}

# Start only LocalStack, for running api/worker on the host.
localstack:
    docker compose up -d localstack

# (Re-)create the S3 bucket, DynamoDB table and SQS queue.
bootstrap:
    docker compose run --rm bootstrap

# Purge all messages from the jobs queue.
purge:
    {{ local_env }} uv run python purge_queue.py

# --- Running programs on the host -------------------------------------------

# Run the API on the host with autoreload (needs `just localstack`).
api port="8000":
    {{ local_env }} uv run uvicorn services.api.main:app --reload \
        --port {{ port }}

# Run the worker on the host (needs `just localstack`).
worker:
    {{ local_env }} uv run python -m services.worker.main

# Submit a demo job and poll it (default URL is the compose api).
demo a="-1" b="1" url="http://127.0.0.1:8080":
    uv run python client_demo.py {{ a }} {{ b }} {{ url }}
