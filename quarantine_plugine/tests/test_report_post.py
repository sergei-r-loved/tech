from dataclasses import asdict
import json
from unittest.mock import patch

import pytest
from httpx import MockTransport, Response, TimeoutException, TransportError

from quarantine_plugine.plugin import Result, _post_result
from quarantine_plugine.test_data.create_run_data_generator import make_valid_run_dt


def _handler_fabric(status, json):
    calls = []

    def _handler(request):
        calls.append(request)
        return Response(status, json=json, request=request)

    return _handler, calls


def _exception_handler_fabric(exception):
    def exception_handler(request):
        raise exception

    return exception_handler


def _negative_to_positive_handler_fabric(retry_attempts):
    statuses = [503 for _ in range(retry_attempts - 1)]
    statuses.append(200)
    statuses = iter(statuses)

    def _handler(request):
        status = next(statuses)
        return Response(status, request=request)

    return _handler


def _exception_to_positive_handler_fabric(retry_attempts):
    results: list[TimeoutException | int] = [
        TimeoutException for _ in range(retry_attempts - 1)
    ]
    results.append(202)
    results = iter(results)

    def _handler(request):
        result = next(results)
        if isinstance(result, TimeoutException):
            raise TimeoutException
        return Response(result, request=request)

    return _handler


def _valid_body() -> Result:
    return make_valid_run_dt()


# -------------TESTS--------------------------#


def test_post_result_postive_after_negative():
    body = _valid_body()
    retry_attempts = 3

    with patch("time.sleep") as mock_sleep:
        result, status = _post_result(
            payload=body,
            transport=MockTransport(
                _negative_to_positive_handler_fabric(retry_attempts)
            ),
            timeout_sleep=1,
            retry_attempts=retry_attempts,
        )

    assert result
    assert status == 200
    assert mock_sleep.call_count == retry_attempts - 1


def test_post_result_postive_after_exception():
    body = _valid_body()
    retry_attempts = 3

    with patch("time.sleep") as mock_sleep:
        result, status = _post_result(
            payload=body,
            transport=MockTransport(
                _exception_to_positive_handler_fabric(retry_attempts)
            ),
            timeout_sleep=1,
            retry_attempts=retry_attempts,
        )

    assert result
    assert status == 202
    assert mock_sleep.call_count == retry_attempts - 1


def test_post_result_body_and_url():
    handler, calls = _handler_fabric(202, {"message": "Run created"})
    body = _valid_body()

    _post_result(
        payload=body,
        transport=MockTransport(handler),
        timeout_sleep=1,
    )

    assert str(calls[0].url).endswith("/v1/runs")
    assert json.loads(calls[0].content.decode("utf-8")) == asdict(body)


@pytest.mark.parametrize(
    "status_code, result, calls_count",
    [
        (199, False, 1),
        (300, False, 1),
        (600, False, 1),
        (399, False, 1),
        (400, False, 1),
        (499, False, 1),
        (200, True, 1),
        (299, True, 1),
    ],
)
def test_post_result_status(status_code, result, calls_count):
    handler, calls = _handler_fabric(status_code, {"message": "Run created"})
    response = _post_result(
        payload=_valid_body(),
        transport=MockTransport(handler),
        timeout_sleep=1,
    )

    assert response == (result, status_code)
    assert len(calls) == calls_count


@pytest.mark.parametrize(
    "exception, message", [(TimeoutException, "Timeout"), (TransportError, "Transport")]
)
def test_post_result_handle_expected_exceptions(exception, message):
    expected_exception = exception(message)

    response = _post_result(
        payload=_valid_body(),
        transport=MockTransport(_exception_handler_fabric(expected_exception)),
        timeout_sleep=1,
        retry_attempts=1,
    )

    assert response == (False, expected_exception)


def test_post_result_doesnt_fail_if_get_unexpected_exception():
    unexpected_exception = AttributeError("Unexpected")

    response = _post_result(
        payload=_valid_body(),
        transport=MockTransport(_exception_handler_fabric(unexpected_exception)),
        timeout_sleep=1,
        retry_attempts=1,
    )

    assert response == (False, unexpected_exception)


@pytest.mark.parametrize(
    "status_code, result, retry_attempts",
    [
        (500, False, 3),
        (599, False, 3),
        (429, False, 3),
    ],
)
def test_post_result_retry(status_code, result, retry_attempts):
    handler, calls = _handler_fabric(status_code, {"message": "Run created"})

    with patch("time.sleep") as mock_sleep:
        response = _post_result(
            payload=_valid_body(),
            transport=MockTransport(handler),
            timeout_sleep=0.1,
            retry_attempts=retry_attempts,
        )

    assert response == (result, status_code)
    assert mock_sleep.call_count == retry_attempts - 1
    assert len(calls) == retry_attempts
