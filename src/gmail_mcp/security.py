"""Content sanitization, prompt injection defense, and audit logging."""

import logging

logger = logging.getLogger("gmail-mcp.audit")


def log_tool_call(tool_name: str, user_id: str, arg_keys: list[str]) -> None:
    """Log a tool invocation for audit purposes. Never logs full content."""
    logger.info("TOOL=%s USER=%s ARGS=%s", tool_name, user_id, arg_keys)


def sanitize_email_content(email_data: dict) -> dict:
    """Wrap untrusted content in XML-style delimiters.

    Returns a new dict — does not mutate the input. This prevents
    double-wrapping if the same parsed dict is ever reused.
    """
    result = dict(email_data)
    if "subject" in result:
        result["subject"] = f"<email_subject>{result['subject']}</email_subject>"
    if "body" in result:
        result["body"] = f"<email_body>\n{result['body']}\n</email_body>"
    if "from" in result:
        result["from"] = f"<email_from>{result['from']}</email_from>"
    if "to" in result:
        result["to"] = f"<email_to>{result['to']}</email_to>"
    if "snippet" in result:
        result["snippet"] = f"<email_snippet>{result['snippet']}</email_snippet>"
    return result
