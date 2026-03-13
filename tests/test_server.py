"""Tests for MCP server tool dispatch and access control enforcement."""

import pytest

import gmail_mcp.server as server_module
from gmail_mcp.server import call_tool, list_tools


@pytest.fixture(autouse=True)
def _reset_server_config():
    """Reset server config between tests."""
    original_config = server_module.config
    server_module.config = {}
    yield
    server_module.config = original_config


class TestListTools:
    @pytest.mark.asyncio
    async def test_read_only_returns_6_tools(self):
        server_module.config = {"tool_access": {"preset": "read-only"}}
        tools = await list_tools()
        assert len(tools) == 6
        names = {t.name for t in tools}
        assert "gmail_search" in names
        assert "gmail_create_draft" not in names

    @pytest.mark.asyncio
    async def test_standard_returns_11_tools(self):
        server_module.config = {"tool_access": {"preset": "standard"}}
        tools = await list_tools()
        assert len(tools) == 11
        names = {t.name for t in tools}
        assert "gmail_create_draft" in names
        assert "gmail_modify_labels" in names


class TestCallToolAccessControl:
    @pytest.mark.asyncio
    async def test_disabled_tool_raises(self):
        server_module.config = {"tool_access": {"preset": "read-only"}}
        with pytest.raises(ValueError, match="not enabled"):
            await call_tool("gmail_create_draft", {"account": "test@example.com"})

    @pytest.mark.asyncio
    async def test_disabled_tool_error_mentions_preset(self):
        server_module.config = {"tool_access": {"preset": "read-only"}}
        with pytest.raises(ValueError, match="read-only"):
            await call_tool("gmail_modify_labels", {"account": "test@example.com"})

    @pytest.mark.asyncio
    async def test_unknown_tool_raises(self):
        server_module.config = {"tool_access": {"preset": "standard"}}
        with pytest.raises(ValueError, match="not enabled"):
            await call_tool("gmail_send_email", {"account": "test@example.com"})


class TestToolDefinitions:
    """Validate structural properties of all tool definitions."""

    @pytest.mark.asyncio
    async def test_all_tools_have_account_param(self):
        server_module.config = {"tool_access": {"preset": "standard"}}
        tools = await list_tools()
        for tool in tools:
            props = tool.inputSchema.get("properties", {})
            assert "account" in props, f"{tool.name} missing 'account' parameter"

    @pytest.mark.asyncio
    async def test_all_tools_require_account(self):
        server_module.config = {"tool_access": {"preset": "standard"}}
        tools = await list_tools()
        for tool in tools:
            required = tool.inputSchema.get("required", [])
            assert "account" in required, f"{tool.name} does not require 'account'"

    @pytest.mark.asyncio
    async def test_all_tools_disallow_additional_properties(self):
        server_module.config = {"tool_access": {"preset": "standard"}}
        tools = await list_tools()
        for tool in tools:
            assert tool.inputSchema.get("additionalProperties") is False, (
                f"{tool.name} allows additional properties"
            )
