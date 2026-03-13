"""Tests for tiered access control and OAuth scope resolution."""

import pytest

from gmail_mcp.access_control import (
    SCOPE_READONLY,
    TOOL_SCOPE_REQUIREMENTS,
    get_enabled_tools,
    get_required_scopes,
)


class TestGetEnabledTools:
    def test_defaults_to_read_only(self):
        enabled = get_enabled_tools({})
        assert "gmail_search" in enabled
        assert "gmail_get_email" in enabled
        assert "gmail_create_draft" not in enabled
        assert "gmail_modify_labels" not in enabled

    def test_read_only_preset_explicit(self):
        config = {"tool_access": {"preset": "read-only"}}
        enabled = get_enabled_tools(config)
        assert len(enabled) == 6
        assert "gmail_create_draft" not in enabled

    def test_standard_preset(self):
        config = {"tool_access": {"preset": "standard"}}
        enabled = get_enabled_tools(config)
        assert len(enabled) == 11
        assert "gmail_create_draft" in enabled
        assert "gmail_modify_labels" in enabled
        assert "gmail_create_label" in enabled
        assert "gmail_delete_label" in enabled

    def test_override_enable_tool(self):
        config = {
            "tool_access": {
                "preset": "read-only",
                "overrides": {"gmail_create_draft": True},
            }
        }
        enabled = get_enabled_tools(config)
        assert "gmail_create_draft" in enabled
        # Other write tools still disabled
        assert "gmail_modify_labels" not in enabled

    def test_override_disable_tool(self):
        config = {
            "tool_access": {
                "preset": "standard",
                "overrides": {"gmail_delete_label": False},
            }
        }
        enabled = get_enabled_tools(config)
        assert "gmail_delete_label" not in enabled
        # Other standard tools still enabled
        assert "gmail_create_draft" in enabled

    def test_invalid_preset_raises(self):
        config = {"tool_access": {"preset": "admin"}}
        with pytest.raises(ValueError, match="Invalid preset"):
            get_enabled_tools(config)

    def test_unknown_tool_override_raises(self):
        config = {
            "tool_access": {
                "overrides": {"gmail_send_email": True},
            }
        }
        with pytest.raises(ValueError, match="Unknown tool"):
            get_enabled_tools(config)


class TestGetRequiredScopes:
    def test_readonly_tools_only_need_readonly_scope(self):
        enabled = {"gmail_search", "gmail_get_email", "gmail_list_labels"}
        scopes = get_required_scopes(enabled)
        assert scopes == [SCOPE_READONLY]

    def test_draft_adds_compose_scope(self):
        enabled = {"gmail_search", "gmail_create_draft"}
        scopes = get_required_scopes(enabled)
        assert SCOPE_READONLY in scopes
        assert "https://www.googleapis.com/auth/gmail.compose" in scopes

    def test_label_tools_add_labels_scope(self):
        enabled = {"gmail_search", "gmail_create_label"}
        scopes = get_required_scopes(enabled)
        assert "https://www.googleapis.com/auth/gmail.labels" in scopes

    def test_modify_labels_adds_modify_scope(self):
        enabled = {"gmail_search", "gmail_modify_labels"}
        scopes = get_required_scopes(enabled)
        assert "https://www.googleapis.com/auth/gmail.modify" in scopes

    def test_standard_preset_scopes(self):
        config = {"tool_access": {"preset": "standard"}}
        enabled = get_enabled_tools(config)
        scopes = get_required_scopes(enabled)
        assert SCOPE_READONLY in scopes
        assert "https://www.googleapis.com/auth/gmail.compose" in scopes
        assert "https://www.googleapis.com/auth/gmail.labels" in scopes
        assert "https://www.googleapis.com/auth/gmail.modify" in scopes
        assert len(scopes) == 4

    def test_no_duplicate_scopes(self):
        # Multiple label tools should not add gmail.labels twice
        enabled = {"gmail_create_label", "gmail_update_label", "gmail_delete_label"}
        scopes = get_required_scopes(enabled)
        assert scopes.count("https://www.googleapis.com/auth/gmail.labels") == 1

    def test_full_scope_never_present(self):
        """The unrestricted mail.google.com scope must never appear."""
        enabled = set(TOOL_SCOPE_REQUIREMENTS.keys())
        scopes = get_required_scopes(enabled)
        assert "https://mail.google.com/" not in scopes
