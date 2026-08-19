"""FastMCP server assembly + fail-fast startup sequence (server-config §startup).

Startup order: load config (``CONFIG_*`` fails fast) -> ``GET /myself`` (401
maps to ``AUTH_UNAUTHORIZED``) -> ``GET /field`` cache (failure fails fast) ->
register the 9 tools with i18n names/descriptions. Any startup failure raises
:class:`JiraError` before a tool is registered, so no tools are exposed.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

from mcp_jira.client import JiraClient
from mcp_jira.config import Settings, load_config
from mcp_jira.fields import FieldMap
from mcp_jira.i18n import MESSAGES, TOOL_IDS, tool_description, tool_name
from mcp_jira.tools import Tools


def build_app(settings: Settings, client: JiraClient, fields: FieldMap) -> FastMCP:
    """Assemble the FastMCP app and register the 9 tools; performs no I/O."""
    app = FastMCP("mcp-jira")
    tools = Tools(client, fields, settings)
    for tool_id in TOOL_IDS:
        app.add_tool(
            getattr(tools, tool_id),
            name=tool_name(tool_id, settings.language),
            description=tool_description(tool_id, settings.language),
        )
    return app


def create_server(
    config_path: Path | None = None,
    env: Mapping[str, str] | None = None,
    transport: httpx.BaseTransport | None = None,
) -> FastMCP:
    """Run the startup sequence and return a fully registered FastMCP app.

    Raises :class:`JiraError` with a §4.4 code (``CONFIG_*``, ``AUTH_UNAUTHORIZED``)
    on any startup failure — no tools are exposed in that case.
    """
    settings = load_config(config_path, env)
    client = JiraClient(
        settings.jira_url,
        settings.jira_pat,
        messages=dict(MESSAGES[settings.language]),
        transport=transport,
    )
    client.request("GET", "/rest/api/2/myself")  # 401 -> AUTH_UNAUTHORIZED, fail fast
    fields = FieldMap.from_http(client)  # /field failure fails fast (design)
    return build_app(settings, client, fields)
