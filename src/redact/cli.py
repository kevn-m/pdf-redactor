"""CLI entry point for PDF redaction tool."""

import logging
import sys
from pathlib import Path

import click

from redact import __version__
from redact.patterns import (
    BUILTIN_PATTERNS,
    Pattern,
    compile_patterns,
    get_builtin_patterns,
    load_yaml_patterns,
)
from redact.redactor import RedactionError, redact_document
from redact.secrets import get_redact_vars, load_env

logger = logging.getLogger(__name__)


def get_default_output(input_path: str | Path) -> Path:
    """Generate default output path by adding _redacted suffix.

    Args:
        input_path: Original input file path.

    Returns:
        Path with _redacted added before extension.
    """
    path = Path(input_path)
    return path.with_stem(f"{path.stem}_redacted")


def list_patterns() -> str:
    """Return formatted string of available built-in patterns.

    Returns:
        Multi-line string listing all patterns with descriptions.
    """
    lines = ["Available patterns:", ""]
    for name, pattern in BUILTIN_PATTERNS.items():
        lines.append(f"  {name:<16} {pattern.description}")
    return "\n".join(lines)


def setup_logging(verbose: bool, quiet: bool) -> None:
    """Configure logging based on verbosity flags.

    Args:
        verbose: Enable debug-level logging.
        quiet: Suppress all non-error output.
    """
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        stream=sys.stderr,
    )


@click.command()
@click.argument("input_file", type=click.Path(exists=True), required=False)
@click.argument("output_file", type=click.Path(), required=False)
@click.option(
    "-p",
    "--pattern",
    "patterns",
    multiple=True,
    help="Built-in pattern to use (repeatable).",
)
@click.option(
    "-c",
    "--config",
    "config_path",
    type=click.Path(),
    help="YAML config file with pattern definitions.",
)
@click.option(
    "-a",
    "--all-patterns",
    is_flag=True,
    help="Use all built-in patterns.",
)
@click.option(
    "-M",
    "--no-metadata",
    is_flag=True,
    help="Skip metadata stripping.",
)
@click.option(
    "-I",
    "--strip-images",
    is_flag=True,
    help="Remove all images (barcodes, logos, etc.).",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Verbose output.",
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help="Errors only.",
)
@click.option(
    "-l",
    "--list-patterns",
    "list_patterns_flag",
    is_flag=True,
    help="List available patterns and exit.",
)
@click.version_option(version=__version__)
def main(
    input_file: str | None,
    output_file: str | None,
    patterns: tuple[str, ...],
    config_path: str | None,
    all_patterns: bool,
    no_metadata: bool,
    strip_images: bool,
    verbose: bool,
    quiet: bool,
    list_patterns_flag: bool,
) -> None:
    """Redact PII from PDF files.

    INPUT_FILE is the PDF to redact. OUTPUT_FILE is optional; defaults to
    INPUT_FILE with _redacted suffix.
    """
    # Handle --list-patterns
    if list_patterns_flag:
        click.echo(list_patterns())
        return

    # Require input file for redaction
    if not input_file:
        raise click.UsageError("Missing argument 'INPUT_FILE'.")

    # Validate mutually exclusive options
    if verbose and quiet:
        raise click.UsageError("Cannot use --verbose and --quiet together.")

    setup_logging(verbose, quiet)

    # Load .env file
    load_env()

    # Build pattern list
    active_patterns: list[Pattern] = []

    # Add all built-in patterns if --all-patterns flag is set
    if all_patterns:
        active_patterns.extend(get_builtin_patterns())

    # Validate and add explicit patterns (in addition to --all-patterns)
    if patterns:
        invalid = [p for p in patterns if p not in BUILTIN_PATTERNS]
        if invalid:
            raise click.UsageError(f"Unknown pattern(s): {', '.join(invalid)}")
        # Only add if not already included via --all-patterns
        if not all_patterns:
            active_patterns.extend(get_builtin_patterns(list(patterns)))

    # Load from config file
    if config_path:
        config_file = Path(config_path)
        if not config_file.exists():
            raise click.UsageError(f"Config file not found: {config_path}")
        try:
            yaml_patterns = load_yaml_patterns(config_file)
            active_patterns.extend(yaml_patterns)
        except Exception as e:
            raise click.UsageError(f"Failed to load config: {e}") from e

    # Add REDACT_* env vars as literal patterns
    redact_vars = get_redact_vars()
    for name, value in redact_vars.items():
        if value:  # Only add non-empty values
            active_patterns.append(
                Pattern(
                    name=f"env_{name}",
                    regex=value,
                    description=f"From REDACT_{name} env var",
                )
            )

    # Default to all built-in patterns if none specified via -p, -c, or -a
    # (env vars alone don't count - user must explicitly choose patterns)
    if not all_patterns and not patterns and not config_path:
        active_patterns = get_builtin_patterns() + active_patterns

    # Compile patterns
    try:
        compiled = compile_patterns(active_patterns)
    except Exception as e:
        raise click.UsageError(f"Invalid pattern regex: {e}") from e

    if not compiled:
        raise click.UsageError("No patterns to apply.")

    # Determine output path
    input_path = Path(input_file)
    if output_file:
        output_path = Path(output_file)
    else:
        output_path = get_default_output(input_path)

    # Create parent directories if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Prevent overwriting input file
    if output_path.resolve() == input_path.resolve():
        raise click.UsageError(
            "Output path cannot be the same as input path. "
            "Use a different name or omit OUTPUT_FILE for automatic naming."
        )

    # Log what we're doing
    if verbose:
        click.echo(f"Input: {input_path}")
        click.echo(f"Output: {output_path}")
        click.echo(f"Patterns: {[name for name, _ in compiled]}")
        click.echo(f"Strip metadata: {not no_metadata}")
        click.echo(f"Strip images: {strip_images}")
        click.echo("")

    # Perform redaction
    try:
        result = redact_document(
            input_path=input_path,
            output_path=output_path,
            patterns=compiled,
            strip_meta=not no_metadata,
            strip_images=strip_images,
        )
    except RedactionError as e:
        raise click.ClickException(str(e)) from e

    # Output results
    if not quiet:
        msg = f"Redacted {result.total_redactions} item(s) across {result.pages_processed} page(s)"
        if result.images_removed > 0:
            msg += f", removed {result.images_removed} image(s)"
        click.echo(msg)
        click.echo(f"Output saved to: {output_path}")

    if verbose and result.redactions_by_pattern:
        click.echo("")
        click.echo("Redactions by pattern:")
        for pattern_name, count in result.redactions_by_pattern.items():
            click.echo(f"  {pattern_name}: {count}")


if __name__ == "__main__":
    main()
