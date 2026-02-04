"""Tests for redact.secrets module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from redact.secrets import expand_env_vars, get_redact_vars, load_env


class TestLoadEnv:
    """Tests for load_env function."""

    def test_load_env_with_valid_path(self, tmp_path: Path) -> None:
        """Should return True when loading existing .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_VAR=test_value\n")

        with patch.dict(os.environ, {}, clear=False):
            result = load_env(env_file)

            assert result is True
            assert os.environ.get("TEST_VAR") == "test_value"

        # Verify cleanup - var should not persist
        assert "TEST_VAR" not in os.environ

    def test_load_env_with_nonexistent_path(self, tmp_path: Path) -> None:
        """Should return False when .env file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.env"

        result = load_env(nonexistent)

        assert result is False

    def test_load_env_with_string_path(self, tmp_path: Path) -> None:
        """Should accept string path as well as Path object."""
        env_file = tmp_path / ".env"
        env_file.write_text("STRING_PATH_VAR=value\n")

        with patch.dict(os.environ, {}, clear=False):
            result = load_env(str(env_file))

            assert result is True
            assert os.environ.get("STRING_PATH_VAR") == "value"

        # Verify cleanup
        assert "STRING_PATH_VAR" not in os.environ


class TestExpandEnvVars:
    """Tests for expand_env_vars function."""

    def test_expand_single_var(self) -> None:
        """Should expand a single ${VAR} pattern."""
        with patch.dict(os.environ, {"MY_VAR": "hello"}):
            result = expand_env_vars("Value: ${MY_VAR}")

        assert result == "Value: hello"

    def test_expand_multiple_vars(self) -> None:
        """Should expand multiple ${VAR} patterns."""
        with patch.dict(os.environ, {"FIRST": "one", "SECOND": "two"}):
            result = expand_env_vars("${FIRST} and ${SECOND}")

        assert result == "one and two"

    def test_missing_var_left_as_is(self) -> None:
        """Should leave missing variables as-is."""
        with patch.dict(os.environ, {}, clear=True):
            # Ensure the var doesn't exist
            os.environ.pop("NONEXISTENT_VAR", None)
            result = expand_env_vars("Value: ${NONEXISTENT_VAR}")

        assert result == "Value: ${NONEXISTENT_VAR}"

    def test_no_vars_returns_original(self) -> None:
        """Should return original string when no vars present."""
        result = expand_env_vars("No variables here")

        assert result == "No variables here"

    def test_empty_string(self) -> None:
        """Should handle empty string."""
        result = expand_env_vars("")

        assert result == ""

    def test_adjacent_vars(self) -> None:
        """Should handle adjacent variable patterns."""
        with patch.dict(os.environ, {"A": "1", "B": "2"}):
            result = expand_env_vars("${A}${B}")

        assert result == "12"

    def test_nested_braces_not_supported(self) -> None:
        """Should not expand nested or malformed patterns."""
        with patch.dict(os.environ, {"VAR": "value"}):
            # Nested braces - inner part won't match
            result = expand_env_vars("${${VAR}}")

        # The outer ${...} contains ${VAR} which isn't a valid var name
        assert "${" in result


class TestGetRedactVars:
    """Tests for get_redact_vars function."""

    def test_returns_redact_prefixed_vars(self) -> None:
        """Should return only REDACT_ prefixed variables."""
        env = {
            "REDACT_FULL_NAME": "John Smith",
            "REDACT_ADDRESS": "123 Main St",
            "OTHER_VAR": "ignored",
        }
        with patch.dict(os.environ, env, clear=True):
            result = get_redact_vars()

        assert result == {
            "FULL_NAME": "John Smith",
            "ADDRESS": "123 Main St",
        }

    def test_strips_prefix(self) -> None:
        """Should strip REDACT_ prefix from keys."""
        with patch.dict(os.environ, {"REDACT_TEST": "value"}, clear=True):
            result = get_redact_vars()

        assert "TEST" in result
        assert "REDACT_TEST" not in result

    def test_empty_when_no_redact_vars(self) -> None:
        """Should return empty dict when no REDACT_ vars exist."""
        with patch.dict(os.environ, {"OTHER": "value"}, clear=True):
            result = get_redact_vars()

        assert result == {}

    def test_preserves_values(self) -> None:
        """Should preserve variable values exactly."""
        with patch.dict(os.environ, {"REDACT_SPECIAL": "has spaces & symbols!"}, clear=True):
            result = get_redact_vars()

        assert result["SPECIAL"] == "has spaces & symbols!"
