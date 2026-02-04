"""Environment variable loading and expansion for redaction patterns."""

import os
import re
from pathlib import Path

from dotenv import load_dotenv as dotenv_load


def load_env(path: str | Path | None = None) -> bool:
    """Load .env file using python-dotenv.

    Args:
        path: Path to .env file. If None, uses default .env in current directory.

    Returns:
        True if file was loaded, False otherwise.
    """
    if path is not None:
        env_path = Path(path)
        if not env_path.exists():
            return False
        return dotenv_load(env_path)

    return dotenv_load()


def expand_env_vars(text: str) -> str:
    """Expand ${VAR} syntax in strings using os.environ.

    Args:
        text: String potentially containing ${VAR} patterns.

    Returns:
        String with environment variables expanded. Missing vars are left as-is.
    """
    pattern = r"\$\{([^}]+)\}"

    def replace_var(match: re.Match[str]) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))

    return re.sub(pattern, replace_var, text)


def get_redact_vars() -> dict[str, str]:
    """Return dict of all REDACT_* environment variables with prefix stripped.

    Returns:
        Dict mapping variable names (without REDACT_ prefix) to their values.
        Example: REDACT_FULL_NAME=John → {"FULL_NAME": "John"}
    """
    prefix = "REDACT_"
    return {
        key[len(prefix) :]: value
        for key, value in os.environ.items()
        if key.startswith(prefix)
    }
