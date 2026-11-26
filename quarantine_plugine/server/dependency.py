from typing import Annotated

from fastapi import Request, Depends

from quarantine_plugine.server.repository import Repository


def get_repositry(request: Request):
    pool = request.app.state.db.pool
    with pool.connection() as conn:
        yield Repository(connection=conn)


RepositoryDep = Annotated[
    Repository,
    Depends(get_repositry),
]
