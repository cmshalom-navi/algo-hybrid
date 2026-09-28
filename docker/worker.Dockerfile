FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY domain ./domain
COPY services/worker ./services/worker

RUN pip install --no-cache-dir .

CMD ["python", "-m", "services.worker.main"]
