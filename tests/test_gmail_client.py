"""Tests for GmailClient internal helpers (no API calls)."""

import pytest

from gmail_mcp.gmail_client import GmailClient


class TestSanitizeHeader:
    def test_clean_header_passes(self):
        assert GmailClient._sanitize_header("Hello World", "subject") == "Hello World"

    def test_newline_rejected(self):
        with pytest.raises(ValueError, match="newlines"):
            GmailClient._sanitize_header("Hello\nBcc: attacker@evil.com", "subject")

    def test_carriage_return_rejected(self):
        with pytest.raises(ValueError, match="newlines"):
            GmailClient._sanitize_header("Hello\r\nBcc: attacker@evil.com", "to")

    def test_empty_string_passes(self):
        assert GmailClient._sanitize_header("", "subject") == ""
