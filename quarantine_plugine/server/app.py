from fastapi import FastAPI, HTTPException, Response
from server.models.create_run import (
    RunRequest,
    CreateResponse,
)

app = FastAPI()


CURRENT_STATE: dict[str, RunRequest] = {}


@app.post(
    "/v1/post_run",
    response_model=CreateResponse,
    responses={
        202: {"model": CreateResponse, "description": "Run successfully created"},
        200: {"model": CreateResponse, "description": "Run already exists"},
    },
)
def create_run(run: RunRequest, response: Response):
    if run.run_id not in CURRENT_STATE:
        CURRENT_STATE[run.run_id] = run
        response.status_code = 202
        return CreateResponse(message="Run created")
    if run.run_id in CURRENT_STATE:
        response.status_code = 200
        return CreateResponse(message="Run is already created")


@app.get("/v1/{run_id}")
def get_run_by_run_id(run_id: str):
    run = CURRENT_STATE.get(run_id, None)
    if not run:
        raise HTTPException(status_code=404, detail="Item not found")
    return run
