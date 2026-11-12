import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from quarantine_plugine.server.app import CURRENT_STATE, app
from quarantine_plugine.server.models.create_run import RunRequest
from quarantine_plugine.test_data.create_run_data_generator import make_valid_run

client = TestClient(app)

RUNS_URL = "/v1/runs"
RUN_URL = "/v1/runs/{run_id}"

REQUIRED_RUN_FIELDS = ["run_id", "tests"]
NULLABLE_RUN_FIELDS = ["repo", "commit", "branch", "ci_url"]
REQUIRED_TEST_FIELDS = ["nodeid", "status", "duration", "quarantined"]


@pytest.fixture(autouse=True)
def clean_state():
    """Каждый тест начинает с пустого сервера - тесты не зависят от порядка."""
    CURRENT_STATE.clear()
    yield
    CURRENT_STATE.clear()


def _valid_body() -> dict:
    return make_valid_run().model_dump(mode="json")


def _error_locs(response) -> list[list]:
    return [error["loc"] for error in response.json()["detail"]]


# --- приём и идемпотентность -------------------------------------------------


def test_create_run_202():
    response = client.post(RUNS_URL, json=_valid_body())

    assert response.status_code == 202


def test_two_different_runs_202():
    assert client.post(RUNS_URL, json=_valid_body()).status_code == 202
    assert client.post(RUNS_URL, json=_valid_body()).status_code == 202


def test_repeat_same_run_200_same_body():
    body = _valid_body()

    first = client.post(RUNS_URL, json=body)
    second = client.post(RUNS_URL, json=body)

    assert second.status_code == 200
    assert second.json() == first.json()


def test_repeat_does_not_overwrite_run():
    """Повтор с тем же run_id, но другими данными — храним первый, не перезаписываем."""
    body = _valid_body()
    client.post(RUNS_URL, json=body)

    client.post(RUNS_URL, json=body | {"commit": "other-commit"})

    stored = client.get(RUN_URL.format(run_id=body["run_id"])).json()
    assert stored["commit"] == body["commit"]


# --- чтение ------------------------------------------------------------------


def test_get_returns_what_was_posted():
    body = _valid_body()
    client.post(RUNS_URL, json=body)

    response = client.get(RUN_URL.format(run_id=body["run_id"]))

    assert response.status_code == 200
    assert RunRequest.model_validate(response.json()) == RunRequest.model_validate(body)


def test_get_unknown_run_404():
    response = client.get(RUN_URL.format(run_id="no-such-run"))

    assert response.status_code == 404


@pytest.mark.parametrize("field", REQUIRED_RUN_FIELDS)
def test_missing_required_run_field_422(field):
    body = _valid_body()
    del body[field]

    response = client.post(RUNS_URL, json=body)

    assert response.status_code == 422
    assert ["body", field] in _error_locs(response)


@pytest.mark.parametrize("field", REQUIRED_TEST_FIELDS)
def test_missing_required_test_field_422(field):
    body = _valid_body()
    del body["tests"][0][field]

    response = client.post(RUNS_URL, json=body)

    assert response.status_code == 422
    assert ["body", "tests", 0, field] in _error_locs(response)


@pytest.mark.parametrize("field", NULLABLE_RUN_FIELDS)
def test_nullable_run_field_accepts_null_202(field):
    response = client.post(RUNS_URL, json=_valid_body() | {field: None})

    assert response.status_code == 202


def test_passed_test_without_traceback_202():
    """У прошедшего теста плагин шлёт traceback: null."""
    body = _valid_body()
    body["tests"][0]["traceback"] = None

    response = client.post(RUNS_URL, json=body)

    assert response.status_code == 202


def test_unknown_status_422():
    body = _valid_body()
    body["tests"][0]["status"] = "banana"

    response = client.post(RUNS_URL, json=body)

    assert response.status_code == 422
    assert ["body", "tests", 0, "status"] in _error_locs(response)


# --- контракт: настоящий JSON плагина -> сервер -------------------------------


def _plugin_source() -> str:
    return (Path(__file__).resolve().parent.parent / "plugin.py").read_text("utf-8")


def test_server_accepts_real_plugin_report(pytester, monkeypatch):
    for var in ("RUN_ID", "REPO", "GIT_COMMIT", "BRANCH", "CI_URL"):
        monkeypatch.delenv(var, raising=False)
    pytester.makeconftest(_plugin_source())
    pytester.makepyfile(
        """
        def test_passes():
            pass

        def test_fails():
            assert 1 == 2
        """
    )

    pytester.runpytest("--flaky-report=r.json")
    report = json.loads((pytester.path / "r.json").read_text("utf-8"))

    response = client.post(RUNS_URL, json=report)

    assert response.status_code == 202, response.json()
