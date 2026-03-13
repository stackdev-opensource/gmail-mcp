# Gmail MCP Server (Secure)

[![PyPI](https://img.shields.io/pypi/v/gmail-mcp-secure)](https://pypi.org/project/gmail-mcp-secure/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A secure [MCP](https://modelcontextprotocol.io/) server that gives AI assistants like Claude access to Gmail. Security-first design — hardened against prompt injection, credential theft, and unauthorized actions.

**Why this one?** Unlike other Gmail MCP servers, this one ships with tiered access control, prompt injection defense, audit logging, and a no-send-by-design policy. Read more in [Security](#security).

## Quick Start

### 1. Install

```bash
pip install gmail-mcp-secure
```

Requires Python 3.11+.

### 2. Set up Google Cloud

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the **Gmail API** (APIs & Services > Library)
3. Create **OAuth 2.0 credentials** (APIs & Services > Credentials > Create Credentials > OAuth client ID > Desktop app)
4. Download the JSON file as `client_secret.json`
5. Add your email as a **test user** in the OAuth consent screen

### 3. Authenticate

```bash
python -m gmail_mcp auth \
  --account you@example.com \
  --client-secrets client_secret.json
```

This opens a browser for Google consent, saves the token locally, and prints environment variables you can use instead.

### 4. Run

```bash
python -m gmail_mcp serve --account you@example.com
```

## MCP Client Integration

### Claude Desktop

Add to your config file:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "gmail": {
      "command": "python",
      "args": ["-m", "gmail_mcp", "serve", "--account", "you@example.com"]
    }
  }
}
```

### Claude Code

```bash
claude mcp add gmail -- python -m gmail_mcp serve --account you@example.com
```

### Environment Variables (Docker / CI / any client)

Instead of file-based tokens, pass credentials via environment variables:

```json
{
  "mcpServers": {
    "gmail": {
      "command": "python",
      "args": ["-m", "gmail_mcp", "serve", "--account", "you@example.com"],
      "env": {
        "GMAIL_CLIENT_ID": "xxxxx.apps.googleusercontent.com",
        "GMAIL_CLIENT_SECRET": "GOCSPX-xxxxx",
        "GMAIL_REFRESH_TOKEN": "1//xxxxx"
      }
    }
  }
}
```

The `auth` subcommand prints these values after authenticating.

### Multi-Account

```bash
python -m gmail_mcp serve \
  --account work@company.com \
  --account personal@gmail.com
```

For multi-account env vars, use per-account refresh tokens:

```
GMAIL_REFRESH_TOKEN_WORK_COMPANY_COM=1//xxxxx
GMAIL_REFRESH_TOKEN_PERSONAL_GMAIL_COM=1//yyyyy
```

The suffix is the email with `@`, `.`, `+` replaced by `_`, uppercased (e.g. `work@company.com` → `WORK_COMPANY_COM`). Falls back to `GMAIL_REFRESH_TOKEN` for single-account setups.

Or use a config file:

```bash
python -m gmail_mcp serve --accounts-file accounts.json
```

See [config/example.accounts.json](config/example.accounts.json) for the file format.

## Available Tools

### Read-Only (default)

| Tool | Description |
|------|-------------|
| `gmail_get_profile` | Get account profile info (email, message count) |
| `gmail_search` | Search emails using Gmail query syntax |
| `gmail_get_email` | Retrieve full email content by ID |
| `gmail_get_thread` | Get all messages in a conversation thread |
| `gmail_list_labels` | List all labels/folders |
| `gmail_get_attachment` | Download attachment as base64 (never written to disk) |

### Standard (includes all read-only tools, plus:)

| Tool | Description | Scope |
|------|-------------|-------|
| `gmail_create_draft` | Create a draft email (user must manually send) | `gmail.compose` |
| `gmail_create_label` | Create a new label/folder | `gmail.labels` |
| `gmail_update_label` | Rename an existing label | `gmail.labels` |
| `gmail_delete_label` | Delete a label (messages are kept) | `gmail.labels` |
| `gmail_modify_labels` | Add/remove labels on messages (archive, mark read/unread, move) | `gmail.modify` |

## Tool Access Configuration

By default, the server runs in `read-only` mode — the safest option.

### Presets

| Preset | What the AI can do |
|--------|-------------------|
| `read-only` | Search, read emails, list labels, download attachments |
| `standard` | All of the above + create drafts, manage labels, organize messages |

### Examples

```bash
# Standard preset (enables all write tools)
python -m gmail_mcp serve --account you@example.com --preset standard

# Read-only but enable just drafts
python -m gmail_mcp serve --account you@example.com --enable-tool gmail_create_draft

# Standard but disable label deletion
python -m gmail_mcp serve --account you@example.com --preset standard --disable-tool gmail_delete_label
```

When authenticating, match the preset so the correct OAuth scopes are requested:

```bash
python -m gmail_mcp auth --account you@example.com --preset standard --client-secrets client_secret.json
```

### Config File

```json
{
  "accounts": [{"email": "you@example.com"}],
  "tool_access": {
    "preset": "standard",
    "overrides": {
      "gmail_delete_label": false
    }
  }
}
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GMAIL_CLIENT_ID` | Google OAuth client ID (shared across all accounts) |
| `GMAIL_CLIENT_SECRET` | Google OAuth client secret (shared across all accounts) |
| `GMAIL_REFRESH_TOKEN` | OAuth refresh token (single-account setups) |
| `GMAIL_REFRESH_TOKEN_<SUFFIX>` | Per-account refresh token (e.g. `GMAIL_REFRESH_TOKEN_YOU_EXAMPLE_COM`) |
| `GMAIL_CLIENT_SECRETS` | Path to `client_secret.json` (alternative to `--client-secrets`) |
| `GMAIL_MCP_CONFIG_DIR` | Override config directory (default: `~/.config/gmail-mcp`) |

## Security

### Design Principles

1. **Read-only by default** — write operations must be explicitly enabled via preset or overrides
2. **No email sending** — draft creation only; no `send` capability exists in the codebase
3. **Minimal OAuth scopes** — only the scopes required by enabled tools are requested; never `https://mail.google.com/`
4. **Prompt injection defense** — all untrusted email content wrapped in XML-style delimiters
5. **Header injection prevention** — newlines rejected in email header fields
6. **Restrictive file permissions** — token files stored with `600` permissions (owner read/write only)
7. **Path traversal protection** — email addresses validated before constructing file paths
8. **Error isolation** — internal errors logged to stderr; only safe messages returned to the AI
9. **Audit logging** — every tool call logged with timestamp, tool name, and argument summary
10. **No arbitrary file writes** — attachments returned as base64, never written to disk

### Reporting Vulnerabilities

See [SECURITY.md](SECURITY.md) for our vulnerability disclosure policy.

## Development

```bash
git clone https://github.com/stackdev-opensource/gmail-mcp.git
cd gmail-mcp
uv venv --python 3.11 && source .venv/bin/activate
uv pip install -e ".[dev]"
ruff check src/
pytest
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE)
