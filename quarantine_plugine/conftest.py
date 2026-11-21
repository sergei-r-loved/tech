from pathlib import Path
from pytest import MonkeyPatch
import psycopg
import pytest

from testcontainers.community.postgres import PostgresContainer

INIT_DB = Path(__file__).resolve().parent / "init_db" / "schema.sql"


@pytest.fixture(scope="session")
def postgres():
    with (
        PostgresContainer(
            "postgres:18.7",
            username="test",
            password="test",
            dbname="test_db",
            driver=None,
        ) as postgres,
        MonkeyPatch().context() as m,
    ):
        m.setenv("DATABASE_URL", postgres.get_connection_url())
        conn = psycopg.connect(postgres.get_connection_url())
        sql = INIT_DB.read_text(encoding="utf-8")

        with conn.cursor() as cursor:
            cursor.execute(sql)
        conn.commit()
        conn.close()

        yield postgres
