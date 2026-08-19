"""Error model for mcp-jira (PRD §4.4): stable codes, precedence, HTTP mapper.

Pure module — no I/O and no httpx dependency. ``map_http_error`` maps an HTTP
response shape to a :class:`JiraError`; transport failures become
``NETWORK_ERROR`` via :func:`network_error`; ``CONFIG_*`` errors are raised by
``mcp_jira.config`` directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# §4.4 codes in error-precedence order (CONFIG_* > AUTH_* > RATE_LIMITED >
# VALIDATION_* > NOT_FOUND > SERVER_ERROR > NETWORK_ERROR > INTERNAL).
ERROR_PRECEDENCE: tuple[str, ...] = (
    "CONFIG_MISSING",
    "CONFIG_INVALID",
    "AUTH_UNAUTHORIZED",
    "AUTH_FORBIDDEN",
    "RATE_LIMITED",
    "VALIDATION_ERROR",
    "JQL_INVALID",
    "TRANSITION_INVALID",
    "FIELD_NOT_EDITABLE",
    "NOT_FOUND",
    "SERVER_ERROR",
    "NETWORK_ERROR",
    "INTERNAL",
)

# English message templates (PRD §4.4 "Surfaced message (en)"). Placeholders are
# filled by the mapper; i18n mirrors this table per language (design Risk 3).
EN_MESSAGES: dict[str, str] = {
    "CONFIG_MISSING": (
        "Configuration missing. Run `mcp-jira setup` or create `~/.config/mcp-jira/config.json`."
    ),
    "CONFIG_INVALID": ("Invalid configuration: {detail}. Fix config or re-run `mcp-jira setup`."),
    "AUTH_UNAUTHORIZED": (
        "Authentication failed. Your PAT is invalid or expired. Generate a new "
        "one in Jira admin → PATs."
    ),
    "AUTH_FORBIDDEN": ("You don't have permission for this operation on the target resource."),
    "NOT_FOUND": "Resource not found: {detail}.",
    "VALIDATION_ERROR": "Invalid request: {detail}.",
    "JQL_INVALID": "Invalid JQL: {detail}.",
    "TRANSITION_INVALID": "Transition '{name}' is not available. Available: {available}.",
    "FIELD_NOT_EDITABLE": "Field '{name}' is not editable in this issue/status.",
    "RATE_LIMITED": "Jira rate limit hit. Retry after {retry_after}.",
    "SERVER_ERROR": "Jira server error ({status}). Jira may be down or overloaded.",
    "NETWORK_ERROR": "Could not reach Jira at {url}: {detail}.",
    "READ_ONLY_MODE": "Read-only mode is enabled. This mutation is blocked.",
    "INTERNAL": "Unexpected error: {detail}. This is a bug — report it.",
}


@dataclass(frozen=True)
class JiraError(Exception):
    """A surfaced error: stable §4.4 ``code`` plus a localized, redacted message."""

    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def redact_pat(text: str, pat: str) -> str:
    """Replace every occurrence of ``pat`` in ``text``; no-op for an empty PAT."""
    return text.replace(pat, "[REDACTED]") if pat else text


def _render(messages: Mapping[str, str], code: str, **kwargs: Any) -> str:
    template = messages.get(code) or EN_MESSAGES.get(code) or EN_MESSAGES["INTERNAL"]
    return template.format(**kwargs)


def _classify_400(body: dict[str, Any], endpoint: str) -> str:
    """Discriminate an HTTP 400 by payload shape (design Risk 2)."""
    if body.get("errors"):
        return "VALIDATION_ERROR"
    if body.get("errorMessages") and endpoint == "search":
        return "JQL_INVALID"
    return "JQL_INVALID" if endpoint == "search" else "VALIDATION_ERROR"


def _verbatim(body: dict[str, Any], key: str, sep: str) -> str:
    return sep.join(str(item) for item in (body.get(key) or []))


def _retry_after(headers: Mapping[str, str] | None) -> str:
    for key, value in (headers or {}).items():
        if key.lower() == "retry-after":
            try:
                return f"{int(value)}s"
            except ValueError:
                return value or "unknown"
    return "unknown"


def map_http_error(
    status: int,
    body: dict[str, Any] | None = None,
    *,
    endpoint: str = "",
    headers: Mapping[str, str] | None = None,
    messages: Mapping[str, str] = EN_MESSAGES,
    pat: str | None = None,
) -> JiraError:
    """Map an HTTP failure to a :class:`JiraError` honoring §4.4 precedence.

    Branch order follows ``ERROR_PRECEDENCE``: auth outranks rate-limit, which
    outranks validation, etc. ``messages`` supplies localized templates (i18n);
    ``pat`` is redacted from the surfaced message when provided.
    """
    body = body or {}
    code: str
    kwargs: dict[str, Any]
    if status == 401:
        code, kwargs = "AUTH_UNAUTHORIZED", {}
    elif status == 403:
        code, kwargs = "AUTH_FORBIDDEN", {}
    elif status == 429:
        code, kwargs = "RATE_LIMITED", {"retry_after": _retry_after(headers)}
    elif status == 400:
        code = _classify_400(body, endpoint)
        if code == "JQL_INVALID":
            kwargs = {"detail": _verbatim(body, "errorMessages", "; ")}
        else:
            field_errors = body.get("errors") or {}
            kwargs = {"detail": ", ".join(str(v) for v in field_errors.values())}
    elif status == 404:
        detail = _verbatim(body, "errorMessages", "; ") or f"HTTP {status}"
        code, kwargs = "NOT_FOUND", {"detail": detail}
    elif status >= 500:
        code, kwargs = "SERVER_ERROR", {"status": status}
    else:
        code, kwargs = "INTERNAL", {"detail": f"HTTP {status} from Jira"}
    message = redact_pat(_render(messages, code, **kwargs), pat or "")
    return JiraError(code, message)


def network_error(
    url: str,
    detail: str,
    *,
    messages: Mapping[str, str] = EN_MESSAGES,
    pat: str | None = None,
) -> JiraError:
    """Build a ``NETWORK_ERROR`` for transport failures (used by the HTTP client)."""
    message = redact_pat(_render(messages, "NETWORK_ERROR", url=url, detail=detail), pat or "")
    return JiraError("NETWORK_ERROR", message)
