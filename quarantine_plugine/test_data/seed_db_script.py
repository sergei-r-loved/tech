from logging import getLogger
from datetime import UTC, datetime, timedelta
import random
from quarantine_plugine.server.db import Database
from quarantine_plugine.server.settings import Settings
from quarantine_plugine.test_data.create_run_data_generator import (
    make_valid_test,
    make_valid_run,
)


logger = getLogger(__name__)


def make_db():
    settings = Settings()
    db = Database(
        database_url=settings.DATABASE_URL,
        min_size=settings.DATABASE_MIN_SIZE,
        max_size=settings.DATABASE_MAX_SIZE,
    )
    db.connect()
    return db


def _push_to_db(connection, runs):
    query = """
        INSERT INTO run (run_id, repo, commit, started_at, branch, ci_url)
        VALUES (%(run_id)s, %(repo)s, %(commit)s, %(started_at)s, %(branch)s, %(ci_url)s)
        ON CONFLICT (run_id) DO NOTHING
    """
    runs_no_tests = [run.model_dump(exclude={"tests"}) for run in runs]
    with connection.transaction(), connection.cursor() as cur:
        cur.executemany(
            query,
            runs_no_tests,
        )
        tests = []
        for t in run.tests:
            test = t.model_dump()
            test["run_id"] = run.run_id
            tests.append(test)
        cur.executemany(
            "INSERT INTO result (run_id, nodeid, status, quarantined, duration, traceback) values (%(run_id)s, %(nodeid)s, %(status)s, %(quarantined)s, %(duration)s, %(traceback)s)",
            tests,
        )
    return True


def _pseudo_random_data(run, tests):
    now = datetime.now(UTC)
    start = now - timedelta(days=30)
    return start + (now - start) * run / max(tests - 1, 1)


COMMITS: list[str] = []
RUNS = 300
TESTS = 3000
REPOS = ["tech/go", "tech/front", "tech/workers"]
STATUSES = ["passed", "failed", "skipped", "error"]

DB = make_db()

ready_runs: list = []
start = datetime.now()

while RUNS:
    tests_count = TESTS
    run = make_valid_run(0)
    run.started_at = _pseudo_random_data(RUNS, TESTS)
    run.repo = random.choice(REPOS)
    COMMITS.append(run.commit)

    if random.randint(1, 3) == 1 and COMMITS:
        run.commit = random.choice(COMMITS)
    tests: list = []

    for i in range(tests_count + 1):
        test = make_valid_test(i)
        if i > 2500:
            test.status = random.choice(STATUSES)
        tests.append(test)
    run.tests = tests
    ready_runs.append(run)
    RUNS -= 1

    pool = DB.pool
    with pool.connection() as conn:
        result = _push_to_db(conn, ready_runs)

DB.disconnect()
logger.warning(f"Script worked for {datetime.now() - start}")
