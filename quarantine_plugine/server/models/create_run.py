from pydantic import BaseModel, Field


class RunTest(BaseModel):
    nodeid: str
    status: str
    duration: float
    quarantined: bool
    traceback: str


class RunRequest(BaseModel):
    run_id: str = Field(min_length=1)
    repo: str
    commit: str
    branch: str
    started_at: str
    ci_url: str
    tests: list[RunTest]


class CreateResponse(BaseModel):
    message: str
