"""HTTP client for FlowScribe remote-direct task execution."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import ssl
import time
from typing import Any
from urllib import error, parse, request

from flowscribe.core.errors import DownloadError, TranscriptionError


@dataclass(frozen=True)
class RemoteServerClient:
    """Minimal stdlib HTTP client for a single remote FlowScribe server."""

    base_url: str
    token: str | None = None
    verify_tls: bool = True
    timeout_seconds: float = 30.0

    def upload_file(self, path: Path) -> dict[str, Any]:
        url = self._url(
            "/v1/uploads",
            {"filename": path.name},
        )
        try:
            response = self._request_json(
                url,
                method="POST",
                data=path.read_bytes(),
                headers={"Content-Type": "application/octet-stream"},
            )
        except OSError as exc:
            raise DownloadError(f"Could not upload local media {path}: {exc}") from exc
        response["filename"] = response.get("filename") or path.name
        return response

    def submit_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(
            self._url("/v1/tasks"),
            method="POST",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    def get_task_status(self, task_id: str) -> dict[str, Any]:
        return self._request_json(self._url(f"/v1/tasks/{parse.quote(task_id, safe='')}"))

    def get_task_events(self, task_id: str) -> list[dict[str, Any]]:
        payload = self._request_text(self._url(f"/v1/tasks/{parse.quote(task_id, safe='')}/events"))
        events: list[dict[str, Any]] = []
        for line in payload.splitlines():
            if not line.startswith("data: "):
                continue
            try:
                raw = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            if isinstance(raw, dict):
                events.append(raw)
        return events

    def get_task_result(self, task_id: str) -> dict[str, Any]:
        return self._request_json(self._url(f"/v1/tasks/{parse.quote(task_id, safe='')}/result"))

    def get_server_info(self) -> dict[str, Any]:
        return self._request_json(self._url("/v1/server"))

    def download_artifact(self, artifact_id: str, destination: Path) -> Path:
        content = self._request_bytes(self._url(f"/v1/artifacts/{parse.quote(artifact_id, safe='')}"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return destination

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def _request_json(
        self,
        url: str,
        *,
        method: str = "GET",
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload = self._request_bytes(url, method=method, data=data, headers=headers)
        try:
            parsed = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TranscriptionError("Remote server returned invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise TranscriptionError("Remote server returned an unexpected JSON payload.")
        return parsed

    def _request_text(
        self,
        url: str,
        *,
        method: str = "GET",
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        payload = self._request_bytes(url, method=method, data=data, headers=headers)
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise TranscriptionError("Remote server returned invalid text content.") from exc

    def _request_bytes(
        self,
        url: str,
        *,
        method: str = "GET",
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        request_headers = dict(headers or {})
        if self.token:
            request_headers["Authorization"] = f"Bearer {self.token}"
        req = request.Request(url, data=data, method=method, headers=request_headers)
        context = None
        if url.startswith("https://") and not self.verify_tls:
            context = ssl._create_unverified_context()
        try:
            with request.urlopen(req, timeout=self.timeout_seconds, context=context) as response:
                return response.read()
        except error.HTTPError as exc:
            body = exc.read()
            message = _http_error_message(body, exc.reason)
            if exc.code == 404:
                raise TranscriptionError(message or "Remote resource was not found.") from exc
            raise TranscriptionError(message or f"Remote server request failed with status {exc.code}.") from exc
        except error.URLError as exc:
            raise DownloadError(f"Could not reach remote server {self.base_url}: {exc.reason}") from exc

    def _url(self, path: str, query: dict[str, str] | None = None) -> str:
        base = self.base_url.rstrip("/")
        url = f"{base}{path}"
        if query:
            url = f"{url}?{parse.urlencode(query)}"
        return url


def _http_error_message(body: bytes, fallback: object) -> str:
    if body:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return body.decode("utf-8", errors="ignore").strip()
        if isinstance(payload, dict):
            for key in ("error", "message"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value
    return str(fallback or "").strip()
