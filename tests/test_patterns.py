"""Tests for redact.patterns module."""

import re
from pathlib import Path
from unittest.mock import patch

import pytest

from redact.patterns import (
    BUILTIN_PATTERNS,
    Pattern,
    compile_patterns,
    get_builtin_patterns,
    load_yaml_patterns,
)


class TestPatternDataclass:
    """Tests for Pattern dataclass."""

    def test_create_pattern_with_required_fields(self) -> None:
        """Should create pattern with name and regex."""
        pattern = Pattern(name="test", regex=r"\d+")

        assert pattern.name == "test"
        assert pattern.regex == r"\d+"

    def test_default_description_is_empty(self) -> None:
        """Should have empty description by default."""
        pattern = Pattern(name="test", regex=r"\d+")

        assert pattern.description == ""

    def test_default_enabled_is_true(self) -> None:
        """Should be enabled by default."""
        pattern = Pattern(name="test", regex=r"\d+")

        assert pattern.enabled is True

    def test_create_pattern_with_all_fields(self) -> None:
        """Should accept all fields."""
        pattern = Pattern(
            name="test",
            regex=r"\d+",
            description="Matches digits",
            enabled=False,
        )

        assert pattern.name == "test"
        assert pattern.regex == r"\d+"
        assert pattern.description == "Matches digits"
        assert pattern.enabled is False


class TestBuiltinPatterns:
    """Tests for built-in pattern definitions."""

    def test_builtin_patterns_exist(self) -> None:
        """Should have built-in patterns defined."""
        assert len(BUILTIN_PATTERNS) > 0

    def test_account_number_pattern_exists(self) -> None:
        """Should have account_number pattern."""
        assert "account_number" in BUILTIN_PATTERNS

    def test_card_number_pattern_exists(self) -> None:
        """Should have card_number pattern."""
        assert "card_number" in BUILTIN_PATTERNS

    def test_bsb_pattern_exists(self) -> None:
        """Should have bsb pattern."""
        assert "bsb" in BUILTIN_PATTERNS

    def test_tfn_pattern_exists(self) -> None:
        """Should have tfn pattern."""
        assert "tfn" in BUILTIN_PATTERNS

    def test_email_pattern_exists(self) -> None:
        """Should have email pattern."""
        assert "email" in BUILTIN_PATTERNS

    def test_phone_au_pattern_exists(self) -> None:
        """Should have phone_au pattern."""
        assert "phone_au" in BUILTIN_PATTERNS

    def test_all_builtins_are_pattern_instances(self) -> None:
        """All built-in patterns should be Pattern instances."""
        for name, pattern in BUILTIN_PATTERNS.items():
            assert isinstance(pattern, Pattern), f"{name} is not a Pattern"

    def test_all_builtins_have_valid_regex(self) -> None:
        """All built-in patterns should have compilable regex."""
        for name, pattern in BUILTIN_PATTERNS.items():
            try:
                re.compile(pattern.regex)
            except re.error as e:
                pytest.fail(f"Pattern {name} has invalid regex: {e}")


class TestBuiltinPatternMatching:
    """Tests that built-in patterns match expected values."""

    def test_account_number_matches_6_digits(self) -> None:
        """Should match 6-digit account numbers."""
        regex = re.compile(BUILTIN_PATTERNS["account_number"].regex)
        assert regex.search("123456")

    def test_account_number_matches_12_digits(self) -> None:
        """Should match 12-digit account numbers."""
        regex = re.compile(BUILTIN_PATTERNS["account_number"].regex)
        assert regex.search("123456789012")

    def test_card_number_matches_with_spaces(self) -> None:
        """Should match card numbers with spaces."""
        regex = re.compile(BUILTIN_PATTERNS["card_number"].regex)
        assert regex.search("1234 5678 9012 3456")

    def test_card_number_matches_with_dashes(self) -> None:
        """Should match card numbers with dashes."""
        regex = re.compile(BUILTIN_PATTERNS["card_number"].regex)
        assert regex.search("1234-5678-9012-3456")

    def test_card_number_matches_no_separators(self) -> None:
        """Should match card numbers without separators."""
        regex = re.compile(BUILTIN_PATTERNS["card_number"].regex)
        assert regex.search("1234567890123456")

    def test_bsb_matches_with_dash(self) -> None:
        """Should match BSB with dash."""
        regex = re.compile(BUILTIN_PATTERNS["bsb"].regex)
        assert regex.search("123-456")

    def test_bsb_matches_with_space(self) -> None:
        """Should match BSB with space."""
        regex = re.compile(BUILTIN_PATTERNS["bsb"].regex)
        assert regex.search("123 456")

    def test_bsb_matches_no_separator(self) -> None:
        """Should match BSB without separator."""
        regex = re.compile(BUILTIN_PATTERNS["bsb"].regex)
        assert regex.search("123456")

    def test_tfn_matches_with_spaces(self) -> None:
        """Should match TFN with spaces."""
        regex = re.compile(BUILTIN_PATTERNS["tfn"].regex)
        assert regex.search("123 456 789")

    def test_tfn_matches_with_dashes(self) -> None:
        """Should match TFN with dashes."""
        regex = re.compile(BUILTIN_PATTERNS["tfn"].regex)
        assert regex.search("123-456-789")

    def test_tfn_matches_no_separators(self) -> None:
        """Should match TFN without separators."""
        regex = re.compile(BUILTIN_PATTERNS["tfn"].regex)
        assert regex.search("123456789")

    def test_email_matches_standard_email(self) -> None:
        """Should match standard email addresses."""
        regex = re.compile(BUILTIN_PATTERNS["email"].regex)
        assert regex.search("test@example.com")

    def test_email_matches_with_plus(self) -> None:
        """Should match email with plus addressing."""
        regex = re.compile(BUILTIN_PATTERNS["email"].regex)
        assert regex.search("test+filter@example.com")

    def test_phone_au_matches_mobile(self) -> None:
        """Should match Australian mobile numbers."""
        regex = re.compile(BUILTIN_PATTERNS["phone_au"].regex)
        assert regex.search("0412 345 678")

    def test_phone_au_matches_landline(self) -> None:
        """Should match Australian landline numbers."""
        regex = re.compile(BUILTIN_PATTERNS["phone_au"].regex)
        assert regex.search("02 1234 5678")

    def test_phone_au_matches_international(self) -> None:
        """Should match international format."""
        regex = re.compile(BUILTIN_PATTERNS["phone_au"].regex)
        assert regex.search("+61 412 345 678")


class TestGetBuiltinPatterns:
    """Tests for get_builtin_patterns function."""

    def test_returns_all_patterns_when_no_filter(self) -> None:
        """Should return all built-in patterns when names is None."""
        patterns = get_builtin_patterns()

        assert len(patterns) == len(BUILTIN_PATTERNS)

    def test_returns_all_patterns_for_empty_list(self) -> None:
        """Should return all patterns when names is empty list."""
        patterns = get_builtin_patterns(names=[])

        assert len(patterns) == len(BUILTIN_PATTERNS)

    def test_filters_by_single_name(self) -> None:
        """Should return only requested pattern."""
        patterns = get_builtin_patterns(names=["email"])

        assert len(patterns) == 1
        assert patterns[0].name == "email"

    def test_filters_by_multiple_names(self) -> None:
        """Should return multiple requested patterns."""
        patterns = get_builtin_patterns(names=["email", "bsb"])

        assert len(patterns) == 2
        names = {p.name for p in patterns}
        assert names == {"email", "bsb"}

    def test_ignores_unknown_names(self) -> None:
        """Should ignore names not in built-ins."""
        patterns = get_builtin_patterns(names=["email", "nonexistent"])

        assert len(patterns) == 1
        assert patterns[0].name == "email"

    def test_returns_empty_for_all_unknown_names(self) -> None:
        """Should return empty list when all names are unknown."""
        patterns = get_builtin_patterns(names=["fake1", "fake2"])

        assert patterns == []

    def test_returns_pattern_instances(self) -> None:
        """Should return Pattern instances."""
        patterns = get_builtin_patterns()

        for pattern in patterns:
            assert isinstance(pattern, Pattern)


class TestLoadYamlPatterns:
    """Tests for load_yaml_patterns function."""

    def test_load_simple_yaml(self, tmp_path: Path) -> None:
        """Should load patterns from simple YAML file."""
        yaml_content = """
patterns:
  custom_pattern:
    regex: "\\\\d{4}"
    description: "Four digits"
"""
        yaml_file = tmp_path / "patterns.yaml"
        yaml_file.write_text(yaml_content)

        patterns = load_yaml_patterns(yaml_file)

        assert len(patterns) == 1
        assert patterns[0].name == "custom_pattern"
        assert patterns[0].regex == r"\d{4}"
        assert patterns[0].description == "Four digits"

    def test_load_multiple_patterns(self, tmp_path: Path) -> None:
        """Should load multiple patterns from YAML."""
        yaml_content = """
patterns:
  pattern_one:
    regex: "one"
  pattern_two:
    regex: "two"
"""
        yaml_file = tmp_path / "patterns.yaml"
        yaml_file.write_text(yaml_content)

        patterns = load_yaml_patterns(yaml_file)

        assert len(patterns) == 2

    def test_expand_env_vars_in_regex(self, tmp_path: Path) -> None:
        """Should expand ${VAR} in regex patterns."""
        yaml_content = """
patterns:
  name_pattern:
    regex: "${REDACT_FULL_NAME}"
    description: "Account holder name"
"""
        yaml_file = tmp_path / "patterns.yaml"
        yaml_file.write_text(yaml_content)

        with patch.dict("os.environ", {"REDACT_FULL_NAME": "John Smith"}):
            patterns = load_yaml_patterns(yaml_file)

        assert patterns[0].regex == "John Smith"

    def test_missing_env_var_left_as_is(self, tmp_path: Path) -> None:
        """Should leave missing env vars unexpanded."""
        yaml_content = """
patterns:
  name_pattern:
    regex: "${NONEXISTENT_VAR}"
"""
        yaml_file = tmp_path / "patterns.yaml"
        yaml_file.write_text(yaml_content)

        with patch.dict("os.environ", {}, clear=True):
            patterns = load_yaml_patterns(yaml_file)

        assert patterns[0].regex == "${NONEXISTENT_VAR}"

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Should accept string path."""
        yaml_content = """
patterns:
  test:
    regex: "test"
"""
        yaml_file = tmp_path / "patterns.yaml"
        yaml_file.write_text(yaml_content)

        patterns = load_yaml_patterns(str(yaml_file))

        assert len(patterns) == 1

    def test_pattern_disabled_by_default_is_enabled(self, tmp_path: Path) -> None:
        """Patterns should be enabled by default."""
        yaml_content = """
patterns:
  test:
    regex: "test"
"""
        yaml_file = tmp_path / "patterns.yaml"
        yaml_file.write_text(yaml_content)

        patterns = load_yaml_patterns(yaml_file)

        assert patterns[0].enabled is True

    def test_pattern_can_be_disabled(self, tmp_path: Path) -> None:
        """Should respect enabled: false in YAML."""
        yaml_content = """
patterns:
  test:
    regex: "test"
    enabled: false
"""
        yaml_file = tmp_path / "patterns.yaml"
        yaml_file.write_text(yaml_content)

        patterns = load_yaml_patterns(yaml_file)

        assert patterns[0].enabled is False

    def test_raises_on_nonexistent_file(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError for missing file."""
        nonexistent = tmp_path / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError):
            load_yaml_patterns(nonexistent)

    def test_empty_patterns_returns_empty_list(self, tmp_path: Path) -> None:
        """Should return empty list when patterns section is empty."""
        yaml_content = """
patterns: {}
"""
        yaml_file = tmp_path / "patterns.yaml"
        yaml_file.write_text(yaml_content)

        patterns = load_yaml_patterns(yaml_file)

        assert patterns == []

    def test_missing_patterns_key_returns_empty_list(self, tmp_path: Path) -> None:
        """Should return empty list when patterns key is missing."""
        yaml_content = """
other_key: "some value"
"""
        yaml_file = tmp_path / "patterns.yaml"
        yaml_file.write_text(yaml_content)

        patterns = load_yaml_patterns(yaml_file)

        assert patterns == []


class TestCompilePatterns:
    """Tests for compile_patterns function."""

    def test_compiles_single_pattern(self) -> None:
        """Should compile a single pattern."""
        patterns = [Pattern(name="digits", regex=r"\d+")]

        compiled = compile_patterns(patterns)

        assert len(compiled) == 1
        name, regex = compiled[0]
        assert name == "digits"
        assert regex.search("123")

    def test_compiles_multiple_patterns(self) -> None:
        """Should compile multiple patterns."""
        patterns = [
            Pattern(name="digits", regex=r"\d+"),
            Pattern(name="words", regex=r"\w+"),
        ]

        compiled = compile_patterns(patterns)

        assert len(compiled) == 2

    def test_skips_disabled_patterns(self) -> None:
        """Should not compile disabled patterns."""
        patterns = [
            Pattern(name="enabled", regex=r"\d+", enabled=True),
            Pattern(name="disabled", regex=r"\w+", enabled=False),
        ]

        compiled = compile_patterns(patterns)

        assert len(compiled) == 1
        assert compiled[0][0] == "enabled"

    def test_returns_tuple_of_name_and_compiled_regex(self) -> None:
        """Should return tuples of (name, compiled_regex)."""
        patterns = [Pattern(name="test", regex=r"\d+")]

        compiled = compile_patterns(patterns)

        name, regex = compiled[0]
        assert isinstance(name, str)
        assert hasattr(regex, "search")  # compiled regex has search method

    def test_empty_patterns_returns_empty_list(self) -> None:
        """Should return empty list for empty input."""
        compiled = compile_patterns([])

        assert compiled == []

    def test_raises_on_invalid_regex(self) -> None:
        """Should raise on invalid regex pattern."""
        patterns = [Pattern(name="invalid", regex=r"[invalid")]

        with pytest.raises(re.error):
            compile_patterns(patterns)
