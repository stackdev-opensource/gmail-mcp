# Gmail MCP Server — Project Instructions

## Project Overview

Secure MCP server providing Gmail access to AI assistants. Security is the top priority.

## Architecture

- `src/gmail_mcp/` — main package
  - `server.py` — MCP server setup and tool dispatch
  - `tools.py` — tool definitions and input schemas
  - `auth.py` — OAuth authentication (env vars, file-based tokens)
  - `gmail_client.py` — Gmail API wrapper
  - `security.py` — content sanitization, audit logging
  - `access_control.py` — tiered tool access and scope resolution
  - `__main__.py` — CLI entry point
- `config/` — example configuration files
- `PROJECT.md` — full specification and design document

## Key Conventions

- Python 3.11+, use modern syntax
- Ruff for linting (`ruff check src/`)
- All tools must be registered in the tiered access system
- Email content returned to the AI must be wrapped in XML delimiters (`<email_body>`, `<email_subject>`)
- OAuth tokens stored as file-based tokens (`~/.config/gmail-mcp/`) with 600 permissions, or via environment variables
- Permitted OAuth scopes: `gmail.readonly`, `gmail.compose`, `gmail.labels`, `gmail.modify` — never use `https://mail.google.com/`

## Security Rules (Non-Negotiable)

- NEVER implement email sending — only draft creation
- NEVER write attachments to disk — return as base64
- Token files MUST use restrictive permissions (600) — never world-readable
- NEVER add OAuth scopes beyond readonly, compose, labels, and modify
- ALL untrusted content must be sanitized before returning to the AI
- ALL tool invocations must be audit-logged

## Testing

- Tests live in `tests/`
- Run with `pytest`

## Git

- Do not commit `accounts.json`, `client_secret*.json`, or any credential files
