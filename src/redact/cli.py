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


def find_pdf_files(directory: Path) -> list[Path]:
    """Find all PDF files in directory (non-recursive).

    Args:
        directory: Directory to search.

    Returns:
        Sorted list of PDF file paths.
    """
    # Match both .pdf and .PDF extensions
    pdfs = list(directory.glob("*.pdf")) + list(directory.glob("*.PDF"))
    # Remove duplicates on case-insensitive filesystems, keeping first occurrence
    seen: dict[Path, Path] = {}
    for p in pdfs:
        resolved = p.resolve()
        if resolved not in seen:
            seen[resolved] = p
    return sorted(seen.values(), key=lambda p: p.name.lower())


def get_batch_output_dir(
    input_dir: Path, custom_output_dir: Path | str | None = None
) -> Path:
    """Get output directory for batch processing.

    Args:
        input_dir: Input directory containing PDFs.
        custom_output_dir: Optional custom output directory.

    Returns:
        Output directory path.
    """
    if custom_output_dir:
        return Path(custom_output_dir)
    return input_dir / "redacted"


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


def _process_single_file(
    input_path: Path,
    output_file: str | None,
    output_dir: str | None,
    compiled: list,
    no_metadata: bool,
    strip_images: bool,
    verbose: bool,
    quiet: bool,
) -> None:
    """Process a single PDF file."""
    # Determine output path
    if output_dir:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"{input_path.stem}_redacted.pdf"
    elif output_file:
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


def _process_batch(
    input_dir: Path,
    output_dir: str | None,
    compiled: list,
    no_metadata: bool,
    strip_images: bool,
    verbose: bool,
    quiet: bool,
) -> None:
    """Process all PDFs in a directory."""
    pdf_files = find_pdf_files(input_dir)

    if not pdf_files:
        raise click.UsageError(f"No PDF files found in {input_dir}")

    batch_output = get_batch_output_dir(input_dir, output_dir)
    batch_output.mkdir(parents=True, exist_ok=True)

    if verbose:
        click.echo(f"Batch mode: {len(pdf_files)} PDF(s) in {input_dir}")
        click.echo(f"Output directory: {batch_output}")
        click.echo(f"Patterns: {[name for name, _ in compiled]}")
        click.echo(f"Strip metadata: {not no_metadata}")
        click.echo(f"Strip images: {strip_images}")
        click.echo("")

    # Aggregate results
    total_pages = 0
    total_redactions = 0
    total_images = 0
    files_processed = 0
    failures: list[tuple[Path, str]] = []

    for pdf_path in pdf_files:
        output_path = batch_output / f"{pdf_path.stem}_redacted.pdf"

        if verbose:
            click.echo(f"Processing: {pdf_path.name}")

        try:
            result = redact_document(
                input_path=pdf_path,
                output_path=output_path,
                patterns=compiled,
                strip_meta=not no_metadata,
                strip_images=strip_images,
            )
            total_pages += result.pages_processed
            total_redactions += result.total_redactions
            total_images += result.images_removed
            files_processed += 1

            if verbose:
                msg = f"  → {result.total_redactions} redaction(s)"
                if result.images_removed > 0:
                    msg += f", {result.images_removed} image(s) removed"
                click.echo(msg)

        except RedactionError as e:
            failures.append((pdf_path, str(e)))
            if not quiet:
                click.echo(f"  → Failed: {e}", err=True)

    # Summary
    if not quiet:
        click.echo("")
        click.echo(
            f"Processed {files_processed}/{len(pdf_files)} file(s): "
            f"{total_redactions} redaction(s) across {total_pages} page(s)"
        )
        if total_images > 0:
            click.echo(f"Removed {total_images} image(s) total")
        click.echo(f"Output saved to: {batch_output}")

        if failures:
            click.echo("")
            click.echo(f"Failed files ({len(failures)}):")
            for path, error in failures:
                click.echo(f"  {path.name}: {error}")


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
    "-o",
    "--output-dir",
    "output_dir",
    type=click.Path(),
    help="Output directory for batch processing. Default: <input>/redacted/",
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
    output_dir: str | None,
    no_metadata: bool,
    strip_images: bool,
    verbose: bool,
    quiet: bool,
    list_patterns_flag: bool,
) -> None:
    """Redact PII from PDF files.

    INPUT_FILE is the PDF file or directory to redact. For directories, all
    PDFs are processed and output to <dir>/redacted/ by default.

    OUTPUT_FILE is optional for single files; defaults to INPUT_FILE with
    _redacted suffix. Use --output-dir for batch processing.
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

    input_path = Path(input_file)

    # Check if batch mode (directory input)
    if input_path.is_dir():
        _process_batch(
            input_dir=input_path,
            output_dir=output_dir,
            compiled=compiled,
            no_metadata=no_metadata,
            strip_images=strip_images,
            verbose=verbose,
            quiet=quiet,
        )
    else:
        _process_single_file(
            input_path=input_path,
            output_file=output_file,
            output_dir=output_dir,
            compiled=compiled,
            no_metadata=no_metadata,
            strip_images=strip_images,
            verbose=verbose,
            quiet=quiet,
        )


if __name__ == "__main__":
    main()
