from contextlib import contextmanager
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


class Database:
    def __init__(self, database_url: str, min_size: int = 2, max_size: int = 10):
        self.pool: ConnectionPool = ConnectionPool(
            conninfo=database_url,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
            open=False,
        )

    def connect(self) -> None:
        self.pool.open(wait=True)

    def disconnect(self) -> None:
        self.pool.close()

    def get_connections(self):
        return self.pool.connection()
