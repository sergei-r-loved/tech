from dataclasses import asdict
import json
from unittest.mock import patch

import pytest
from httpx import (
    ConnectError,
    LocalProtocolError,
    MockTransport,
    ReadTimeout,
    RemoteProtocolError,
    Response,
    TimeoutException,
    UnsupportedProtocol,
)

from quarantine_plugine.plugin import BASE_URL, Result, _post_result
from quarantine_plugine.test_data.create_run_data_generator import make_valid_run_dt


def _handler_fabric(status, json):
    calls = []

    def _handler(request):
        calls.append(request)
        return Response(status, json=json, request=request)

    return _handler, calls


def _exception_handler_fabric(exception):
    calls = []

    def exception_handler(request):
        calls.append(request)
        raise exception

    return exception_handler, calls


def _negative_to_positive_handler_fabric(retry_attempts):
    statuses = [503 for _ in range(retry_attempts - 1)]
    statuses.append(200)
    statuses = iter(statuses)

    def _handler(request):
        status = next(statuses)
        return Response(status, request=request)

    return _handler


def _exception_to_positive_handler_fabric(retry_attempts):
    results = [TimeoutException("Exception") for _ in range(retry_attempts - 1)]
    results.append(202)
    results = iter(results)

    def _handler(request):
        result = next(results)
        if isinstance(result, TimeoutException):
            raise TimeoutException("Exception")
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

    assert str(calls[0].url) == f"{BASE_URL}/v1/runs"
    assert json.loads(calls[0].content.decode("utf-8")) == asdict(body)


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
    handler, calls = _handler_fabric(status_code, {"message": "Run created"})
    response = _post_result(
        payload=_valid_body(),
        transport=MockTransport(handler),
        timeout_sleep=1,
    )

    assert response == (result, status_code)
    assert len(calls) == 1


# временные: сервер лежит, завис, упал посреди ответа — повтор может помочь
@pytest.mark.parametrize(
    "exception",
    [
        ConnectError("Connection refused"),
        ReadTimeout("Read timed out"),
        RemoteProtocolError("Server disconnected"),
    ],
)
def test_post_result_retries_transient_exceptions(exception):
    handler, calls = _exception_handler_fabric(exception)

    with patch("time.sleep") as mock_sleep:
        response = _post_result(
            payload=_valid_body(),
            transport=MockTransport(handler),
            timeout_sleep=1,
            retry_attempts=3,
        )
    waits = [c.args[0] for c in mock_sleep.call_args_list]

    assert response == (False, exception)
    assert len(calls) == 3
    assert waits == [1, 2]


# постоянные: ошибка на нашей стороне, повтор ничего не исправит
@pytest.mark.parametrize(
    "exception",
    [
        UnsupportedProtocol("Request URL has an unsupported protocol 'ftp://'"),
        LocalProtocolError("Illegal header value"),
        AttributeError("Unexpected"),
    ],
)
def test_post_result_stops_on_permanent_exceptions(exception):
    handler, calls = _exception_handler_fabric(exception)

    with patch("time.sleep") as mock_sleep:
        response = _post_result(
            payload=_valid_body(),
            transport=MockTransport(handler),
            timeout_sleep=1,
        )

    assert response == (False, exception)
    assert len(calls) == 1
    assert mock_sleep.call_count == 0


@pytest.mark.parametrize("status_code", [500, 599, 429])
def test_post_result_retry(status_code):
    handler, calls = _handler_fabric(status_code, {"message": "Run created"})

    with patch("time.sleep") as mock_sleep:
        response = _post_result(
            payload=_valid_body(),
            transport=MockTransport(handler),
            timeout_sleep=1,
            retry_attempts=3,
        )
    waits = [c.args[0] for c in mock_sleep.call_args_list]

    assert response == (False, status_code)
    assert len(calls) == 3
    assert waits == [1, 2]


def test_post_result_retry_cap():
    handler, calls = _handler_fabric(500, {"message": "Run created"})
    retry_attempts = 6

    with patch("time.sleep") as mock_sleep:
        response = _post_result(
            payload=_valid_body(),
            transport=MockTransport(handler),
            timeout_sleep=1,
            retry_attempts=retry_attempts,
        )
    waits = [c.args[0] for c in mock_sleep.call_args_list]

    assert response == (False, 500)
    assert len(calls) == retry_attempts
    assert waits == [1, 2, 4, 8, 10]  # 16 обрезано потолком