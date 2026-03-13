"""Tiered tool access system and OAuth scope resolution."""

from enum import StrEnum


class ToolPreset(StrEnum):
    READ_ONLY = "read-only"
    STANDARD = "standard"


GMAIL_TOOL_TIERS: dict[ToolPreset, dict[str, bool]] = {
    ToolPreset.READ_ONLY: {
        "gmail_get_profile": True,
        "gmail_search": True,
        "gmail_get_email": True,
        "gmail_get_thread": True,
        "gmail_list_labels": True,
        "gmail_get_attachment": True,
        "gmail_create_label": False,
        "gmail_update_label": False,
        "gmail_delete_label": False,
        "gmail_modify_labels": False,
        "gmail_create_draft": False,
    },
    ToolPreset.STANDARD: {
        "gmail_get_profile": True,
        "gmail_search": True,
        "gmail_get_email": True,
        "gmail_get_thread": True,
        "gmail_list_labels": True,
        "gmail_get_attachment": True,
        "gmail_create_label": True,
        "gmail_update_label": True,
        "gmail_delete_label": True,
        "gmail_modify_labels": True,
        "gmail_create_draft": True,
    },
}

# Maps tools to the additional OAuth scopes they require beyond gmail.readonly
TOOL_SCOPE_REQUIREMENTS: dict[str, str] = {
    "gmail_create_draft": "https://www.googleapis.com/auth/gmail.compose",
    "gmail_create_label": "https://www.googleapis.com/auth/gmail.labels",
    "gmail_update_label": "https://www.googleapis.com/auth/gmail.labels",
    "gmail_delete_label": "https://www.googleapis.com/auth/gmail.labels",
    "gmail_modify_labels": "https://www.googleapis.com/auth/gmail.modify",
}

SCOPE_READONLY = "https://www.googleapis.com/auth/gmail.readonly"


def get_enabled_tools(config: dict) -> set[str]:
    """Resolve the final set of enabled tools from preset + overrides.

    Defaults to read-only if no preset is specified.
    """
    tool_access = config.get("tool_access", {})
    preset_name = tool_access.get("preset", "read-only")

    try:
        preset = ToolPreset(preset_name)
    except ValueError:
        valid = [p.value for p in ToolPreset]
        raise ValueError(f"Invalid preset '{preset_name}'. Valid options: {valid}") from None

    enabled = {
        tool_name for tool_name, is_enabled in GMAIL_TOOL_TIERS[preset].items() if is_enabled
    }

    all_known_tools = set(GMAIL_TOOL_TIERS[ToolPreset.STANDARD].keys())
    overrides = tool_access.get("overrides", {})
    for tool_name, should_enable in overrides.items():
        if tool_name not in all_known_tools:
            raise ValueError(
                f"Unknown tool '{tool_name}' in overrides. Valid tools: {sorted(all_known_tools)}"
            )
        if should_enable:
            enabled.add(tool_name)
        else:
            enabled.discard(tool_name)

    return enabled


def get_required_scopes(enabled_tools: set[str]) -> list[str]:
    """Determine the minimum OAuth scopes required for the enabled tools."""
    scopes = [SCOPE_READONLY]

    for tool_name, required_scope in TOOL_SCOPE_REQUIREMENTS.items():
        if tool_name in enabled_tools and required_scope not in scopes:
            scopes.append(required_scope)

    return scopes
