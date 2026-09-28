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
docker/         Dockerfiles for the api and worker images.
tests/          Test suite (unit, and integration against the local stack).
docker-compose.yml   Local dev stack (LocalStack for SQS/DynamoDB/S3).
```

## Local development

```
docker compose up
```

This starts the API, worker, and a LocalStack instance emulating SQS,
DynamoDB, and S3, so the same code path runs locally and in deployed
environments.

## Deployment

Infrastructure is defined in `infra/` and deployed per environment
(dev/staging/prod). See `infra/README.md` (TBD) for details.
