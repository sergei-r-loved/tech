import json
import shlex
from urllib.parse import urlencode

from httpx import Request, Response


class CustomLogger:
    def __init__(self, logger):
        # Принимаем и сохраняем уже существующий объект логера
        self.logger = logger

    def log_request_response(self, request: Request, response: Response):
        curl = self.build_curl_command(
            method=request.method,
            url=str(request.url),
            headers=request.headers,
            query_params=dict(request.url.params),
            body=request.content,
            post_params=None,  # пока с формами не работаю
        )
        try:
            pretty_response: str = json.dumps(
                response.json(), indent=2, ensure_ascii=False
            )
        except json.JSONDecodeError:
            pretty_response = response.text

        separator_block = "=" * 80
        separator_request_response = "-" * 80
        request_body_block = ""
        if request.content:
            pretty_request = json.dumps(
                json.loads(request.content), indent=2, ensure_ascii=False
            )
            request_body_block = f"Request body:\n{pretty_request}\n"

        log_block = (
            f"\n{separator_block}\n"
            f"Curl:\n{curl}\n"
            f"{request_body_block}"
            f"\n{separator_request_response}\n"
            f"Response status: {response.status_code}\n"
            f"Response headers:\n{json.dumps(dict(response.headers), indent=2, ensure_ascii=False)}\n"
            f"Response body:\n{pretty_response}\n"
            f"{separator_block}"
        )
        self.logger.info(log_block)

        return response

    @staticmethod
    def _normalize_post_params(post_params):
        """Нормализует post_params в словарь.

        Args:
            post_params: Может быть списком кортежей или словарем

        Returns:
            Словарь параметров или пустой словарь
        """
        if isinstance(post_params, list):
            return dict(post_params) if post_params else {}
        if isinstance(post_params, dict):
            return post_params
        return {}

    @staticmethod
    def _add_post_params_to_curl(parts, post_params, content_type):
        """Добавляет post_params в список частей curl команды.

        Args:
            parts: Список частей curl команды
            post_params: Словарь параметров
            content_type: Content-Type заголовок
        """
        if not post_params:
            return

        is_multipart = content_type and "multipart/form-data" in content_type
        flag = "-F" if is_multipart else "--data-urlencode"

        for key, value in post_params.items():
            value_str = str(value)
            parts.append(f"{flag} {shlex.quote(f'{key}={value_str}')}")

    @staticmethod
    def build_curl_command(
        method, url, headers=None, body=None, query_params=None, post_params=None
    ):
        """Создает красивую и безопасную cURL-команду из данных запроса, включая query-параметры и post_params."""
        # Копируем URL, чтобы не изменять оригинальную переменную
        final_url = url

        # Добавляем query-параметры к URL, если они есть
        if query_params:
            query_string = urlencode(query_params)
            # Проверяем, есть ли в URL уже параметры, чтобы добавить '?' или '&'
            if "?" in final_url:
                final_url += f"&{query_string}"
            else:
                final_url += f"?{query_string}"

        # Начинаем формировать команду с метода
        parts = ["curl", f"-X {shlex.quote(method.upper())}"]

        # Добавляем заголовки (-H 'Header: Value')
        if headers:
            for key, value in headers.items():
                parts.append(f"-H {shlex.quote(f'{key}: {value}')}")

        # Определяем Content-Type из заголовков
        content_type = None
        if headers:
            content_type = headers.get("Content-Type") or headers.get("content-type")

        # Обрабатываем post_params (form data)
        if post_params:
            params_dict = CustomLogger._normalize_post_params(post_params)
            CustomLogger._add_post_params_to_curl(parts, params_dict, content_type)
        # Добавляем тело запроса (-d '{"key": "value"}')
        # body используется только если нет post_params
        elif body:
            body_str = (
                body.decode("utf-8", errors="ignore")
                if isinstance(body, bytes)
                else str(body)
            )
            parts.append(f"-d {shlex.quote(body_str)}")

        # Добавляем итоговый URL в самом конце
        parts.append(shlex.quote(final_url))

        return " \\\n    ".join(parts)
