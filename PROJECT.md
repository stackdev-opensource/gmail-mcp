# Prompt: Build a Secure Gmail MCP Server

## Context

I need you to build a secure, minimal MCP (Model Context Protocol) server that provides Gmail access to AI assistants like Claude. This server will run locally on my Mac Mini M1 and connect to my Google Workspace account for a B2B company (FuelBuddy). Security is paramount — the server must be hardened against prompt injection attacks and credential theft.

## Background on MCP

MCP (Model Context Protocol) is Anthropic's open standard for connecting AI assistants to external tools. An MCP server exposes "tools" that the AI can invoke. The server communicates with the AI client (like Claude Desktop or OpenFang) over stdio using JSON-RPC.

Key MCP concepts:
- **Tools**: Functions the AI can call (e.g., `query_emails`, `get_email`)
- **Tool schemas**: JSON Schema definitions describing each tool's inputs
- **stdio transport**: Communication happens via stdin/stdout, not HTTP
- **mcp Python package**: `pip install mcp` provides the server framework

## Security Requirements (Critical)

Based on recent MCP security incidents (CVE-2025-6514, Asana data leak, 11.ai calendar exfiltration), implement these safeguards:

### 1. Minimal OAuth Scopes
```python
# ONLY use read-only scope for Gmail
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
]

# If draft creation is needed, add ONLY:
# "https://www.googleapis.com/auth/gmail.compose"

# NEVER use the full-access scope:
# "https://mail.google.com/"  # DO NOT USE
```

### 2. Secure Credential Storage (macOS Keychain)
```python
import keyring

def store_token(email: str, token_data: str):
    keyring.set_password("gmail-mcp", email, token_data)

def get_token(email: str) -> str | None:
    return keyring.get_password("gmail-mcp", email)
```

### 3. No Direct Email Sending
The server must NOT implement any tool that sends emails directly. Draft creation is acceptable (user must manually send from Gmail), but no `send=True` capability.

### 4. No Arbitrary File Writes
Attachments should be returned as base64 data in the response, NOT written to disk. If file writing is absolutely needed, restrict to a single hardcoded directory with filename sanitization.

### 5. Prompt Injection Defense
Wrap all untrusted content (email bodies, subjects, sender names) in clear delimiters:
```python
def sanitize_email_content(email: dict) -> dict:
    """Wrap untrusted content to help LLM distinguish data from instructions."""
    email["body"] = f"<email_body>\n{email['body']}\n</email_body>"
    email["subject"] = f"<email_subject>{email['subject']}</email_subject>"
    return email
```

### 6. Audit Logging
Log every tool invocation with timestamp, tool name, and argument summary (not full content):
```python
import logging
logger = logging.getLogger("gmail-mcp.audit")

def log_tool_call(tool_name: str, user_id: str, arg_keys: list[str]):
    logger.info(f"TOOL={tool_name} USER={user_id} ARGS={arg_keys}")
```

## Technical Specifications

### Dependencies
```toml
[project]
name = "gmail-mcp-secure"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.3.0",
    "google-auth>=2.29.0",
    "google-auth-oauthlib>=1.2.0",
    "google-api-python-client>=2.154.0",
    "keyring>=25.0.0",
    "pydantic>=2.0.0",
]
```

### Project Structure
```
gmail-mcp-secure/
├── pyproject.toml
├── README.md
├── src/
│   └── gmail_mcp/
│       ├── __init__.py
│       ├── __main__.py      # Entry point: python -m gmail_mcp
│       ├── auth.py          # OAuth + Keychain storage
│       ├── gmail_client.py  # Gmail API wrapper
│       ├── server.py        # MCP server setup
│       ├── tools.py         # Tool definitions
│       └── security.py      # Sanitization, logging
└── config/
    └── example.accounts.json
```

## Tools to Implement

Implement ONLY these tools (read-heavy, minimal write):

### 1. `gmail_get_profile`
Returns the authenticated user's email address and profile info. Useful for confirming which account is connected.

```python
{
    "name": "gmail_get_profile",
    "description": "Get the authenticated Gmail user's profile information including email address.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account": {
                "type": "string",
                "description": "Email address of the account to query"
            }
        },
        "required": ["account"]
    }
}
```

### 2. `gmail_search`
Search emails using Gmail's query syntax. Returns metadata only (not full body).

```python
{
    "name": "gmail_search",
    "description": "Search Gmail using query syntax. Returns email metadata (subject, from, date, snippet) without full body content. Use gmail_get_email to retrieve full content.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account": {"type": "string", "description": "Email address of the account"},
            "query": {
                "type": "string", 
                "description": "Gmail search query (e.g., 'is:unread', 'from:example@gmail.com', 'newer_than:7d', 'subject:invoice')"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum emails to return (1-100)",
                "default": 20,
                "minimum": 1,
                "maximum": 100
            }
        },
        "required": ["account", "query"]
    }
}
```

### 3. `gmail_get_email`
Retrieve full email content by ID. This is where prompt injection risk is highest — wrap content in delimiters.

```python
{
    "name": "gmail_get_email",
    "description": "Retrieve a complete email by ID including full body content. Content is wrapped in XML-style tags to clearly separate email data from instructions.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account": {"type": "string"},
            "email_id": {"type": "string", "description": "The Gmail message ID"}
        },
        "required": ["account", "email_id"]
    }
}
```

### 4. `gmail_get_thread`
Get all messages in a conversation thread.

```python
{
    "name": "gmail_get_thread",
    "description": "Retrieve all messages in an email thread/conversation.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account": {"type": "string"},
            "thread_id": {"type": "string", "description": "The Gmail thread ID"}
        },
        "required": ["account", "thread_id"]
    }
}
```

### 5. `gmail_list_labels`
List all Gmail labels (folders) in the account.

```python
{
    "name": "gmail_list_labels",
    "description": "List all labels (folders) in the Gmail account.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account": {"type": "string"}
        },
        "required": ["account"]
    }
}
```

### 6. `gmail_create_draft` (Optional — can omit for pure read-only)
Create a draft email. Does NOT send — user must manually send from Gmail.

```python
{
    "name": "gmail_create_draft",
    "description": "Create a draft email. The draft is saved in Gmail's Drafts folder and must be manually sent by the user. This tool cannot send emails directly.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account": {"type": "string"},
            "to": {"type": "string", "description": "Recipient email address"},
            "subject": {"type": "string"},
            "body": {"type": "string", "description": "Plain text email body"},
            "cc": {
                "type": "array",
                "items": {"type": "string"},
                "description": "CC recipients (optional)"
            },
            "reply_to_id": {
                "type": "string",
                "description": "If replying, the ID of the original message (optional)"
            }
        },
        "required": ["account", "to", "subject", "body"]
    }
}
```

## OAuth Setup Flow

Use the modern `google-auth-oauthlib` library (NOT deprecated `oauth2client`):

```python
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_credentials(email: str, client_secrets_path: str) -> Credentials:
    """Get valid credentials, refreshing or re-authenticating as needed."""
    
    # Try to load from Keychain
    token_json = get_token_from_keychain(email)
    
    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
        if creds.valid:
            return creds
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            store_token_in_keychain(email, creds.to_json())
            return creds
    
    # Need fresh authentication
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
    creds = flow.run_local_server(port=4100)
    store_token_in_keychain(email, creds.to_json())
    return creds
```

## Multi-Account Support

Support multiple Google accounts via a config file:

```json
// accounts.json
{
    "accounts": [
        {
            "email": "shreesh@fuelbuddy.io",
            "type": "work",
            "description": "FuelBuddy primary work account"
        },
        {
            "email": "personal@gmail.com",
            "type": "personal", 
            "description": "Personal Gmail"
        }
    ]
}
```

The `account` parameter in each tool specifies which account to use.

## MCP Server Implementation Pattern

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

app = Server("gmail-mcp-secure")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="gmail_search", description="...", inputSchema={...}),
        Tool(name="gmail_get_email", description="...", inputSchema={...}),
        # ... other tools
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Log the call
    log_tool_call(name, arguments.get("account", "unknown"), list(arguments.keys()))
    
    # Dispatch to handler
    if name == "gmail_search":
        return await handle_gmail_search(arguments)
    elif name == "gmail_get_email":
        return await handle_gmail_get_email(arguments)
    # ... etc
    
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Configuration for OpenFang/Claude Desktop

```toml
# OpenFang config.toml
[[mcp_servers]]
name = "gmail"
timeout_secs = 30

[mcp_servers.transport]
type = "stdio"
command = "python"
args = ["-m", "gmail_mcp", "--accounts", "/path/to/accounts.json", "--client-secrets", "/path/to/client_secret.json"]
```

```json
// Claude Desktop claude_desktop_config.json
{
    "mcpServers": {
        "gmail": {
            "command": "python",
            "args": ["-m", "gmail_mcp", "--accounts", "/path/to/accounts.json", "--client-secrets", "/path/to/client_secret.json"]
        }
    }
}
```

## Testing Checklist

Before deployment, verify:

1. **Authentication works**: Can authenticate and tokens are stored in Keychain (not filesystem)
2. **Scope is minimal**: Check Google Cloud Console shows only `gmail.readonly` (or + `gmail.compose`)
3. **Search works**: `gmail_search` returns results for valid queries
4. **Content wrapping**: `gmail_get_email` returns body wrapped in `<email_body>` tags
5. **No send capability**: Confirm there's no way to send emails directly
6. **Multi-account**: Both accounts can be queried independently
7. **Audit logs**: Tool invocations appear in logs
8. **Error handling**: Invalid email IDs return graceful errors, not stack traces

## Configurable Tool Access (Critical Design Requirement)

The server must implement a **tiered access system** that follows the principle of "secure by default, progressively unlockable." Users who run the server with no configuration should get the safest possible behavior. Users who need additional capabilities must explicitly opt into them, creating a deliberate moment of acknowledging the added risk.

This design serves multiple purposes. First, it protects casual users who just want basic functionality from accidentally exposing themselves to risks they don't understand. Second, it creates a clear audit trail of what capabilities are enabled. Third, it allows the same codebase to serve both paranoid security-conscious deployments and more permissive setups where convenience matters more.

### The Tier System

Rather than exposing individual toggles for each tool (which would be tedious and error-prone) or having a single on/off switch (which is too coarse), implement **preset tiers** that cover common use cases. Each tier represents a coherent set of capabilities that make sense together.

**Tier 1: `read-only`** — This is the default tier that applies when users don't specify anything in their configuration. It enables only tools that read data and cannot modify anything. This tier is appropriate for users who want their AI assistant to help them search, summarize, and understand their email without any risk of the AI taking actions on their behalf.

```python
TIER_READ_ONLY = {
    "gmail_get_profile": True,
    "gmail_search": True,
    "gmail_get_email": True,
    "gmail_get_thread": True,
    "gmail_list_labels": True,
    "gmail_create_draft": False,  # Disabled — no write capability
}
```

**Tier 2: `standard`** — This tier adds the ability to create email drafts. Drafts are a relatively safe form of write access because they require manual user action to actually send. The AI can compose a reply, but the user must open Gmail and click Send themselves. This tier suits users who want help composing emails but still want to maintain final control over what actually gets sent.

```python
TIER_STANDARD = {
    "gmail_get_profile": True,
    "gmail_search": True,
    "gmail_get_email": True,
    "gmail_get_thread": True,
    "gmail_list_labels": True,
    "gmail_create_draft": True,  # Enabled — can create drafts
}
```

The design intentionally stops at two tiers because this server does not implement more dangerous operations like sending emails directly, deleting messages, or managing filters. If you were to add such features in the future, they would belong in a third `full` tier that users must very deliberately enable.

### Individual Tool Overrides

In addition to the preset tiers, allow users to override individual tool settings. This handles edge cases where someone wants most of a tier's capabilities but needs to add or remove one specific tool. The override mechanism works on top of the preset, not instead of it.

The configuration file structure should look like this:

```json
{
  "accounts": [
    {
      "email": "shreesh@fuelbuddy.io",
      "type": "work",
      "description": "FuelBuddy work account"
    }
  ],
  
  "tool_access": {
    "preset": "read-only",
    
    "overrides": {
      "gmail_create_draft": true
    }
  }
}
```

In this example, the user starts with the read-only preset but then enables draft creation via an override. The result is equivalent to the standard tier, but expressed differently. This flexibility matters because users think about their needs in different ways — some think "I want read-only plus drafts" while others think "I want standard."

### Implementation Pattern

Here is how to implement the tier resolution logic. The key insight is that the preset provides the baseline, and overrides are applied on top of it. If no preset is specified, default to the most restrictive tier for safety.

```python
# In config.py or a dedicated access_control.py module

from enum import Enum

class ToolPreset(str, Enum):
    READ_ONLY = "read-only"
    STANDARD = "standard"

# Define the tool sets for each tier
# Using a dictionary makes it easy to add new tiers later
GMAIL_TOOL_TIERS: dict[ToolPreset, dict[str, bool]] = {
    ToolPreset.READ_ONLY: {
        "gmail_get_profile": True,
        "gmail_search": True,
        "gmail_get_email": True,
        "gmail_get_thread": True,
        "gmail_list_labels": True,
        "gmail_create_draft": False,
    },
    ToolPreset.STANDARD: {
        "gmail_get_profile": True,
        "gmail_search": True,
        "gmail_get_email": True,
        "gmail_get_thread": True,
        "gmail_list_labels": True,
        "gmail_create_draft": True,
    },
}

def get_enabled_tools(config: dict) -> set[str]:
    """
    Determine which tools are enabled based on the configuration.
    
    This function resolves the final set of enabled tools by:
    1. Starting with the preset tier (defaulting to read-only if not specified)
    2. Applying any individual overrides from the config
    
    Returns a set of tool names that should be exposed to the AI.
    """
    
    # Extract the tool_access section, defaulting to empty dict if missing
    tool_access = config.get("tool_access", {})
    
    # Get the preset name, defaulting to read-only for maximum safety
    preset_name = tool_access.get("preset", "read-only")
    
    # Convert to enum (this will raise ValueError if invalid preset name)
    try:
        preset = ToolPreset(preset_name)
    except ValueError:
        raise ValueError(
            f"Invalid preset '{preset_name}'. "
            f"Valid options are: {[p.value for p in ToolPreset]}"
        )
    
    # Start with the tools enabled by the preset
    enabled = {
        tool_name 
        for tool_name, is_enabled in GMAIL_TOOL_TIERS[preset].items() 
        if is_enabled
    }
    
    # Apply any overrides from the config
    # Overrides can both enable tools (True) or disable them (False)
    overrides = tool_access.get("overrides", {})
    for tool_name, should_enable in overrides.items():
        # Validate that the override refers to a real tool
        all_known_tools = set(GMAIL_TOOL_TIERS[ToolPreset.STANDARD].keys())
        if tool_name not in all_known_tools:
            raise ValueError(
                f"Unknown tool '{tool_name}' in overrides. "
                f"Valid tools are: {sorted(all_known_tools)}"
            )
        
        if should_enable:
            enabled.add(tool_name)
        else:
            enabled.discard(tool_name)
    
    return enabled
```

### Integrating with the MCP Server

The tool access configuration affects two parts of the server: the `list_tools` handler (which tells the AI what tools are available) and the `call_tool` handler (which executes tool invocations). Both must respect the configuration.

```python
# In server.py

# Store all tool definitions, regardless of whether they're enabled
# This makes it easy to enable/disable tools without changing the tool definitions
ALL_TOOL_DEFINITIONS = {
    "gmail_get_profile": Tool(
        name="gmail_get_profile",
        description="Get the authenticated Gmail user's profile information.",
        inputSchema={...}
    ),
    "gmail_search": Tool(
        name="gmail_search",
        description="Search Gmail using query syntax...",
        inputSchema={...}
    ),
    # ... other tools
}

# Similarly, store all tool handlers
ALL_TOOL_HANDLERS = {
    "gmail_get_profile": handle_get_profile,
    "gmail_search": handle_search,
    "gmail_get_email": handle_get_email,
    "gmail_get_thread": handle_get_thread,
    "gmail_list_labels": handle_list_labels,
    "gmail_create_draft": handle_create_draft,
}

@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    Return only the tools that are enabled in the current configuration.
    
    This is important because the AI will only see and attempt to use
    tools that appear in this list. By filtering here, we prevent the
    AI from even knowing about capabilities that are disabled.
    """
    enabled = get_enabled_tools(config)
    
    return [
        tool_def 
        for tool_name, tool_def in ALL_TOOL_DEFINITIONS.items() 
        if tool_name in enabled
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    Execute a tool invocation, but only if the tool is enabled.
    
    This check is defense-in-depth. The AI shouldn't try to call tools
    that weren't in list_tools(), but we verify anyway in case of bugs
    or if someone is probing the server directly.
    """
    enabled = get_enabled_tools(config)
    
    if name not in enabled:
        # Provide a helpful error message that explains what happened
        # and how to fix it, rather than a cryptic failure
        current_preset = config.get("tool_access", {}).get("preset", "read-only")
        raise ValueError(
            f"Tool '{name}' is not enabled in the current configuration. "
            f"Current preset: '{current_preset}'. "
            f"To enable this tool, either change to a preset that includes it, "
            f"or add it to the 'overrides' section of your config file."
        )
    
    # Log the tool invocation for audit purposes
    log_tool_call(name, arguments.get("account", "unknown"), list(arguments.keys()))
    
    # Dispatch to the appropriate handler
    handler = ALL_TOOL_HANDLERS.get(name)
    if not handler:
        raise ValueError(f"No handler registered for tool: {name}")
    
    return await handler(arguments)
```

### Command-Line Overrides for Quick Testing

In addition to the configuration file, provide command-line arguments that allow users to temporarily change the tool access settings without editing their config. This is valuable during development, testing, or when a user needs to do something once without permanently changing their setup.

```python
# In __main__.py

import argparse
import json
import asyncio

def main():
    parser = argparse.ArgumentParser(
        description="Secure Gmail MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default read-only preset
  python -m gmail_mcp --accounts accounts.json --client-secrets secret.json
  
  # Run with standard preset (enables drafts)
  python -m gmail_mcp --accounts accounts.json --client-secrets secret.json --preset standard
  
  # Run read-only but enable just the draft tool
  python -m gmail_mcp --accounts accounts.json --client-secrets secret.json --enable-tool gmail_create_draft
        """
    )
    
    # Required arguments
    parser.add_argument(
        "--accounts", 
        required=True, 
        help="Path to accounts.json configuration file"
    )
    parser.add_argument(
        "--client-secrets", 
        required=True, 
        help="Path to Google OAuth client secrets JSON file"
    )
    
    # Tool access arguments
    parser.add_argument(
        "--preset",
        choices=["read-only", "standard"],
        default=None,
        help="Override the tool preset from config file (default: read-only)"
    )
    parser.add_argument(
        "--enable-tool",
        action="append",
        dest="enable_tools",
        metavar="TOOL_NAME",
        help="Enable a specific tool (can be repeated for multiple tools)"
    )
    parser.add_argument(
        "--disable-tool",
        action="append",
        dest="disable_tools",
        metavar="TOOL_NAME",
        help="Disable a specific tool (can be repeated for multiple tools)"
    )
    
    args = parser.parse_args()
    
    # Load the base configuration from file
    with open(args.accounts) as f:
        config = json.load(f)
    
    # Ensure tool_access section exists
    if "tool_access" not in config:
        config["tool_access"] = {}
    if "overrides" not in config["tool_access"]:
        config["tool_access"]["overrides"] = {}
    
    # Apply command-line overrides (these take precedence over config file)
    if args.preset:
        config["tool_access"]["preset"] = args.preset
    
    if args.enable_tools:
        for tool in args.enable_tools:
            config["tool_access"]["overrides"][tool] = True
    
    if args.disable_tools:
        for tool in args.disable_tools:
            config["tool_access"]["overrides"][tool] = False
    
    # Store config globally for the server to access
    # (In a real implementation, you might use dependency injection instead)
    import gmail_mcp.server as server_module
    server_module.config = config
    server_module.client_secrets_path = args.client_secrets
    
    # Run the server
    asyncio.run(server_module.main())

if __name__ == "__main__":
    main()
```

### Aligning OAuth Scopes with Enabled Tools

An important security detail: the OAuth scopes you request should match the tools that are enabled. There's no reason to request `gmail.compose` scope if the user is running in read-only mode. Requesting minimal scopes follows the principle of least privilege and also builds user trust — they see exactly what permissions are being requested and nothing more.

```python
def get_required_scopes(enabled_tools: set[str]) -> list[str]:
    """
    Determine the minimum OAuth scopes required for the enabled tools.
    
    This function maps tools to the scopes they require, then returns
    the union of all required scopes. This ensures we request only
    what we need, nothing more.
    """
    
    # Base scope — always required for any Gmail access
    scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
    
    # Additional scopes required by specific tools
    # Using a mapping makes it easy to add new tools and their requirements
    tool_scope_requirements = {
        "gmail_create_draft": "https://www.googleapis.com/auth/gmail.compose",
        # If you add more tools that need additional scopes, add them here
        # "gmail_send_email": "https://www.googleapis.com/auth/gmail.send",
        # "gmail_modify_labels": "https://www.googleapis.com/auth/gmail.modify",
    }
    
    for tool_name, required_scope in tool_scope_requirements.items():
        if tool_name in enabled_tools:
            if required_scope not in scopes:
                scopes.append(required_scope)
    
    return scopes
```

When a user changes their configuration from read-only to standard, the next time the server tries to authenticate, it will request the additional `gmail.compose` scope. If the stored credentials don't have this scope, the user will be prompted to re-authenticate. This is intentional — it creates a visible moment where the user approves the expanded access through Google's consent screen.

### Documentation for Users

Include clear documentation in your README that explains the tier system, what each tier enables, and the security implications of each choice. Users should be able to make an informed decision about which tier is appropriate for their use case.

```markdown
## Tool Access Configuration

This server uses a tiered access model to balance functionality with security. 
By default, the server runs in the most restrictive mode. You can expand 
capabilities by choosing a different preset or enabling individual tools.

### Available Presets

#### `read-only` (default)

The safest option. Your AI assistant can search and read your emails but 
cannot create, modify, or delete anything. Choose this if you only need 
help finding information in your inbox or summarizing email threads.

**Enabled tools:**
- `gmail_get_profile` — Check which account is connected
- `gmail_search` — Find emails matching search criteria  
- `gmail_get_email` — Read the full content of an email
- `gmail_get_thread` — Read all messages in a conversation
- `gmail_list_labels` — See your folder/label structure

#### `standard`

Adds the ability to create email drafts. This is useful when you want your 
AI assistant to help compose replies or new emails. The drafts are saved in 
Gmail's Drafts folder — you must manually open Gmail and click Send to 
actually send them. The AI cannot send emails on its own.

**Additional tools:**
- `gmail_create_draft` — Compose and save draft emails

### Choosing a Preset

Think about what you actually need:

- **"I just want to search and read emails"** → Use `read-only`
- **"I want help writing replies"** → Use `standard`

When in doubt, start with `read-only`. You can always change it later.

### Configuration Examples

**Read-only (default behavior, no config needed):**
```json
{
  "accounts": [{"email": "you@example.com", "type": "work"}]
}
```

**Standard preset:**
```json
{
  "accounts": [{"email": "you@example.com", "type": "work"}],
  "tool_access": {
    "preset": "standard"
  }
}
```

**Read-only with just draft creation added:**
```json
{
  "accounts": [{"email": "you@example.com", "type": "work"}],
  "tool_access": {
    "preset": "read-only",
    "overrides": {
      "gmail_create_draft": true
    }
  }
}
```

### Security Considerations

Even in read-only mode, your AI assistant will see the content of your emails. 
Be aware that:

1. **Prompt injection risk**: Malicious emails might contain text designed to 
   trick AI assistants into unintended behavior. This server wraps email 
   content in special tags to help the AI distinguish email data from 
   instructions, but no defense is perfect.

2. **Sensitive information exposure**: The AI will have access to whatever 
   emails match your search queries. Consider this when connecting work 
   accounts that contain confidential information.

3. **Draft creation is relatively safe**: Even with `standard` preset, the AI 
   cannot send emails directly. Drafts require you to manually send them from 
   Gmail. This gives you a chance to review what the AI composed before it 
   actually goes out.
```

## Deliverables

Please provide:

1. Complete Python package with all source files
2. `pyproject.toml` with dependencies
3. `README.md` with setup instructions including the tool access documentation shown above
4. Example `accounts.json` config showing both minimal and full configuration
5. Instructions for creating GCP OAuth credentials

## Security Reminder

This server will have access to sensitive business email. The design must assume:
- The AI may be tricked by malicious email content (prompt injection)
- The OAuth tokens are high-value targets for attackers
- Any write capability could be abused for data exfiltration

When in doubt, remove the feature rather than risk security.
