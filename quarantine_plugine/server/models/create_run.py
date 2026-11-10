from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class RunTest(BaseModel):
    nodeid: str
    status: Literal["passed", "failed", "skipped", "error"]
    duration: float
    quarantined: bool
    traceback: str | None = None


class RunRequest(BaseModel):
    run_id: str
    repo: str | None = None
    commit: str | None = None
    branch: str | None = None
    started_at: datetime
    ci_url: str | None = None
    tests: list[RunTest]


class CreateResponse(BaseModel):
    message: str
