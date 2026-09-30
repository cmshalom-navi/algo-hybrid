FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY domain ./domain
COPY common ./common
COPY services/worker ./services/worker
COPY docker/bootstrap_local.py ./

RUN pip install --no-cache-dir .

CMD ["python", "-m", "services.worker.main"]
