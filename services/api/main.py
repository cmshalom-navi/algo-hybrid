"""HTTP API for submitting solve jobs and polling their status."""

import fastapi
import pydantic

from common import job_store
from common import models

app = fastapi.FastAPI()


class JobCreated(pydantic.BaseModel):
    """Response returned when a job is accepted.

    Attributes:
        job_id: ID of the new job.
        status: Initial job status (always QUEUED).
    """

    job_id: str
    status: str


class JobStatus(pydantic.BaseModel):
    """Current state of a job.

    Attributes:
        job_id: ID of the job.
        status: One of QUEUED, RUNNING, SUCCEEDED or FAILED.
        result: Solver output, once the job has succeeded.
        error: Error message, if the job has failed.
    """

    job_id: str
    status: str
    result: models.ToySolution | None = None
    error: str | None = None


@app.post("/jobs", response_model=JobCreated, status_code=202)
def create_job(request: models.ToyInstance) -> JobCreated:
    """Accepts a solve request and queues it for the worker.

    Args:
        request: The problem parameters.

    Returns:
        The ID and initial status of the new job.
    """
    job_id = job_store.create_job(request)
    return JobCreated(job_id=job_id, status=job_store.STATUS_QUEUED)


@app.get("/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str) -> JobStatus:
    """Returns the current status of a job.

    Args:
        job_id: ID of the job to look up.

    Returns:
        The job's status, and its result or error if finished.

    Raises:
        fastapi.HTTPException: 404 if no such job exists.
    """
    item = job_store.get_job(job_id)
    if item is None:
        raise fastapi.HTTPException(status_code=404, detail="job not found")
    return JobStatus(
        job_id=item["job_id"],
        status=item["status"],
        result=item.get("result"),
        error=item.get("error"),
    )
