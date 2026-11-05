from datetime import datetime, timezone
from random import randint

from quarantine_plugine.server.models.create_run import RunTest, RunRequest


def make_valid_test(id: int) -> RunTest:
    return RunTest(
        nodeid="quarantine_plugine/tests/test_create_run.py" + f"[{id}]" if id else "",
        status="passed",
        duration=11.1,
        quarantined=False,
        traceback="some traceback bla bla",
    )


def make_valid_run(tests_count: int | None = None):
    return RunRequest(
        run_id=str(randint(80000000, 99999999)),
        repo="tech_repo",
        commit="ca82a6d",
        branch="dev/test_branch",
        started_at=str(datetime.now(timezone.utc).timestamp()),
        ci_url="https://github.com/tech/pipeline/123123",
        tests=[make_valid_test(i) for i in range(tests_count if tests_count else 1)],
    )
