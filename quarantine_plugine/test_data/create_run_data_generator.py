from datetime import datetime, timezone
from uuid import uuid4

from quarantine_plugine.server.models.create_run import RunTest, RunRequest


def make_valid_test(id: int) -> RunTest:
    return RunTest(
        # было: "..." + f"[{id}]" if id else "" — тернарник накрывал всю сумму, у id=0 nodeid был ""
        nodeid=f"tests/test_example.py::test_case[{id}]",
        status="passed",
        duration=11.1,
        quarantined=False,
        traceback="some traceback bla bla",
    )


def make_valid_run(tests_count: int | None = None):
    return RunRequest(
        run_id=str(uuid4()),
        repo="tech_repo",
        commit="ca82a6d",
        branch="dev/test_branch",
        # как шлёт плагин: ISO с зоной, не unix-timestamp
        started_at=datetime.now(timezone.utc).isoformat(),
        ci_url="https://github.com/tech/pipeline/123123",
        tests=[make_valid_test(i) for i in range(tests_count if tests_count else 1)],
    )
