"""Pattern definitions and loading for PDF redaction."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from redact.secrets import expand_env_vars

if TYPE_CHECKING:
    from re import Pattern as CompiledPattern


@dataclass
class Pattern:
    """A redaction pattern with name, regex, and metadata."""

    name: str
    regex: str
    description: str = ""
    enabled: bool = True


# Built-in patterns for Australian PII
BUILTIN_PATTERNS: dict[str, Pattern] = {
    "account_number": Pattern(
        name="account_number",
        regex=r"\b\d{6,12}\b",
        description="Bank account numbers (6-12 digits)",
    ),
    "card_number": Pattern(
        name="card_number",
        regex=r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        description="Card numbers (16 digits with optional separators)",
    ),
    "bsb": Pattern(
        name="bsb",
        regex=r"\b\d{3}[-\s]?\d{3}\b",
        description="BSB numbers (XXX-XXX)",
    ),
    "tfn": Pattern(
        name="tfn",
        regex=r"\b\d{3}[-\s]?\d{3}[-\s]?\d{3}\b",
        description="Tax File Numbers (XXX XXX XXX or XXXXXXXXX)",
    ),
    "email": Pattern(
        name="email",
        regex=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        description="Email addresses",
    ),
    "phone_au": Pattern(
        name="phone_au",
        regex=r"(?<![A-Za-z0-9])(?:\+61[ -]?|0)[2-478](?:[ -]?\d){8}\b",
        description="Australian phone numbers",
    ),
}


def get_builtin_patterns(names: list[str] | None = None) -> list[Pattern]:
    """Get built-in patterns, optionally filtered by name.

    Args:
        names: List of pattern names to include. If None or empty, returns all.

    Returns:
        List of Pattern instances.
    """
    if not names:
        return list(BUILTIN_PATTERNS.values())

    return [
        BUILTIN_PATTERNS[name]
        for name in names
        if name in BUILTIN_PATTERNS
    ]


def load_yaml_patterns(path: str | Path) -> list[Pattern]:
    """Load patterns from a YAML configuration file.

    The YAML file should have this structure:
        patterns:
          pattern_name:
            regex: "pattern"
            description: "optional description"
            enabled: true  # optional, defaults to true

    Environment variables in ${VAR} format are expanded in regex values.

    Args:
        path: Path to YAML file.

    Returns:
        List of Pattern instances.

    Raises:
        FileNotFoundError: If the file doesn't exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Pattern file not found: {path}")

    with path.open() as f:
        data = yaml.safe_load(f)

    patterns_data = data.get("patterns", {})
    if not patterns_data:
        return []

    patterns = []
    for name, config in patterns_data.items():
        regex = expand_env_vars(config.get("regex", ""))
        patterns.append(
            Pattern(
                name=name,
                regex=regex,
                description=config.get("description", ""),
                enabled=config.get("enabled", True),
            )
        )

    return patterns


def compile_patterns(
    patterns: list[Pattern],
) -> list[tuple[str, "CompiledPattern[str]"]]:
    """Compile Pattern instances into regex objects.

    Args:
        patterns: List of Pattern instances.

    Returns:
        List of (name, compiled_regex) tuples for enabled patterns.

    Raises:
        re.error: If a pattern has invalid regex.
    """
    compiled = []
    for pattern in patterns:
        if not pattern.enabled:
            continue
        compiled.append((pattern.name, re.compile(pattern.regex)))

    return compiled
