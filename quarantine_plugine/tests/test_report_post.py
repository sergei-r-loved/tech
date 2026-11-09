from unittest.mock import patch

import pytest
from httpx import Client, MockTransport, Response, TimeoutException, TransportError

from quarantine_plugine.plugin import Result, _post_result
from quarantine_plugine.test_data.create_run_data_generator import make_valid_run_dt

BASE_URL = "http://127.0.0.1:8000"


def _handler_fabric(status, json):
    def _handler(request):
        return Response(status, json=json)

    return _handler


def _exception_handler_fabric(exception):
    def exception_handler(request):
        raise exception

    return exception_handler


def _valid_body() -> Result:
    return make_valid_run_dt()


@pytest.mark.parametrize(
    "status_code, result",
    [
        (199, False),
        (300, False),
        (600, False),
        (399, False),
        (400, False),
        (499, False),
        (200, True),
        (299, True),
    ],
)
def test_post_result_status(status_code, result):
    client = Client(
        transport=MockTransport(
            _handler_fabric(status_code, {"message": "Run created"})
        )
    )

    test_url = f"{BASE_URL}/v1/runs"
    response = _post_result(test_url, _valid_body(), client, 1)

    assert response == (result, status_code)


@pytest.mark.parametrize(
    "exception, message", [(TimeoutException, "Timeout"), (TransportError, "Transport")]
)
def test_post_result_handle_expected_exceptions(exception, message):
    expected_exception = exception(message)
    client = Client(
        transport=MockTransport(_exception_handler_fabric(expected_exception))
    )

    test_url = f"{BASE_URL}/v1/runs"
    response = _post_result(test_url, _valid_body(), client, 1, 1)

    assert response == (False, expected_exception)


def test_post_result_fails_if_get_unexpected_exception():
    expected_exception = AttributeError
    client = Client(
        transport=MockTransport(
            _exception_handler_fabric(expected_exception("Unexpected"))
        )
    )

    test_url = f"{BASE_URL}/v1/runs"
    with pytest.raises(expected_exception, match="Unexpected"):
        _post_result(test_url, _valid_body(), client, 1, 1)


@pytest.mark.parametrize(
    "status_code, result, retry_attempts",
    [
        (500, False, 3),
        (599, False, 3),
        (429, False, 3),
    ],
)
def test_post_result_retry(status_code, result, retry_attempts):
    client = Client(
        transport=MockTransport(
            _handler_fabric(status_code, {"message": "Run created"})
        )
    )

    test_url = f"{BASE_URL}/v1/runs"
    with patch("time.sleep") as mock_sleep:
        response = _post_result(test_url, _valid_body(), client, 0.1, retry_attempts)

    assert response == (result, status_code)
    assert mock_sleep.call_count == retry_attempts
