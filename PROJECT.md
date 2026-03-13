# Gmail MCP Server — Design Specification

## Overview

A secure, minimal MCP (Model Context Protocol) server providing Gmail access to AI assistants. Security is the top priority — the server is hardened against prompt injection, credential theft, and unauthorized actions.

## Background on MCP

MCP is Anthropic's open standard for connecting AI assistants to external tools. An MCP server exposes "tools" that the AI can invoke over stdio using JSON-RPC.

Key concepts:

- **Tools**: Functions the AI can call (e.g., `gmail_search`, `gmail_get_email`)
- **Tool schemas**: JSON Schema definitions describing each tool's inputs
- **stdio transport**: Communication via stdin/stdout (stdout reserved for JSON-RPC, stderr for logging)
- **`mcp` Python package**: Provides the server framework

## Security Requirements (Non-Negotiable)

Based on known MCP security risks (prompt injection, credential exfiltration, unauthorized actions):

### 1. Minimal OAuth Scopes

```python
# Default: read-only scope
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Added dynamically based on enabled tools:
# "https://www.googleapis.com/auth/gmail.compose"  (gmail_create_draft)
# "https://www.googleapis.com/auth/gmail.labels"   (gmail_create/update/delete_label)
# "https://www.googleapis.com/auth/gmail.modify"   (gmail_modify_labels)

# NEVER permitted:
# "https://mail.google.com/"
```

OAuth scopes are dynamically resolved based on which tools are enabled — no unnecessary permissions are requested.

### 2. Credential Storage (Multi-Tier)

Credentials are resolved in priority order:

1. **Environment variables** — `GMAIL_REFRESH_TOKEN` + `GMAIL_CLIENT_ID` + `GMAIL_CLIENT_SECRET` (stateless, for Docker/CI/MCP clients)
2. **Token file** — `~/.config/gmail-mcp/accounts/<email>/token.json` with `600` permissions (cross-platform, written by `auth` subcommand)

Client secrets can be provided via `--client-secrets` flag or `GMAIL_CLIENT_SECRETS` env var.

### 3. No Direct Email Sending

The server NEVER sends emails. Draft creation is the maximum write capability — the user must manually send from Gmail.

### 4. No Arbitrary File Writes

Attachments are returned as base64-encoded data — never written to disk.

### 5. Prompt Injection Defense

All untrusted content (email bodies, subjects, sender names, snippets) is wrapped in XML-style delimiters before returning to the AI:

```python
def sanitize_email_content(email: dict) -> dict:
    email["body"] = f"<email_body>\n{email['body']}\n</email_body>"
    email["subject"] = f"<email_subject>{email['subject']}</email_subject>"
    email["from"] = f"<email_from>{email['from']}</email_from>"
    email["to"] = f"<email_to>{email['to']}</email_to>"
    email["snippet"] = f"<email_snippet>{email['snippet']}</email_snippet>"
    return email
```

### 6. Audit Logging

Every tool invocation is logged with timestamp, tool name, account, and argument keys (not values):

```python
logger.info("TOOL=%s USER=%s ARGS=%s", tool_name, user_id, arg_keys)
```

## Architecture

### Project Structure

```
src/gmail_mcp/
├── __init__.py
├── __main__.py        # CLI: auth + serve subcommands
├── auth.py            # OAuth flow + multi-tier credential storage
├── gmail_client.py    # Gmail API wrapper
├── server.py          # MCP server setup + tool dispatch
├── tools.py           # Tool definitions and input schemas
├── security.py        # Content sanitization + audit logging
└── access_control.py  # Tiered access system + scope resolution
```

### CLI Interface

Two subcommands:

```bash
# One-time: authenticate an account (opens browser)
python -m gmail_mcp auth --account user@example.com --client-secrets client_secret.json

# Run the MCP server (never opens browser)
python -m gmail_mcp serve --account user@example.com --preset read-only
```

Account sources (mutually compatible):
- `--account EMAIL` (repeated for multi-account)
- `--accounts-file accounts.json` (for complex configs with overrides)

### MCP Client Integration

The server is configured in the MCP client's JSON config. Environment variables are the standard pattern for secrets:

```json
{
  "mcpServers": {
    "gmail": {
      "command": "python",
      "args": ["-m", "gmail_mcp", "serve", "--account", "user@example.com"],
      "env": {
        "GMAIL_CLIENT_ID": "xxxxx.apps.googleusercontent.com",
        "GMAIL_CLIENT_SECRET": "GOCSPX-xxxxx",
        "GMAIL_REFRESH_TOKEN": "1//xxxxx"
      }
    }
  }
}
```

Or with file-based tokens (after running `auth` subcommand):

```json
{
  "mcpServers": {
    "gmail": {
      "command": "python",
      "args": ["-m", "gmail_mcp", "serve", "--account", "user@example.com"]
    }
  }
}
```

## Tools

Eleven tools across two tiers:

### Read-Only (default)

| Tool | Description |
|------|-------------|
| `gmail_get_profile` | Returns email and profile info. Confirms which account is connected. |
| `gmail_search` | Search using Gmail query syntax. Returns metadata (subject, from, date, snippet) — not full body. |
| `gmail_get_email` | Retrieve complete email by ID. Content wrapped in XML delimiters (highest prompt injection risk surface). |
| `gmail_get_thread` | Get all messages in a conversation thread. Each message individually sanitized. |
| `gmail_list_labels` | List all labels/folders in the account. |
| `gmail_get_attachment` | Download attachment as base64. Never written to disk. |

### Standard (adds write operations)

| Tool | Description | Scope |
|------|-------------|-------|
| `gmail_create_draft` | Create a draft email. Does NOT send — user must manually send from Gmail. Supports reply threading via `reply_to_id`. | `gmail.compose` |
| `gmail_create_label` | Create a new label/folder. Supports nested labels via `/`. | `gmail.labels` |
| `gmail_update_label` | Rename an existing label. | `gmail.labels` |
| `gmail_delete_label` | Delete a label. Messages are kept, only the label is removed. | `gmail.labels` |
| `gmail_modify_labels` | Add/remove labels on messages. Used for archiving, marking read/unread, moving. | `gmail.modify` |

## Tiered Access Control

### Design Principle

Secure by default, progressively unlockable. Users who run with no configuration get the safest behavior. Expanding capabilities requires explicit opt-in.

### Presets

**`read-only` (default)** — 6 read tools enabled, no write capability.

**`standard`** — All 11 tools. Adds draft creation, label CRUD, and message label modification. No dangerous operations (sending, permanent deletion, filter management) are implemented.

### Individual Overrides

Overrides layer on top of presets:

```json
{
  "tool_access": {
    "preset": "read-only",
    "overrides": {
      "gmail_create_draft": true
    }
  }
}
```

CLI overrides take precedence over config file:

```bash
python -m gmail_mcp serve --account user@example.com --enable-tool gmail_create_draft
```

### Scope Alignment

OAuth scopes are dynamically determined from enabled tools via `TOOL_SCOPE_REQUIREMENTS`:

```python
TOOL_SCOPE_REQUIREMENTS = {
    "gmail_create_draft": "gmail.compose",
    "gmail_create_label": "gmail.labels",
    "gmail_update_label": "gmail.labels",
    "gmail_delete_label": "gmail.labels",
    "gmail_modify_labels": "gmail.modify",
}
```

Only the scopes required by enabled tools are requested. Changing presets or enabling new tools may trigger re-authentication if stored credentials lack the required scope.

## MCP Server Pattern

```python
app = Server("gmail-mcp-secure")

@app.list_tools()
async def list_tools() -> list[Tool]:
    # Returns ONLY tools enabled in current config
    enabled = get_enabled_tools(config)
    return [t for name, t in ALL_TOOL_DEFINITIONS.items() if name in enabled]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Defense-in-depth: verify tool is enabled even though list_tools filtered it
    if name not in get_enabled_tools(config):
        raise ValueError(f"Tool '{name}' is not enabled")
    log_tool_call(name, arguments.get("account"), list(arguments.keys()))
    return await TOOL_HANDLERS[name](arguments)
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GMAIL_CLIENT_ID` | Google OAuth client ID |
| `GMAIL_CLIENT_SECRET` | Google OAuth client secret |
| `GMAIL_REFRESH_TOKEN` | OAuth refresh token — single-account (from `auth` subcommand) |
| `GMAIL_REFRESH_TOKEN_<SUFFIX>` | Per-account refresh token (e.g. `GMAIL_REFRESH_TOKEN_YOU_EXAMPLE_COM`) |
| `GMAIL_CLIENT_SECRETS` | Path to `client_secret.json` (alternative to `--client-secrets`) |
| `GMAIL_MCP_CONFIG_DIR` | Override config directory (default: `~/.config/gmail-mcp`) |

## Testing Checklist

1. **Authentication**: Tokens are stored in `~/.config/gmail-mcp/` with `600` permissions
2. **Env var auth**: Server authenticates using `GMAIL_REFRESH_TOKEN` + client ID/secret
3. **Scope minimality**: Only `gmail.readonly` requested in read-only mode; `gmail.compose`, `gmail.labels`, `gmail.modify` added only when corresponding tools are enabled
4. **Search**: `gmail_search` returns sanitized metadata for valid queries
5. **Content wrapping**: `gmail_get_email` body wrapped in `<email_body>` tags
6. **No send capability**: No code path exists to send emails
7. **Multi-account**: Multiple accounts can be queried independently
8. **Audit logs**: Every tool call logged to stderr
9. **Error handling**: Invalid IDs return graceful errors, not stack traces
10. **Access control**: Disabled tools return clear error messages, not silent failures

## Security Assumptions

The design assumes:
- The AI may be tricked by malicious email content (prompt injection)
- OAuth tokens are high-value targets
- Any write capability could be abused for data exfiltration
- When in doubt, remove the feature rather than risk security
