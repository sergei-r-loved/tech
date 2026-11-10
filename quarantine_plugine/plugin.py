import json
import os
import time
import warnings
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import TimeoutException, TransportError

from quarantine_plugine.utils.base_http_client import BaseHttpClient

BASE_URL = "http://127.0.0.1:8000"


@dataclass
class Test:
    nodeid: str | None = None
    status: str | None = None
    duration: float | None = None
    quarantined: bool | None = None
    traceback: str | None = None


@dataclass
class Result:
    run_id: str | None = None
    repo: str | None = None
    commit: str | None = None
    branch: str | None = None
    started_at: str | None = None
    ci_url: str | None = None
    tests: list[Test] = field(default_factory=list)


APP_DIR = Path(__file__).resolve().parent
PATH_TO_QUARANTINE = APP_DIR / "quarantine.txt"
RESULTS: Result = Result()
QUARANTINED_TESTS: set = set()
ATTEMPTS_TO_POST_RUNS = 3
BASE_SLEEP_SECONDS = 3
CAP_SLEEP_SECONDS = 10


def _post_result(
    payload,
    url=None,
    transport=None,
    timeout_sleep: float = BASE_SLEEP_SECONDS,
    retry_attempts=ATTEMPTS_TO_POST_RUNS,
):
    client = BaseHttpClient(url or BASE_URL, timeout=2, transport=transport)
    final_status = None
    for attempt in range(retry_attempts):
        try:
            response = client.post("/v1/runs", json=asdict(payload))
            final_status = response.status_code
            if 200 <= final_status < 300:
                return True, final_status
            if (
                (500 <= final_status < 600) or final_status == 429
            ) and attempt != retry_attempts - 1:
                time.sleep(min(CAP_SLEEP_SECONDS, timeout_sleep * 2**attempt))
                continue
            if (400 <= final_status < 500) and final_status != 429:
                return False, final_status
            else:
                return False, final_status
        except (TimeoutException, TransportError) as e:
            final_status = e
            if attempt != retry_attempts - 1:
                time.sleep(min(CAP_SLEEP_SECONDS, timeout_sleep * 2**attempt))
        except Exception as e:  # noqa: BLE001
            final_status = e
    return False, final_status


def _real_status(report) -> str:
    if report.when == "setup" and report.outcome != "passed":
        return "error" if (report.failed or hasattr(report, "wasxfail")) else "skipped"
    if report.skipped and hasattr(report, "wasxfail"):
        return "failed"
    return report.outcome


def _write_to_file(session, path):
    target = session.config.invocation_params.dir / path
    try:
        target.write_text(
            json.dumps(asdict(RESULTS), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except (OSError, UnicodeDecodeError) as e:
        tr = session.config.pluginmanager.get_plugin("terminalreporter")
        tr.write_line(f"flaky-report: не записал {target}: {e}", yellow=True)


def get_quarantine_list(source: Path) -> set[str] | None:
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError, UnicodeDecodeError:
        return None
    lines = [line.strip() for line in lines]
    return {s for s in lines if s and not s.startswith("#")}


def pytest_collection_modifyitems(session, config, items):
    quarantinied = get_quarantine_list(PATH_TO_QUARANTINE) or set()
    matched = set()
    for item in items:
        base = item.nodeid.split("[")[
            0
        ]  # test_p в файле накрывает test_p[a], test_p[b]
        hit = (
            item.nodeid
            if item.nodeid in quarantinied
            else base
            if base in quarantinied
            else None
        )

        if hit:
            matched.add(hit)
            item.add_marker(pytest.mark.xfail(reason="Quarantined", strict=False))
            QUARANTINED_TESTS.add(item.nodeid)

    collected_files = {item.nodeid.split("::")[0] for item in items}
    for missing in quarantinied - matched:
        if missing.split("::")[0] in collected_files:
            warnings.warn(f"quarantine: {missing} не найден — проверь путь от rootdir")


def pytest_addoption(parser):
    parser.addoption(
        "--flaky-report", default=None, help="куда писать JSON с результатами"
    )
    parser.addoption(
        "--send-report",
        default=False,
        help="куда отправить JSON с результатами на сервер",
    )


def pytest_runtest_logreport(report):
    # pytest зовёт этот хук на каждый тест НЕСКОЛЬКО раз
    if (report.when == "setup" and report.outcome in ("failed", "skipped")) or (
        report.when == "call"
    ):
        test = Test(
            nodeid=report.nodeid,
            status=_real_status(report),
            duration=round(report.duration, 4),
            quarantined=report.nodeid in QUARANTINED_TESTS,
            traceback=report.longreprtext or None,
        )
        RESULTS.tests.append(test)


def pytest_sessionstart(session):
    global RESULTS
    QUARANTINED_TESTS.clear()
    RESULTS = Result(
        run_id=os.environ.get("RUN_ID") or str(uuid4()),
        repo=os.environ.get("REPO"),
        commit=os.environ.get("GIT_COMMIT"),
        branch=os.environ.get("BRANCH"),
        ci_url=os.environ.get("CI_URL"),
        started_at=datetime.now(UTC).isoformat(),
    )


def pytest_sessionfinish(session, exitstatus):
    path = session.config.getoption("--flaky-report")
    url = session.config.getoption("--send-report")
    if path:
        _write_to_file(session, path)
    if url and url.startswith("http"):
        result, status = _post_result(url=url, payload=RESULTS)
        if not result:
            tr = session.config.pluginmanager.get_plugin("terminalreporter")
            tr.write_line(
                f"flaky-report: не доставил результат на {url}: {status}", yellow=True
            )
