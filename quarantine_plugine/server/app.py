from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response

from quarantine_plugine.server.settings import Settings
from quarantine_plugine.server.db import Database
from quarantine_plugine.server.models.create_run import (
    CreateResponse,
    RunRequest,
)
from quarantine_plugine.server.dependency import RepositoryDep


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    db = Database(
        database_url=settings.DATABASE_URL,
        min_size=settings.DATABASE_MIN_SIZE,
        max_size=settings.DATABASE_MAX_SIZE,
    )

    db.connect()
    app.state.db = db

    yield
    db.disconnect()


app = FastAPI(lifespan=lifespan)


@app.post(
    "/v1/runs",
    response_model=CreateResponse,
    responses={
        202: {"model": CreateResponse, "description": "Run created"},
        200: {"model": CreateResponse, "description": "Run already exists"},
    },
)
def create_run(run: RunRequest, response: Response, repository: RepositoryDep):
    result = repository.save_run(run)
    if result:
        response.status_code = 202
        return CreateResponse(message="Run created")
    response.status_code = 200
    return CreateResponse(message="Run already exists")


@app.get("/v1/runs/{run_id}")
def get_run_by_run_id(run_id: str, repository: RepositoryDep):
    run = repository.get_run_by_run_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Item not found")
    return run
