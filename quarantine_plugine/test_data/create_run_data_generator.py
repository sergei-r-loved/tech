import string
from datetime import UTC, datetime
from uuid import uuid4
from random import choices, choice

from quarantine_plugine.plugin import Result, Test
from quarantine_plugine.server.models.create_run import RunRequest, RunTest


def _generate_random_commit():
    return "".join(choices(string.ascii_letters + string.digits, k=8))


def _generate_random_repo():
    f_part = choice(["dev", "master", "test"]) + "/"
    return "".join(choices(string.ascii_letters + string.digits, k=8)) + f_part


def make_valid_test(id: int, status: str | None = None) -> RunTest:
    return RunTest(
        nodeid=f"tests/test_example.py::test_case[{id}]",
        status=status or "passed",
        duration=11.1,
        quarantined=False,
        traceback="some traceback bla bla",
    )


def make_valid_run(
    tests_count: int, commit: str | None = None, repo: str | None = None
):
    return RunRequest(
        run_id=str(uuid4()),
        repo=repo or _generate_random_repo(),
        commit=commit or _generate_random_commit(),
        branch="dev/test_branch",
        started_at=datetime.now(UTC),
        ci_url="https://github.com/tech/pipeline/123123",
        tests=[make_valid_test(i) for i in range(tests_count)],
    )


def make_valid_test_dt(id: int) -> Test:
    return Test(
        nodeid=f"tests/test_example.py::test_case[{id}]",
        status="passed",
        duration=11.1,
        quarantined=False,
        traceback="some traceback bla bla",
    )


def make_valid_run_dt(tests_count: int | None = None):
    return Result(
        run_id=str(uuid4()),
        repo="tech_repo",
        commit=_generate_random_commit(),
        branch="dev/test_branch",
        started_at=datetime.now(UTC).isoformat(),
        ci_url="https://github.com/tech/pipeline/123123",
        tests=[make_valid_test_dt(i) for i in range(tests_count if tests_count else 1)],
    )
