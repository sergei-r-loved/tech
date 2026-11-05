from fastapi.testclient import TestClient
import pytest

from quarantine_plugine.test_data.create_run_data_generator import make_valid_run
from server.app import app

client = TestClient(app)

TYPE_TO_MESSAGE = {"string_type": "Input should be a valid string"}


def _message_invalid_param_type(param, input, type):
    return {
        "detail": [
            {
                "type": type,
                "loc": ["body", param],
                "msg": TYPE_TO_MESSAGE[type],
                "input": input,
            }
        ]
    }


def test_create_valid_item_202():
    response = client.post(
        "/v1/post_run",
        json=make_valid_run().model_dump(),
    )

    assert response.status_code == 202
    assert response.json() == {"message": "Run created"}


def test_create_existing_item_200():
    run = make_valid_run()
    client.post(
        "/v1/post_run",
        json=run.model_dump(),
    )

    response = client.post(
        "/v1/post_run",
        json=run.model_dump(),
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Run is already created"}


def test_create_two_items_202():
    response = client.post(
        "/v1/post_run",
        json=make_valid_run().model_dump(),
    )

    assert response.status_code == 202

    response = client.post(
        "/v1/post_run",
        json=make_valid_run().model_dump(),
    )
    assert response.status_code == 202
    assert response.json() == {"message": "Run created"}


def test_get_item_200():
    run = make_valid_run()
    response = client.post(
        "/v1/post_run",
        json=run.model_dump(),
    )

    assert response.status_code == 202

    response = client.get(
        f"/v1/{run.run_id}",
    )
    assert response.status_code == 200
    assert response.json()["run_id"] == run.run_id
    assert response.json()["repo"] == run.repo
    # TODO: Остальные поля? Как то грамотно по ним проитерироваться мб


def test_get_unexisting_item_404():
    response = client.get(
        "/v1/55",
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}


# TODO: продолжать ли такие тесты плодить
@pytest.mark.parametrize(
    "param, type, input",
    [
        pytest.param("run_id", "string_type", 2222, id="run_id_as_int"),
        pytest.param("run_id", "string_type", 22.22, id="run_id_as_float"),
        # pytest.param("run_id", "string_type", "", id="run_id_is_empty"),
        pytest.param("repo", "string_type", 2222, id="repo_as_int"),
        pytest.param("repo", "string_type", 22.22, id="repo_as_float"),
        pytest.param("commit", "string_type", 2222, id="commit_as_int"),
        pytest.param("commit", "string_type", 22.22, id="commit_as_float"),
        pytest.param("branch", "string_type", 2222, id="branch_as_int"),
        pytest.param("branch", "string_type", 22.22, id="branch_as_float"),
    ],
)
def test_create_item_invalid_param_type_422(param, type, input):
    run = make_valid_run().model_dump()
    run[param] = input

    response = client.post(
        "/v1/post_run",
        json=run,
    )

    assert response.status_code == 422
    assert response.json() == _message_invalid_param_type(param, input, type)


# TODO: тесты на мин длину (обязательность поля) pytest.param("run_id", "string_type", "", id="run_id_is_empty"),
# TODO:
