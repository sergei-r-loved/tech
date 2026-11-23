import json
from pathlib import Path

from psycopg.errors import UniqueViolation
import pytest

from quarantine_plugine.server.models.create_run import RunRequest
from quarantine_plugine.test_data.create_run_data_generator import make_valid_run


REPO = "tech/quarantine_plugin"
GIT_COMMIT = "ag14fosht45g"

RUNS_URL = "/v1/runs"
RUN_URL = "/v1/runs/{run_id}"

REQUIRED_RUN_FIELDS = [
    "run_id",
    "tests",
    "commit",
    "repo",
]
NULLABLE_RUN_FIELDS = ["branch", "ci_url"]
REQUIRED_TEST_FIELDS = ["nodeid", "status", "duration", "quarantined"]


def _valid_body(test_count: int | None = None) -> dict:
    return make_valid_run(test_count if test_count is not None else 1).model_dump(
        mode="json"
    )


def _error_locs(response) -> list[list]:
    return [error["loc"] for error in response.json()["detail"]]


# --- приём и идемпотентность -------------------------------------------------


def test_create_run_202(client):
    response = client.post(RUNS_URL, json=_valid_body())

    assert response.status_code == 202


def test_two_different_runs_202(client):
    assert client.post(RUNS_URL, json=_valid_body()).status_code == 202
    assert client.post(RUNS_URL, json=_valid_body()).status_code == 202


def test_repeat_same_run_200_same_body(client):
    body = _valid_body()

    client.post(RUNS_URL, json=body)
    second = client.post(RUNS_URL, json=body)

    assert second.status_code == 200
    assert second.json() == {"message": "Run already exists"}


def test_repeat_does_not_overwrite_run(client):
    """Повтор с тем же run_id, но другими данными — храним первый, не перезаписываем."""
    body = _valid_body()
    client.post(RUNS_URL, json=body)

    client.post(RUNS_URL, json=body | {"commit": "other-commit"})

    stored = client.get(RUN_URL.format(run_id=body["run_id"])).json()
    assert stored["commit"] == body["commit"]


# --- чтение ------------------------------------------------------------------


def test_get_returns_what_was_posted(client):
    body = _valid_body()
    client.post(RUNS_URL, json=body)

    response = client.get(RUN_URL.format(run_id=body["run_id"]))

    assert response.status_code == 200
    assert RunRequest.model_validate(response.json()) == RunRequest.model_validate(body)


def test_get_unknown_run_404(client):
    response = client.get(RUN_URL.format(run_id="no-such-run"))

    assert response.status_code == 404


@pytest.mark.parametrize("field", REQUIRED_RUN_FIELDS)
def test_missing_required_run_field_422(client, field):
    body = _valid_body()
    del body[field]

    response = client.post(RUNS_URL, json=body)

    assert response.status_code == 422
    assert ["body", field] in _error_locs(response)


@pytest.mark.parametrize("field", REQUIRED_TEST_FIELDS)
def test_missing_required_test_field_422(client, field):
    body = _valid_body()
    del body["tests"][0][field]

    response = client.post(RUNS_URL, json=body)

    assert response.status_code == 422
    assert ["body", "tests", 0, field] in _error_locs(response)


@pytest.mark.parametrize("field", NULLABLE_RUN_FIELDS)
def test_nullable_run_field_accepts_null_202(client, field):
    response = client.post(RUNS_URL, json=_valid_body() | {field: None})

    assert response.status_code == 202


def test_passed_test_without_traceback_202(client):
    """У прошедшего теста плагин шлёт traceback: null."""
    body = _valid_body()
    body["tests"][0]["traceback"] = None

    response = client.post(RUNS_URL, json=body)

    assert response.status_code == 202


def test_unknown_status_422(client):
    body = _valid_body()
    body["tests"][0]["status"] = "banana"

    response = client.post(RUNS_URL, json=body)

    assert response.status_code == 422
    assert ["body", "tests", 0, "status"] in _error_locs(response)


def test_rollback_if_error_404(client):
    body = _valid_body(2)
    body["tests"][0]["nodeid"] = "banana"
    body["tests"][1]["nodeid"] = "banana"

    with pytest.raises(UniqueViolation):
        client.post(RUNS_URL, json=body)
    response = client.get(RUN_URL.format(run_id=body["run_id"]))

    assert response.status_code == 404


def test_run_no_tests_202(client):
    body = _valid_body(0)
    post_response = client.post(RUNS_URL, json=body)
    get_response = client.get(RUN_URL.format(run_id=body["run_id"]))

    assert post_response.status_code == 202
    assert get_response.status_code == 200
    assert get_response.json()["tests"] == []


# --- контракт: настоящий JSON плагина -> сервер -------------------------------


def _plugin_source() -> str:
    return (Path(__file__).resolve().parent.parent / "plugin.py").read_text("utf-8")


def test_server_accepts_real_plugin_report(client, pytester, monkeypatch):
    for var in ("RUN_ID", "BRANCH", "CI_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("REPO", REPO)
    monkeypatch.setenv("GIT_COMMIT", GIT_COMMIT)
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
