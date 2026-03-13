"""Tests for authentication path validation and env var resolution."""

import pytest

from gmail_mcp.auth import _env_key, _validate_email_for_path


class TestValidateEmailForPath:
    def test_valid_email(self):
        # Should not raise
        _validate_email_for_path("user@example.com")

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError, match="Invalid email"):
            _validate_email_for_path("../../../etc/passwd")

    def test_rejects_forward_slash(self):
        with pytest.raises(ValueError, match="Invalid email"):
            _validate_email_for_path("user/../../root")

    def test_rejects_backslash(self):
        with pytest.raises(ValueError, match="Invalid email"):
            _validate_email_for_path("user\\..\\root")

    def test_rejects_null_byte(self):
        with pytest.raises(ValueError, match="Invalid email"):
            _validate_email_for_path("user@example.com\0.evil")

    def test_rejects_double_dot(self):
        with pytest.raises(ValueError, match="Invalid email"):
            _validate_email_for_path("user@..com")


class TestEnvKey:
    def test_basic_email(self):
        assert _env_key("user@example.com") == "USER_EXAMPLE_COM"

    def test_email_with_plus(self):
        assert _env_key("user+tag@example.com") == "USER_TAG_EXAMPLE_COM"

    def test_email_with_dots(self):
        assert _env_key("first.last@company.co.uk") == "FIRST_LAST_COMPANY_CO_UK"
