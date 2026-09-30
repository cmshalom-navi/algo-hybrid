from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from common import job_store

app = FastAPI()


class SolveRequest(BaseModel):
    a: float
    b: float


class JobCreated(BaseModel):
    job_id: str
    status: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    result: dict | None = None
    error: str | None = None


@app.post("/jobs", response_model=JobCreated, status_code=202)
def create_job(request: SolveRequest) -> JobCreated:
    job_id = job_store.create_job(request.a, request.b)
    return JobCreated(job_id=job_id, status="QUEUED")


@app.get("/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str) -> JobStatus:
    item = job_store.get_job(job_id)
    if item is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobStatus(
        job_id=item["job_id"],
        status=item["status"],
        result=item.get("result"),
        error=item.get("error"),
    )
