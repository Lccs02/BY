"""Minimal Feishu OpenAPI client with in-memory token caching."""

from __future__ import annotations

import time
from typing import Any, Self

import httpx

from .config import Settings


class FeishuAPIError(RuntimeError):
    """A sanitized OpenAPI error; request bodies and credentials are excluded."""

    def __init__(self, operation: str, code: int | str, message: str, request_id: str = ""):
        self.operation = operation
        self.code = code
        self.api_message = message
        self.request_id = request_id
        hint = ""
        normalized = message.lower()
        if code in {99991663, 99991668, 99991672, 99991679} or any(
            word in normalized for word in ("permission", "forbidden", "scope")
        ):
            hint = " Check the app's published Bitable permissions/scopes in Feishu Open Platform."
        request_text = f" request_id={request_id}" if request_id else ""
        super().__init__(f"{operation} failed: code={code}, message={message}.{hint}{request_text}")


class FeishuClient:
    """Authenticate and issue sanitized Feishu OpenAPI requests."""

    def __init__(self, settings: Settings, timeout: float = 20.0):
        self.settings = settings
        self._http = httpx.Client(base_url=settings.api_base_url, timeout=timeout)
        self._tenant_token: str | None = None
        self._token_expires_at = 0.0

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._tenant_token = None
        self._token_expires_at = 0.0
        self._http.close()

    def authenticate(self, force: bool = False) -> None:
        """Acquire and cache a tenant token without returning or printing it."""

        if not force and self._tenant_token and time.monotonic() < self._token_expires_at:
            return
        try:
            response = self._http.post(
                "/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self.settings.app_id_value,
                    "app_secret": self.settings.app_secret_value,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FeishuAPIError("authenticate", "transport", type(exc).__name__) from exc
        code = payload.get("code", -1)
        token = payload.get("tenant_access_token")
        if code != 0 or not token:
            raise FeishuAPIError("authenticate", code, str(payload.get("msg", "unknown error")))
        expires_in = max(int(payload.get("expire", 7200)) - 120, 60)
        self._tenant_token = str(token)
        self._token_expires_at = time.monotonic() + expires_in

    def request(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.authenticate()
        assert self._tenant_token is not None
        try:
            response = self._http.request(
                method,
                path,
                params=params,
                json=json,
                headers={"Authorization": f"Bearer {self._tenant_token}"},
            )
            response.raise_for_status()
            payload = response.json() if response.content else {"code": 0, "data": {}}
        except httpx.HTTPStatusError as exc:
            request_id = exc.response.headers.get("x-request-id", "")
            try:
                error = exc.response.json()
            except ValueError:
                error = {}
            raise FeishuAPIError(
                operation,
                error.get("code", exc.response.status_code),
                str(error.get("msg", exc.response.reason_phrase)),
                request_id,
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise FeishuAPIError(operation, "transport", type(exc).__name__) from exc
        code = payload.get("code", 0)
        if code != 0:
            raise FeishuAPIError(
                operation,
                code,
                str(payload.get("msg", "unknown error")),
                str(payload.get("request_id", "")),
            )
        return payload.get("data") or {}
