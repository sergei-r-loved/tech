from datetime import datetime
from typing import Literal

from quarantine_plugine.server.models.custom_base_model import CustomBaseModel


class RunTest(CustomBaseModel):
    nodeid: str
    status: Literal["passed", "failed", "skipped", "error"]
    duration: float
    quarantined: bool
    traceback: str | None = None


class RunRequest(CustomBaseModel):
    run_id: str
    repo: str
    commit: str
    branch: str | None = None
    started_at: datetime
    ci_url: str | None = None
    tests: list[RunTest]


class CreateResponse(CustomBaseModel):
    message: str
