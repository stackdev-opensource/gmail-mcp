"""MCP tool definitions and input schemas."""

from mcp.types import Tool

ALL_TOOL_DEFINITIONS: dict[str, Tool] = {
    "gmail_get_profile": Tool(
        name="gmail_get_profile",
        description=(
            "Get the authenticated Gmail user's profile information including email address."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Email address of the account to query",
                },
            },
            "required": ["account"],
            "additionalProperties": False,
        },
    ),
    "gmail_search": Tool(
        name="gmail_search",
        description=(
            "Search Gmail using query syntax. Returns email metadata "
            "(subject, from, date, snippet) without full body content. "
            "Use gmail_get_email to retrieve full content."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Email address of the account",
                },
                "query": {
                    "type": "string",
                    "description": (
                        "Gmail search query (e.g., 'is:unread', "
                        "'from:example@gmail.com', 'newer_than:7d', "
                        "'subject:invoice')"
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum emails to return (1-100)",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": ["account", "query"],
            "additionalProperties": False,
        },
    ),
    "gmail_get_email": Tool(
        name="gmail_get_email",
        description=(
            "Retrieve a complete email by ID including full body content. "
            "Content is wrapped in XML-style tags to clearly separate "
            "email data from instructions."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Email address of the account",
                },
                "email_id": {
                    "type": "string",
                    "description": "The Gmail message ID",
                },
            },
            "required": ["account", "email_id"],
            "additionalProperties": False,
        },
    ),
    "gmail_get_thread": Tool(
        name="gmail_get_thread",
        description="Retrieve all messages in an email thread/conversation.",
        inputSchema={
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Email address of the account",
                },
                "thread_id": {
                    "type": "string",
                    "description": "The Gmail thread ID",
                },
            },
            "required": ["account", "thread_id"],
            "additionalProperties": False,
        },
    ),
    "gmail_list_labels": Tool(
        name="gmail_list_labels",
        description="List all labels (folders) in the Gmail account.",
        inputSchema={
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Email address of the account",
                },
            },
            "required": ["account"],
            "additionalProperties": False,
        },
    ),
    "gmail_get_attachment": Tool(
        name="gmail_get_attachment",
        description=(
            "Download an email attachment and return it as base64-encoded data. "
            "Use gmail_get_email first to find attachment IDs. "
            "The attachment is never written to disk."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Email address of the account",
                },
                "email_id": {
                    "type": "string",
                    "description": "The Gmail message ID that contains the attachment",
                },
                "attachment_id": {
                    "type": "string",
                    "description": "The attachment ID from gmail_get_email results",
                },
            },
            "required": ["account", "email_id", "attachment_id"],
            "additionalProperties": False,
        },
    ),
    "gmail_create_label": Tool(
        name="gmail_create_label",
        description="Create a new label (folder) in the Gmail account.",
        inputSchema={
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Email address of the account",
                },
                "name": {
                    "type": "string",
                    "description": "Label name (use '/' for nested labels, e.g. 'Projects/Active')",
                },
            },
            "required": ["account", "name"],
            "additionalProperties": False,
        },
    ),
    "gmail_update_label": Tool(
        name="gmail_update_label",
        description="Rename an existing label.",
        inputSchema={
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Email address of the account",
                },
                "label_id": {
                    "type": "string",
                    "description": "The label ID (from gmail_list_labels)",
                },
                "new_name": {
                    "type": "string",
                    "description": "New name for the label",
                },
            },
            "required": ["account", "label_id", "new_name"],
            "additionalProperties": False,
        },
    ),
    "gmail_delete_label": Tool(
        name="gmail_delete_label",
        description=(
            "Delete a label. Messages with this label are NOT deleted, "
            "only the label is removed from them."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Email address of the account",
                },
                "label_id": {
                    "type": "string",
                    "description": "The label ID to delete (from gmail_list_labels)",
                },
            },
            "required": ["account", "label_id"],
            "additionalProperties": False,
        },
    ),
    "gmail_modify_labels": Tool(
        name="gmail_modify_labels",
        description=(
            "Add or remove labels on a message. Use this to archive (remove INBOX), "
            "mark as read (remove UNREAD), move to folders, or organize emails. "
            "Use gmail_list_labels to find label IDs."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Email address of the account",
                },
                "email_id": {
                    "type": "string",
                    "description": "The Gmail message ID",
                },
                "add_labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Label IDs to add (e.g. ['STARRED', 'Label_123'])",
                },
                "remove_labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Label IDs to remove (e.g. ['INBOX', 'UNREAD']). "
                        "Remove 'INBOX' to archive, remove 'UNREAD' to mark as read."
                    ),
                },
            },
            "required": ["account", "email_id"],
            "additionalProperties": False,
        },
    ),
    "gmail_create_draft": Tool(
        name="gmail_create_draft",
        description=(
            "Create a draft email. The draft is saved in Gmail's Drafts "
            "folder and must be manually sent by the user. This tool "
            "cannot send emails directly."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Email address of the account",
                },
                "to": {
                    "type": "string",
                    "description": "Recipient email address",
                },
                "subject": {"type": "string"},
                "body": {
                    "type": "string",
                    "description": "Plain text email body",
                },
                "cc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "CC recipients (optional)",
                },
                "reply_to_id": {
                    "type": "string",
                    "description": ("If replying, the ID of the original message (optional)"),
                },
            },
            "required": ["account", "to", "subject", "body"],
            "additionalProperties": False,
        },
    ),
}
