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


def _decode_part(part) -> str:
    """Decode a MIME part's payload to a string, honoring its charset."""
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


class TestBuildMimeMessage:
    """Tests for the MIME builder used by create_draft."""

    def test_plain_is_single_part(self):
        msg = GmailClient._build_mime_message("Hello world", "plain")
        assert msg.get_content_type() == "text/plain"
        assert "Hello world" in _decode_part(msg)

    def test_markdown_produces_multipart_alternative(self):
        msg = GmailClient._build_mime_message("# Hi\n\nThis is **bold**.", "markdown")
        assert msg.get_content_type() == "multipart/alternative"
        parts = msg.get_payload()
        assert len(parts) == 2
        assert parts[0].get_content_type() == "text/plain"
        assert parts[1].get_content_type() == "text/html"
        # Plain part should retain the markdown source
        assert "# Hi" in _decode_part(parts[0])
        # HTML part should have rendered tags
        html = _decode_part(parts[1])
        assert "<h1>" in html or "<h1 " in html
        assert "<strong>bold</strong>" in html

    def test_html_produces_multipart_with_plain_fallback(self):
        msg = GmailClient._build_mime_message(
            "<h1>Title</h1><p>Hello <b>world</b></p>", "html"
        )
        assert msg.get_content_type() == "multipart/alternative"
        parts = msg.get_payload()
        assert parts[0].get_content_type() == "text/plain"
        assert parts[1].get_content_type() == "text/html"
        plain = _decode_part(parts[0])
        assert "<h1>" not in plain
        assert "Title" in plain
        assert "Hello world" in plain

    def test_invalid_format_rejected(self):
        with pytest.raises(ValueError, match="Invalid body_format"):
            GmailClient._build_mime_message("body", "rtf")

    def test_markdown_links_rendered(self):
        msg = GmailClient._build_mime_message(
            "See [the docs](https://example.com).", "markdown"
        )
        html = _decode_part(msg.get_payload()[1])
        assert '<a href="https://example.com">the docs</a>' in html

    def test_markdown_lists_rendered(self):
        msg = GmailClient._build_mime_message("- one\n- two\n- three", "markdown")
        html = _decode_part(msg.get_payload()[1])
        assert "<ul>" in html
        assert "<li>one</li>" in html

    def test_markdown_nl2br_keeps_single_newlines(self):
        """Gmail users expect single newlines to become <br>, not be collapsed."""
        msg = GmailClient._build_mime_message("Line one\nLine two", "markdown")
        html = _decode_part(msg.get_payload()[1])
        assert "<br" in html

    def test_html_script_tags_stripped_from_plain_fallback(self):
        msg = GmailClient._build_mime_message(
            "<p>Safe</p><script>alert('x')</script>", "html"
        )
        plain = _decode_part(msg.get_payload()[0])
        assert "alert" not in plain
        assert "Safe" in plain

    def test_plain_utf8_supported(self):
        msg = GmailClient._build_mime_message("Café naïve — résumé", "plain")
        assert msg.get_content_charset() == "utf-8"
        assert "Café naïve — résumé" in _decode_part(msg)


class TestHtmlToPlain:
    def test_strips_tags(self):
        assert "<" not in GmailClient._html_to_plain("<p>Hello</p>")

    def test_br_becomes_newline(self):
        result = GmailClient._html_to_plain("one<br>two<br/>three")
        assert result.count("\n") == 2

    def test_list_items_get_dash_prefix(self):
        result = GmailClient._html_to_plain("<ul><li>a</li><li>b</li></ul>")
        assert "- a" in result
        assert "- b" in result

    def test_entities_decoded(self):
        assert "&" in GmailClient._html_to_plain("a &amp; b")
        assert "<" in GmailClient._html_to_plain("a &lt; b")

    def test_script_and_style_removed(self):
        result = GmailClient._html_to_plain(
            "<style>body{}</style><p>Hello</p><script>x</script>"
        )
        assert "Hello" in result
        assert "body" not in result
        assert "x" not in result
