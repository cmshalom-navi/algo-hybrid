FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY domain ./domain
COPY common ./common
COPY services/api ./services/api

RUN pip install --no-cache-dir .

CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
