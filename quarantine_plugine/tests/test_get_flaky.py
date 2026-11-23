from datetime import UTC, datetime, timedelta

import pytest

from quarantine_plugine.test_data.create_run_data_generator import (
    make_valid_run,
    make_valid_test,
)

RUNS_URL = "/v1/runs"
GET_FLAKY_URL = "/v1/repos/flaky"
RUN_URL = "/v1/runs/{run_id}"

def _valid_body(
    test_count: int | None = None,
    repo: str | None = None,
    commit: str | None = None,
    tests_status: list | None = None,
) -> dict:
    tests = []
    if tests_status is not None:
        tests = [make_valid_test(id, status).model_dump(mode="json") for id, status in enumerate(tests_status)]
        test_count = 0
    else:
        test_count = test_count if test_count is not None else 1
    body = make_valid_run(tests_count=test_count, repo=repo, commit=commit).model_dump(mode="json")
    if tests:
        body["tests"] = tests
    return body


def test_get_flaky_passed_and_failed_same_commit(client):
    # statuses = ["passed", "failed"]
    first_run = _valid_body()
    first_run["tests"][0]["status"] = "passed"
    # second_run = _valid_body(commit=first_run["commit"], repo=first_run["repo"], tests_status=statuses)
    second_run = _valid_body(commit=first_run["commit"], repo=first_run["repo"])
    second_run["tests"][0]["status"] = "failed"
    client.post(RUNS_URL, json=first_run)
    client.post(RUNS_URL, json=second_run)

    get_response = client.get(GET_FLAKY_URL, params={"days": 7, "repo": second_run["repo"]})

    assert get_response.status_code == 200
    assert len(get_response.json()) == 1
    assert get_response.json()[0]["commit"] == second_run["commit"]
    assert get_response.json()[0]["nodeid"] == second_run["tests"][0]["nodeid"]


def test_no_flaky_passed_and_skipped_same_commit(client):
    first_run = _valid_body()
    first_run["tests"][0]["status"] = "passed"
    second_run = _valid_body(commit=first_run["commit"], repo=first_run["repo"])
    second_run["tests"][0]["status"] = "skipped"
    client.post(RUNS_URL, json=first_run)
    client.post(RUNS_URL, json=second_run)

    get_response = client.get(GET_FLAKY_URL, params={"days": 7, "repo": second_run["repo"]})

    assert get_response.status_code == 200
    assert len(get_response.json()) == 0

def test_no_flaky_passed_and_failed_different_commit(client):
    first_run = _valid_body()
    first_run["tests"][0]["status"] = "passed"
    second_run = _valid_body(repo=first_run["repo"])
    second_run["tests"][0]["status"] = "failed"
    client.post(RUNS_URL, json=first_run)
    client.post(RUNS_URL, json=second_run)

    get_response = client.get(GET_FLAKY_URL, params={"days": 7, "repo": second_run["repo"]})

    assert get_response.status_code == 200
    assert len(get_response.json()) == 0

def test_get_flaky_passed_and_failed_same_commit_out_window(client):
    # statuses = ["passed", "failed"]
    first_run = _valid_body()
    first_run["tests"][0]["status"] = "passed"
    date_out_of_window = datetime.now(UTC) - timedelta(days=8)
    date_out_of_window = date_out_of_window.isoformat()
    first_run["started_at"] = date_out_of_window
    # second_run = _valid_body(commit=first_run["commit"], repo=first_run["repo"], tests_status=statuses)
    second_run = _valid_body(commit=first_run["commit"], repo=first_run["repo"])
    second_run["tests"][0]["status"] = "failed"
    client.post(RUNS_URL, json=first_run)
    client.post(RUNS_URL, json=second_run)

    get_response = client.get(GET_FLAKY_URL, params={"days": 7, "repo": second_run["repo"]})
    print(get_response.json())
    # assert get_response.status_code == 200
    # assert len(get_response.json()) == 0