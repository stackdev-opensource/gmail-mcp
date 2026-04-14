"""Content sanitization, prompt injection defense, and audit logging."""

import json
import logging
import os
import threading
import urllib.error
import urllib.request

logger = logging.getLogger("gmail-mcp.audit")

# Optional HTTP audit sink — enabled when GMAIL_MCP_AUDIT_ENDPOINT is set.
# Events are POSTed in a daemon thread so a slow or unreachable sink never
# blocks tool execution.
_AUDIT_ENDPOINT = os.environ.get("GMAIL_MCP_AUDIT_ENDPOINT", "").strip()
_AUDIT_SERVER_NAME = os.environ.get("GMAIL_MCP_AUDIT_SERVER_NAME", "gmail_mcp").strip()
_AUDIT_TIMEOUT_SECONDS = 2.0


def _post_audit_event(payload: dict) -> None:
    """Best-effort POST of a single audit event. Never raises."""
    if not _AUDIT_ENDPOINT:
        return
    # Restrict to http/https — urllib.request.urlopen otherwise accepts file://
    # and other schemes that would turn an env var into a local-file read.
    if not _AUDIT_ENDPOINT.startswith(("http://", "https://")):
        logger.warning(
            "GMAIL_MCP_AUDIT_ENDPOINT must use http:// or https:// scheme; got %r",
            _AUDIT_ENDPOINT,
        )
        return
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(  # noqa: S310 — scheme validated above
            _AUDIT_ENDPOINT,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(  # noqa: S310 — scheme validated above
            req, timeout=_AUDIT_TIMEOUT_SECONDS
        ) as resp:
            resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.debug("audit POST failed: %s", exc)


def log_tool_call(tool_name: str, user_id: str, arg_keys: list[str]) -> None:
    """Log a tool invocation for audit purposes. Never logs full content."""
    logger.info("TOOL=%s USER=%s ARGS=%s", tool_name, user_id, arg_keys)

    if _AUDIT_ENDPOINT:
        payload = {
            "server": _AUDIT_SERVER_NAME,
            "tool": tool_name,
            "user": user_id,
            "args": list(arg_keys),
        }
        threading.Thread(
            target=_post_audit_event,
            args=(payload,),
            daemon=True,
        ).start()


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
