"""HTTP client wrapper for the Jira REST v2 API (design: retry-once, redacted logs).

Owns the retry policy (error-handling §retry): retry at most once after a 1s
backoff on 5xx or transport errors; never on 4xx (including 429); a 401 from
the retry outranks the preceding timeout/5xx (§4.4 precedence). Logs to stderr
only — never stdout, the MCP transport — with the PAT redacted, the HTTP
status, and the Jira correlation id when present.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any

import httpx

from mcp_jira.errors import EN_MESSAGES, JiraError, map_http_error, network_error, redact_pat

_LOGGER = logging.getLogger("mcp_jira.client")

_BACKOFF_S = 1.0
_CORRELATION_HEADERS = ("x-arequestid", "x-request-id")


def _ensure_stderr_handler() -> None:
    if not _LOGGER.handlers:
        _LOGGER.addHandler(logging.StreamHandler(sys.stderr))
        _LOGGER.setLevel(logging.INFO)


_ensure_stderr_handler()


class JiraClient:
    """Synchronous httpx wrapper authenticating with ``Authorization: Bearer <PAT>``."""

    def __init__(
        self,
        base_url: str,
        pat: str,
        *,
        messages: dict[str, str] = EN_MESSAGES,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._pat = pat
        self._messages = messages
        self._client = httpx.Client(
            base_url=self._base_url,
            transport=transport,
            timeout=timeout,
            headers={"Authorization": f"Bearer {pat}"},
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        """Call ``method`` on ``path``; return parsed JSON, or ``None`` on empty bodies.

        Raises :class:`JiraError` mapped per §4.4 for HTTP and transport failures.
        """
        response = self._attempt(method, path, params=params, json=json)
        return self._parse_body(response)

    def close(self) -> None:
        """Release the underlying httpx connection pool."""
        self._client.close()

    # -- internals ----------------------------------------------------------

    def _attempt(self, method: str, path: str, *, params: Any, json: Any) -> httpx.Response:
        for attempt in (1, 2):
            try:
                response = self._client.request(method, path, params=params, json=json)
            except httpx.TransportError as exc:
                self._log_transport_error(method, path, exc)
                if attempt == 1:
                    time.sleep(_BACKOFF_S)
                    continue
                raise network_error(
                    self._base_url,
                    redact_pat(str(exc), self._pat),
                    messages=self._messages,
                    pat=self._pat,
                ) from exc
            self._log_response(method, path, response)
            if response.status_code >= 500 and attempt == 1:
                time.sleep(_BACKOFF_S)
                continue
            if response.status_code >= 300:
                raise self._map_error(response, path)
            return response
        raise AssertionError("unreachable")

    def _map_error(self, response: httpx.Response, path: str) -> JiraError:
        try:
            body = response.json()
        except ValueError:
            body = None
        endpoint = "search" if "/search" in path else ""
        err = map_http_error(
            response.status_code,
            body,
            endpoint=endpoint,
            headers=response.headers,
            messages=self._messages,
            pat=self._pat,
        )
        _LOGGER.warning("jira %s %s failed with %s", path, response.status_code, err)
        return err

    def _log_response(self, method: str, path: str, response: httpx.Response) -> None:
        corr = self._correlation_id(response)
        _LOGGER.info(
            "jira %s %s -> %s%s",
            method,
            redact_pat(path, self._pat),
            response.status_code,
            f" correlation_id={corr}" if corr else "",
        )

    def _log_transport_error(self, method: str, path: str, exc: httpx.TransportError) -> None:
        _LOGGER.warning(
            "jira %s %s transport error: %s",
            method,
            redact_pat(path, self._pat),
            redact_pat(str(exc), self._pat),
        )

    @staticmethod
    def _correlation_id(response: httpx.Response) -> str | None:
        for key, value in response.headers.items():
            if key.lower() in _CORRELATION_HEADERS and value:
                return value
        return None

    @staticmethod
    def _parse_body(response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return None
