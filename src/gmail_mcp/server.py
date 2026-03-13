"""MCP server setup and tool dispatch."""

import json
import logging

from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from gmail_mcp.access_control import get_enabled_tools, get_required_scopes
from gmail_mcp.auth import get_credentials
from gmail_mcp.gmail_client import GmailClient
from gmail_mcp.security import log_tool_call
from gmail_mcp.tools import ALL_TOOL_DEFINITIONS

logger = logging.getLogger("gmail-mcp.server")

# These are set by __main__.py before the server starts
config: dict = {}
client_secrets_path: str = ""

app = Server("gmail-mcp-secure")

# Cache authenticated Gmail clients per account
_clients: dict[str, GmailClient] = {}


def _get_client(account: str) -> GmailClient:
    """Get or create an authenticated GmailClient for the given account."""
    if account not in _clients:
        # Validate that the account is in the config
        configured_emails = {a["email"] for a in config.get("accounts", [])}
        if account not in configured_emails:
            raise ValueError(
                f"Account '{account}' is not configured. "
                f"Configured accounts: {sorted(configured_emails)}"
            )

        enabled_tools = get_enabled_tools(config)
        scopes = get_required_scopes(enabled_tools)
        credentials = get_credentials(account, client_secrets_path or None, scopes)
        _clients[account] = GmailClient(credentials)

    return _clients[account]


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Return only the tools enabled in the current configuration."""
    enabled = get_enabled_tools(config)
    return [
        tool_def for tool_name, tool_def in ALL_TOOL_DEFINITIONS.items() if tool_name in enabled
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a tool invocation, with access control and audit logging."""
    enabled = get_enabled_tools(config)

    if name not in enabled:
        current_preset = config.get("tool_access", {}).get("preset", "read-only")
        raise ValueError(
            f"Tool '{name}' is not enabled. "
            f"Current preset: '{current_preset}'. "
            f"Change the preset or add it to 'overrides' in your config."
        )

    log_tool_call(name, arguments.get("account", "unknown"), list(arguments.keys()))

    handler = TOOL_HANDLERS.get(name)
    if not handler:
        raise ValueError(f"No handler registered for tool: {name}")

    try:
        return await handler(arguments)
    except HttpError as e:
        # Gmail API error — return status and reason without leaking internals
        logger.exception("Gmail API error in %s", name)
        raise ValueError(f"Gmail API error ({e.resp.status}): {e.reason}") from None
    except GoogleAuthError:
        # Auth error — never leak token details
        logger.exception("Authentication error in %s", name)
        raise ValueError(
            f"Authentication failed for account '{arguments.get('account', 'unknown')}'. "
            f"Try re-running: python -m gmail_mcp auth --account {arguments.get('account', '')}"
        ) from None
    except ValueError:
        # Our own validation errors (e.g. header injection) — pass through
        raise
    except Exception:
        # Catch-all — log full trace to stderr, return safe message to AI
        logger.exception("Unexpected error in %s", name)
        raise ValueError(f"An unexpected error occurred while executing {name}") from None


# -- Tool handlers --


async def handle_get_profile(arguments: dict) -> list[TextContent]:
    client = _get_client(arguments["account"])
    profile = client.get_profile()
    return [TextContent(type="text", text=json.dumps(profile, indent=2))]


async def handle_search(arguments: dict) -> list[TextContent]:
    client = _get_client(arguments["account"])
    max_results = arguments.get("max_results", 20)
    max_results = max(1, min(100, max_results))
    results = client.search(arguments["query"], max_results=max_results)
    return [TextContent(type="text", text=json.dumps(results, indent=2))]


async def handle_get_email(arguments: dict) -> list[TextContent]:
    client = _get_client(arguments["account"])
    email_data = client.get_email(arguments["email_id"])
    return [TextContent(type="text", text=json.dumps(email_data, indent=2))]


async def handle_get_thread(arguments: dict) -> list[TextContent]:
    client = _get_client(arguments["account"])
    thread_data = client.get_thread(arguments["thread_id"])
    return [TextContent(type="text", text=json.dumps(thread_data, indent=2))]


async def handle_list_labels(arguments: dict) -> list[TextContent]:
    client = _get_client(arguments["account"])
    labels = client.list_labels()
    return [TextContent(type="text", text=json.dumps(labels, indent=2))]


async def handle_create_draft(arguments: dict) -> list[TextContent]:
    client = _get_client(arguments["account"])
    result = client.create_draft(
        to=arguments["to"],
        subject=arguments["subject"],
        body=arguments["body"],
        cc=arguments.get("cc"),
        reply_to_id=arguments.get("reply_to_id"),
    )
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def handle_get_attachment(arguments: dict) -> list[TextContent]:
    client = _get_client(arguments["account"])
    result = client.get_attachment(arguments["email_id"], arguments["attachment_id"])
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def handle_create_label(arguments: dict) -> list[TextContent]:
    client = _get_client(arguments["account"])
    result = client.create_label(arguments["name"])
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def handle_update_label(arguments: dict) -> list[TextContent]:
    client = _get_client(arguments["account"])
    result = client.update_label(arguments["label_id"], arguments["new_name"])
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def handle_delete_label(arguments: dict) -> list[TextContent]:
    client = _get_client(arguments["account"])
    result = client.delete_label(arguments["label_id"])
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def handle_modify_labels(arguments: dict) -> list[TextContent]:
    client = _get_client(arguments["account"])
    result = client.modify_labels(
        arguments["email_id"],
        add_labels=arguments.get("add_labels"),
        remove_labels=arguments.get("remove_labels"),
    )
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


TOOL_HANDLERS = {
    "gmail_get_profile": handle_get_profile,
    "gmail_search": handle_search,
    "gmail_get_email": handle_get_email,
    "gmail_get_thread": handle_get_thread,
    "gmail_list_labels": handle_list_labels,
    "gmail_get_attachment": handle_get_attachment,
    "gmail_create_label": handle_create_label,
    "gmail_update_label": handle_update_label,
    "gmail_delete_label": handle_delete_label,
    "gmail_modify_labels": handle_modify_labels,
    "gmail_create_draft": handle_create_draft,
}


async def main() -> None:
    """Run the MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
