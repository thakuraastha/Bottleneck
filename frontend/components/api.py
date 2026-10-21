from __future__ import annotations

import os
from typing import Any

import requests


class ApiError(RuntimeError):
    pass


class BottleneckApi:
    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        self.base_url = (base_url or os.getenv("BOTTLENECK_API_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.timeout = timeout

    def get(self, path: str, **params: Any) -> Any:
        return self._request("GET", path, params=params or None)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request("POST", path, json=payload)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = requests.request(method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise ApiError(f"Backend unavailable at {self.base_url}: {exc}") from exc
        if not response.ok:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ApiError(f"{response.status_code}: {detail}")
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

