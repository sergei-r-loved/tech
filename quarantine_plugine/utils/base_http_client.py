import logging
from typing import Literal

import httpx
from httpx import HTTPStatusError, Request

from quarantine_plugine.utils.custom_logger import CustomLogger

logger = logging.getLogger(__name__)
custom_logger = CustomLogger(logger)


class BaseHttpClient:
    METHOD_TYPES = Literal["GET", "POST", "PUT", "DELETE"]

    def __init__(self, base_url, timeout) -> None:
        self.base_url = base_url
        self.timeout = timeout

    def _get_default_headers(self):
        return {
            "Content-Type": "application/json",
        }

    # def _build_authorization_header(self):
    #     # just example, here is could be any logic with signature, authorization generation for each request
    #     return {"Authorization": f"Apikey qwerty_{randint(1, 10)}"}

    def _build_request(
        self,
        method: METHOD_TYPES,
        endpoint: str,
        headers: dict | None = None,
        params: dict | None = None,
        json: dict | None = None,
    ) -> Request:
        request_headers = self._get_default_headers()
        # generate authorization headers/signature, whatever
        # authorization_headers = self._build_authorization_header()
        # merge auth heards with default headers
        # request_headers.update(authorization_headers)
        # if any headers provided merge with current headers
        if headers:
            request_headers.update(headers)
        # build target url
        url = self.base_url + endpoint if endpoint else ""

        return httpx.Request(
            method=method, url=url, params=params, headers=request_headers, json=json
        )

    def _send_request(
        self,
        method: METHOD_TYPES,
        endpoint: str,
        headers: dict | None = None,
        params: dict | None = None,
        json: dict | None = None,
        expected_status: int | None = None,
    ):
        request = self._build_request(method, endpoint, headers, params, json)

        with httpx.Client(verify=True, timeout=self.timeout) as client:
            response = client.send(request)
        custom_logger.log_request_response(request, response)

        if expected_status is not None and response.status_code != expected_status:
            raise HTTPStatusError(
                f"Expected status {expected_status}, got {response.status_code}\n {response.text}",
                request=request,
                response=response,
            )

        return response

    def get(
        self,
        endpoint: str,
        headers: dict | None = None,
        params: dict | None = None,
        expected_status: int | None = None,
    ):
        return self._send_request(
            method="GET",
            endpoint=endpoint,
            headers=headers,
            params=params,
            expected_status=expected_status,
        )

    def post(
        self,
        endpoint: str,
        headers: dict | None = None,
        params: dict | None = None,
        json: dict | None = None,
        expected_status: int | None = None,
    ):
        return self._send_request(
            method="POST",
            endpoint=endpoint,
            headers=headers,
            params=params,
            json=json,
            expected_status=expected_status,
        )

    def put(
        self,
        endpoint: str,
        headers: dict | None = None,
        params: dict | None = None,
        json: dict | None = None,
        expected_status: int | None = None,
    ):
        return self._send_request(
            method="PUT",
            endpoint=endpoint,
            headers=headers,
            params=params,
            json=json,
            expected_status=expected_status,
        )

    def delete(
        self,
        endpoint: str,
        headers: dict | None = None,
        params: dict | None = None,
        json: dict | None = None,
        expected_status: int | None = None,
    ):
        return self._send_request(
            method="DELETE",
            endpoint=endpoint,
            headers=headers,
            params=params,
            json=json,
            expected_status=expected_status,
        )
