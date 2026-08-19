"""i18n tables for mcp-jira: en/es tool names/descriptions and error templates.

Jira-provided verbatim details, config keys, log lines, and code identifiers
stay untranslated (design Risk 3). Unknown languages and codes fall back to
English.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mcp_jira.errors import EN_MESSAGES

LANGUAGES = ("en", "es")

TOOL_IDS: tuple[str, ...] = (
    "search_issues",
    "get_issue",
    "create_issue",
    "update_issue",
    "transition_issue",
    "add_comment",
    "get_comments",
    "list_projects",
    "list_fields",
)

_TOOL_NAMES: dict[str, dict[str, str]] = {
    "search_issues": {"en": "search_issues", "es": "buscar_incidencias"},
    "get_issue": {"en": "get_issue", "es": "obtener_incidencia"},
    "create_issue": {"en": "create_issue", "es": "crear_incidencia"},
    "update_issue": {"en": "update_issue", "es": "actualizar_incidencia"},
    "transition_issue": {"en": "transition_issue", "es": "transicionar_incidencia"},
    "add_comment": {"en": "add_comment", "es": "agregar_comentario"},
    "get_comments": {"en": "get_comments", "es": "obtener_comentarios"},
    "list_projects": {"en": "list_projects", "es": "listar_proyectos"},
    "list_fields": {"en": "list_fields", "es": "listar_campos"},
}

_TOOL_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "search_issues": {
        "en": (
            "Search Jira issues by JQL. Returns key, summary, status, assignee, "
            "priority, and issue type. max_results defaults to 50 and is capped at 100."
        ),
        "es": (
            "Busca incidencias de Jira por JQL. Devuelve clave, resumen, estado, "
            "asignado, prioridad y tipo. max_results es 50 por defecto y se limita a 100."
        ),
    },
    "get_issue": {
        "en": (
            "Get a single issue by key, including all fields and the workflow "
            "transitions available to the authenticated user."
        ),
        "es": (
            "Obtiene una incidencia por clave, con todos sus campos y las "
            "transiciones de flujo disponibles para el usuario autenticado."
        ),
    },
    "create_issue": {
        "en": (
            "Create a Jira issue in a project. Custom fields may be passed by "
            "display name or raw customfield_XXXXX id."
        ),
        "es": (
            "Crea una incidencia de Jira en un proyecto. Los campos personalizados "
            "pueden pasarse por nombre o por id customfield_XXXXX."
        ),
    },
    "update_issue": {
        "en": (
            "Update fields of an existing issue (custom fields by display name or "
            "raw id). Fails if a field is not editable."
        ),
        "es": (
            "Actualiza campos de una incidencia existente (campos personalizados "
            "por nombre o id). Fallo si un campo no es editable."
        ),
    },
    "transition_issue": {
        "en": "Move an issue through its workflow by transition name or id.",
        "es": "Mueve una incidencia por su flujo de trabajo mediante nombre o id de transición.",
    },
    "add_comment": {
        "en": "Add a comment to an issue. Returns the created comment id and date.",
        "es": "Agrega un comentario a una incidencia. Devuelve el id y la fecha del comentario creado.",
    },
    "get_comments": {
        "en": "List comments on an issue (id, author, created, body).",
        "es": "Lista los comentarios de una incidencia (id, autor, fecha, cuerpo).",
    },
    "list_projects": {
        "en": "List projects with their keys, names, and issue types.",
        "es": "Lista los proyectos con sus claves, nombres y tipos de incidencia.",
    },
    "list_fields": {
        "en": "List all fields with id, name, custom flag, type, and allowed values.",
        "es": "Lista todos los campos con id, nombre, indicador custom, tipo y valores permitidos.",
    },
}

# Error message templates keyed by §4.4 code; en mirrors errors.EN_MESSAGES.
MESSAGES: dict[str, Mapping[str, str]] = {
    "en": EN_MESSAGES,
    "es": {
        "CONFIG_MISSING": (
            "Falta configuración. Ejecuta `mcp-jira setup` o crea `~/.config/mcp-jira/config.json`."
        ),
        "CONFIG_INVALID": (
            "Configuración no válida: {detail}. Corrige la configuración o vuelve "
            "a ejecutar `mcp-jira setup`."
        ),
        "AUTH_UNAUTHORIZED": (
            "Error de autenticación. Tu PAT no es válido o ha caducado. Genera uno "
            "nuevo en Administración de Jira → PAT."
        ),
        "AUTH_FORBIDDEN": (
            "No tienes permiso para realizar esta operación sobre el recurso de destino."
        ),
        "NOT_FOUND": "Recurso no encontrado: {detail}.",
        "VALIDATION_ERROR": "Solicitud no válida: {detail}.",
        "JQL_INVALID": "JQL no válido: {detail}.",
        "TRANSITION_INVALID": (
            "La transición '{name}' no está disponible. Disponibles: {available}."
        ),
        "FIELD_NOT_EDITABLE": "El campo '{name}' no es editable en esta incidencia/estado.",
        "RATE_LIMITED": "Se alcanzó el límite de peticiones de Jira. Reintenta después de {retry_after}.",
        "SERVER_ERROR": (
            "Error del servidor de Jira ({status}). Jira puede estar caído o sobrecargado."
        ),
        "NETWORK_ERROR": "No se pudo conectar con Jira en {url}: {detail}.",
        "READ_ONLY_MODE": "El modo de solo lectura está activado. Esta mutación está bloqueada.",
        "INTERNAL": "Error inesperado: {detail}. Esto es un error — repórtalo.",
    },
}


def tool_name(tool_id: str, language: str = "en") -> str:
    """Localized tool name; unknown language/tool falls back to the en name."""
    lang = language if language in LANGUAGES else "en"
    return _TOOL_NAMES.get(tool_id, {}).get(lang) or tool_id


def tool_description(tool_id: str, language: str = "en") -> str:
    """Localized tool description; unknown language falls back to English."""
    lang = language if language in LANGUAGES else "en"
    return _TOOL_DESCRIPTIONS.get(tool_id, {}).get(lang) or ""


def message(code: str, language: str = "en", **kwargs: Any) -> str:
    """Render a localized error template; unknown language/code falls back to en."""
    lang = language if language in LANGUAGES else "en"
    template = MESSAGES[lang].get(code) or MESSAGES["en"].get(code) or EN_MESSAGES["INTERNAL"]
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return EN_MESSAGES["INTERNAL"].format(detail=code)
