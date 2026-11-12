import json
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

from quarantine_plugine.server.app import CURRENT_STATE, app
from quarantine_plugine.server.models.create_run import RunRequest
from quarantine_plugine.utils.base_http_client import BaseHttpClient

RUN_ID = "probe-1"


def _read_plugin():
    path_to_conftest = Path(__file__).resolve().parent.parent / "plugin.py"
    return path_to_conftest.read_text("utf-8")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live_server():
    CURRENT_STATE.clear()
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    deadline = time.monotonic() + 5
    while not server.started:
        assert time.monotonic() < deadline
        time.sleep(0.01)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    t.join(5)


def _post_spy():
    calls = []

    def _handler(
        self,
        endpoint,
        **kwargs,
    ):
        calls.append(endpoint)
        return httpx.Response(202)

    return _handler, calls


def test_send_server_up(pytester, monkeypatch, live_server):
    monkeypatch.setenv("RUN_ID", RUN_ID)
    pytester.makeconftest(_read_plugin())
    pytester.makepyfile("def test_ok(): pass")
    r = pytester.runpytest(f"--send-report={live_server}")

    r.assert_outcomes(passed=1)
    assert r.ret == 0
    assert httpx.get(f"{live_server}/v1/runs/{RUN_ID}").status_code == 200


def test_send_server_down(live_server, pytester, monkeypatch):
    port = _free_port()
    url = "http://127.0.0.1"
    monkeypatch.setattr(time, "sleep", lambda s: None)
    pytester.makeconftest(_read_plugin())
    pytester.makepyfile("def test_ok(): pass")
    r = pytester.runpytest(f"--send-report={url}:{port}")

    r.assert_outcomes(passed=1)
    r.stdout.fnmatch_lines(["*не доставил результат*"])
    r.stdout.fnmatch_lines([f"*{url}:{port}*"])
    assert r.ret == 0


def test_server_has_same_as_file(live_server, pytester, monkeypatch):
    monkeypatch.setenv("RUN_ID", RUN_ID)
    pytester.makeconftest(_read_plugin())
    pytester.makepyfile("def test_ok(): pass")

    r = pytester.runpytest("--flaky-report=r.json", f"--send-report={live_server}")
    path_to_report = pytester.path / "r.json"
    file = json.loads(path_to_report.read_text())
    response_server = httpx.get(f"{live_server}/v1/runs/{RUN_ID}")

    assert r.ret == 0
    assert RunRequest.model_validate(
        response_server.json()
    ) == RunRequest.model_validate(file)


def test_send_no_flag(pytester, monkeypatch):
    handler, calls = _post_spy()
    monkeypatch.setattr(BaseHttpClient, "post", handler)
    pytester.makeconftest(_read_plugin())
    pytester.makepyfile("def test_ok(): pass")

    r = pytester.runpytest()

    assert r.ret == 0
    assert calls == []
