"""Gmail API wrapper for querying messages, threads, and labels."""

import base64
import email.mime.text
import logging

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from gmail_mcp.security import sanitize_email_content

logger = logging.getLogger("gmail-mcp.client")


class GmailClient:
    """Thin wrapper around the Gmail API, enforcing security constraints."""

    def __init__(self, credentials: Credentials) -> None:
        self._service = build("gmail", "v1", credentials=credentials)

    def get_profile(self) -> dict:
        """Get the authenticated user's profile. Returns only safe fields."""
        raw = self._service.users().getProfile(userId="me").execute()
        return {
            "email": raw.get("emailAddress", ""),
            "messages_total": raw.get("messagesTotal", 0),
            "threads_total": raw.get("threadsTotal", 0),
            "history_id": raw.get("historyId", ""),
        }

    def search(self, query: str, max_results: int = 20) -> list[dict]:
        """Search emails, returning metadata only (not full body).

        Returns a list of email metadata dicts with sanitized fields.
        """
        results = (
            self._service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )

        messages = results.get("messages", [])
        if not messages:
            return []

        # Batch fetch metadata for all messages in a single round-trip
        fetched: list[dict | None] = [None] * len(messages)

        def _make_callback(index: int):  # noqa: ANN202
            def _cb(request_id, response, exception):  # noqa: ANN001, ARG001
                if exception is None:
                    fetched[index] = response

            return _cb

        batch = self._service.new_batch_http_request()
        for i, msg_stub in enumerate(messages):
            req = (
                self._service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg_stub["id"],
                    format="metadata",
                    metadataHeaders=["Subject", "From", "To", "Date"],
                )
            )
            batch.add(req, callback=_make_callback(i))
        batch.execute()

        output = []
        for msg in fetched:
            if msg is not None:
                parsed = self._parse_metadata(msg)
                output.append(sanitize_email_content(parsed))

        return output

    def get_email(self, email_id: str) -> dict:
        """Retrieve a full email by ID. Content is sanitized."""
        msg = (
            self._service.users().messages().get(userId="me", id=email_id, format="full").execute()
        )
        parsed = self._parse_full_message(msg)
        return sanitize_email_content(parsed)

    def get_thread(self, thread_id: str) -> dict:
        """Retrieve all messages in a thread. Each message is sanitized."""
        thread = (
            self._service.users().threads().get(userId="me", id=thread_id, format="full").execute()
        )
        messages = []
        for msg in thread.get("messages", []):
            parsed = self._parse_full_message(msg)
            messages.append(sanitize_email_content(parsed))

        return {"thread_id": thread_id, "messages": messages}

    def list_labels(self) -> list[dict]:
        """List all labels in the account."""
        results = self._service.users().labels().list(userId="me").execute()
        return [
            {"id": label["id"], "name": label["name"], "type": label.get("type", "")}
            for label in results.get("labels", [])
        ]

    @staticmethod
    def _sanitize_header(value: str, field_name: str) -> str:
        """Reject header values containing newlines to prevent header injection."""
        if "\n" in value or "\r" in value:
            raise ValueError(f"Invalid characters in {field_name}: newlines are not allowed")
        return value

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        cc: list[str] | None = None,
        reply_to_id: str | None = None,
    ) -> dict:
        """Create a draft email. Does NOT send."""
        message = email.mime.text.MIMEText(body)
        message["to"] = self._sanitize_header(to, "to")
        message["subject"] = self._sanitize_header(subject, "subject")
        if cc:
            for addr in cc:
                self._sanitize_header(addr, "cc")
            message["cc"] = ", ".join(cc)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft_body: dict = {"message": {"raw": raw}}

        if reply_to_id:
            # Fetch the original message to get threadId and headers for proper threading
            original = (
                self._service.users()
                .messages()
                .get(
                    userId="me",
                    id=reply_to_id,
                    format="metadata",
                    metadataHeaders=["Message-ID", "Subject"],
                )
                .execute()
            )
            draft_body["message"]["threadId"] = original.get("threadId")

            # Set In-Reply-To and References headers for proper threading
            for header in original.get("payload", {}).get("headers", []):
                if header["name"].lower() == "message-id":
                    message["In-Reply-To"] = header["value"]
                    message["References"] = header["value"]
                    break

            # Re-encode after adding headers
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            draft_body["message"]["raw"] = raw

        result = self._service.users().drafts().create(userId="me", body=draft_body).execute()
        return {"draft_id": result["id"], "message": "Draft created successfully"}

    def create_label(self, name: str) -> dict:
        """Create a new label. Requires gmail.labels scope."""
        body = {"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
        result = self._service.users().labels().create(userId="me", body=body).execute()
        return {"id": result["id"], "name": result["name"]}

    def update_label(self, label_id: str, new_name: str) -> dict:
        """Rename a label. Requires gmail.labels scope."""
        body = {"name": new_name}
        result = (
            self._service.users().labels().update(userId="me", id=label_id, body=body).execute()
        )
        return {"id": result["id"], "name": result["name"]}

    def delete_label(self, label_id: str) -> dict:
        """Delete a label. Requires gmail.labels scope."""
        self._service.users().labels().delete(userId="me", id=label_id).execute()
        return {"deleted": True, "label_id": label_id}

    def modify_labels(
        self,
        email_id: str,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> dict:
        """Add/remove labels on a message. Requires gmail.modify scope."""
        body: dict = {
            "addLabelIds": add_labels or [],
            "removeLabelIds": remove_labels or [],
        }
        result = (
            self._service.users()
            .messages()
            .modify(userId="me", id=email_id, body=body)
            .execute()
        )
        return {"id": result["id"], "label_ids": result.get("labelIds", [])}

    def get_attachment(self, email_id: str, attachment_id: str) -> dict:
        """Download an attachment and return it as base64. Never writes to disk."""
        result = (
            self._service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=email_id, id=attachment_id)
            .execute()
        )
        return {
            "data": result.get("data", ""),
            "size": result.get("size", 0),
        }

    # -- Internal helpers --

    def _parse_metadata(self, msg: dict) -> dict:
        """Extract metadata fields from a Gmail API message response."""
        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
        return {
            "id": msg["id"],
            "thread_id": msg.get("threadId", ""),
            "subject": headers.get("subject", "(no subject)"),
            "from": headers.get("from", "(unknown)"),
            "to": headers.get("to", ""),
            "date": headers.get("date", ""),
            "snippet": msg.get("snippet", ""),
            "label_ids": msg.get("labelIds", []),
        }

    def _parse_full_message(self, msg: dict) -> dict:
        """Extract full content from a Gmail API message response."""
        parsed = self._parse_metadata(msg)
        parsed["body"] = self._extract_body(msg.get("payload", {}))

        # Include attachment metadata (not content) for awareness
        attachments = []
        self._collect_attachments(msg.get("payload", {}), attachments)
        if attachments:
            parsed["attachments"] = attachments

        return parsed

    def _extract_body(self, payload: dict) -> str:
        """Recursively extract the text body from a message payload.

        Prefers text/plain over text/html. For nested multipart structures
        (e.g. multipart/mixed > multipart/alternative > text/plain), recurses
        fully and uses the deepest text/plain found.
        """
        # Simple single-part message
        if payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode(errors="replace")

        # Multipart — prefer text/plain, fall back to text/html
        parts = payload.get("parts", [])
        text_body = ""
        html_body = ""

        for part in parts:
            mime_type = part.get("mimeType", "")
            if mime_type == "text/plain" and part.get("body", {}).get("data"):
                text_body = base64.urlsafe_b64decode(part["body"]["data"]).decode(errors="replace")
            elif mime_type == "text/html" and part.get("body", {}).get("data"):
                html_body = base64.urlsafe_b64decode(part["body"]["data"]).decode(errors="replace")
            elif mime_type.startswith("multipart/"):
                nested = self._extract_body(part)
                if nested and nested != "(no body content)":
                    # Nested result wins over what we have at this level,
                    # since the inner multipart/alternative is the real content
                    if not text_body:
                        text_body = nested
                    if not html_body and nested.startswith("<"):
                        html_body = nested

        return text_body or html_body or "(no body content)"

    def _collect_attachments(self, payload: dict, attachments: list[dict]) -> None:
        """Collect attachment metadata (filename, size) without downloading content."""
        filename = payload.get("filename")
        attachment_id = payload.get("body", {}).get("attachmentId")
        if filename and attachment_id:
            attachments.append(
                {
                    "filename": filename,
                    "mime_type": payload.get("mimeType", ""),
                    "size": payload.get("body", {}).get("size", 0),
                    "attachment_id": attachment_id,
                }
            )

        for part in payload.get("parts", []):
            self._collect_attachments(part, attachments)
