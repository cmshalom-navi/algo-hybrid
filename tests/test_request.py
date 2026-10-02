"""Tests for clients.request.

HTTP calls are faked by patching urllib.request.urlopen, so no API server
is needed.
"""

import json
from typing import Any
from unittest import mock
import urllib.request

import pytest

from clients import request
from common import models

_BASE_URL = "http://api.test"
_JOB_URL = f"{_BASE_URL}/jobs/job-1"
_CREATED = {"job_id": "job-1", "status": "QUEUED"}


def _response(payload: dict[str, Any]) -> mock.MagicMock:
    """Returns a fake urlopen() context manager yielding `payload`."""
    response = mock.MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(
        payload
    ).encode()
    return response


def _sent(urlopen: mock.MagicMock, call_index: int) -> urllib.request.Request:
    """Returns the HTTP request passed to the given urlopen() call."""
    return urlopen.call_args_list[call_index].args[0]


@pytest.fixture(name="urlopen")
def _urlopen() -> Any:
    with mock.patch.object(urllib.request, "urlopen") as urlopen:
        yield urlopen


@pytest.fixture(name="sleep")
def _sleep() -> Any:
    with mock.patch.object(request.time, "sleep") as sleep:
        yield sleep


def _submit(
    urlopen: mock.MagicMock, *job_payloads: dict[str, Any]
) -> request.Request:
    """Creates a Request, queueing `job_payloads` as later GET responses."""
    urlopen.side_effect = [_response(p) for p in (_CREATED, *job_payloads)]
    return request.Request(models.ToyInstance(a=-1, b=0.5), _BASE_URL)


def test_init_posts_instance(urlopen: mock.MagicMock) -> None:
    """Creating a Request POSTs the instance as JSON to /jobs."""
    _submit(urlopen)

    sent = _sent(urlopen, 0)
    assert sent.get_method() == "POST"
    assert sent.full_url == f"{_BASE_URL}/jobs"
    assert sent.get_header("Content-type") == "application/json"
    assert isinstance(sent.data, bytes)
    assert json.loads(sent.data) == {"a": -1, "b": 0.5}


def test_init_stores_job_details(urlopen: mock.MagicMock) -> None:
    """The job ID and initial status from the response are stored."""
    job = _submit(urlopen)

    assert job.base_url == _BASE_URL
    assert job.job_id == "job-1"
    assert job.status == "QUEUED"


@pytest.mark.parametrize("final_status", ["SUCCEEDED", "FAILED"])
def test_poll_returns_terminal_payload(
    urlopen: mock.MagicMock, sleep: mock.MagicMock, final_status: str
) -> None:
    """poll() GETs the job until it finishes and returns the payload."""
    final = {"job_id": "job-1", "status": final_status, "result": None}
    job = _submit(
        urlopen,
        {"job_id": "job-1", "status": "QUEUED"},
        {"job_id": "job-1", "status": "RUNNING"},
        final,
    )

    assert job.poll(interval_seconds=0.25) == final
    assert job.status == final_status
    assert urlopen.call_count == 4
    for call_index in range(1, 4):
        sent = _sent(urlopen, call_index)
        assert sent.get_method() == "GET"
        assert sent.full_url == _JOB_URL
        assert sent.data is None
    assert sleep.call_args_list == [mock.call(0.25)] * 2


def test_poll_raises_on_timeout(
    urlopen: mock.MagicMock, sleep: mock.MagicMock
) -> None:
    """poll() raises TimeoutError if the job is still running."""
    job = _submit(urlopen, {"job_id": "job-1", "status": "RUNNING"})

    # Start, one in-time check, then one past the deadline.
    with mock.patch.object(
        request.time, "monotonic", side_effect=[0.0, 0.5, 1.5]
    ):
        with pytest.raises(TimeoutError, match="job-1"):
            job.poll(timeout_seconds=1.0)

    assert job.status == "RUNNING"
    assert urlopen.call_count == 2
    sleep.assert_called_once()
