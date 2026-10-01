# algo-hybrid

Service that accepts requests with deeply structured parameters and runs an
optimization algorithm (Google OR-Tools) asynchronously, deployed on AWS.

## Architecture

Request → API (validates, enqueues job) → SQS → Worker (Fargate, long-running,
solves with OR-Tools) → result written to DynamoDB/S3 → client polls job status.

Workers run on ECS Fargate (not Lambda) because solves can take well over
15 minutes.

## Structure

```
services/
  api/          FastAPI app: validates requests, writes jobs to SQS + DynamoDB
  worker/       Long-polls SQS, builds the OR-Tools model, solves, writes results
domain/         Shared, AWS-free: Pydantic schemas, request->model mapping,
                solver logic. Unit-testable in isolation.
infra/          Infrastructure as code (CDK/Terraform) for AWS resources.
docker/         Dockerfiles for the api and worker images, and
                docker-compose.yml for the local dev stack (LocalStack for
                SQS/DynamoDB/S3).
tests/          Test suite (unit, and integration against the local stack).
```

## Local development

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker, and
[just](https://just.systems/) (`uv tool install rust-just`).

```
cp .env.example .env   # first time only; fill in LOCALSTACK_AUTH_TOKEN
just sync              # create .venv from uv.lock (Python 3.11 + dev tools)
just up                # build and start the full stack
just demo -2 1         # submit a job to the stack and poll for the result
```

Run `just` to list all recipes. Common ones:

| Recipe | What it does |
|---|---|
| `just check` | lint + typecheck + tests (what CI should run) |
| `just test [args]` | pytest, e.g. `just test -k vertex` |
| `just fmt` | auto-fix lint issues and reformat |
| `just up` / `just down` / `just logs [svc]` | manage the compose stack |
| `just localstack` + `just api` / `just worker` | run services on the host (with autoreload for the API) against LocalStack |
| `just bootstrap` / `just purge` | (re-)create AWS resources / purge the job queue |

Dependencies are locked in `uv.lock`; the Docker images install from the
same lockfile. After editing dependencies in `pyproject.toml`, run
`just lock` and commit `uv.lock`.

Run from the repo root: `.env` sets `COMPOSE_FILE` to
`docker/docker-compose.yml`.

This starts the API, worker, and a LocalStack instance emulating SQS,
DynamoDB, and S3, so the same code path runs locally and in deployed
environments.

## Deployment

Infrastructure is defined in `infra/` and deployed per environment
(dev/staging/prod). See `infra/README.md` (TBD) for details.
