"""Core PDF redaction functionality using PyMuPDF."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pymupdf

from redact.metadata import strip_metadata

if TYPE_CHECKING:
    from re import Pattern as CompiledPattern


class RedactionError(Exception):
    """Raised when redaction fails."""


@dataclass
class RedactionResult:
    """Result of a redaction operation."""

    pages_processed: int = 0
    total_redactions: int = 0
    redactions_by_pattern: dict[str, int] = field(default_factory=dict)


def redact_page(
    page: pymupdf.Page,
    patterns: list[tuple[str, "CompiledPattern[str]"]],
) -> RedactionResult:
    """Mark and apply redactions for a single page.

    Searches the page text for all pattern matches, marks them for redaction,
    then applies the redactions (removing text from PDF structure).

    Args:
        page: PyMuPDF page object to redact.
        patterns: List of (pattern_name, compiled_regex) tuples.

    Returns:
        RedactionResult with counts of redactions applied.
    """
    redactions_by_pattern: dict[str, int] = {}
    total_redactions = 0

    page_text = page.get_text()

    for pattern_name, compiled_regex in patterns:
        for match in compiled_regex.finditer(page_text):
            matched_text = match.group()
            # Find all rectangles where this text appears on the page
            rects = page.search_for(matched_text)
            for rect in rects:
                page.add_redact_annot(rect, fill=(0, 0, 0))
                total_redactions += 1
                redactions_by_pattern[pattern_name] = (
                    redactions_by_pattern.get(pattern_name, 0) + 1
                )

    # Apply all redactions at once
    if total_redactions > 0:
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_REMOVE,
            graphics=2,
        )

    return RedactionResult(
        pages_processed=1,
        total_redactions=total_redactions,
        redactions_by_pattern=redactions_by_pattern,
    )


def redact_document(
    input_path: str | Path,
    output_path: str | Path,
    patterns: list[tuple[str, "CompiledPattern[str]"]],
    strip_meta: bool = True,
) -> RedactionResult:
    """Redact a PDF document and save to output path.

    Processes all pages, applies pattern-based redactions, optionally strips
    metadata, and saves with garbage collection to remove unreferenced objects.

    Args:
        input_path: Path to input PDF file.
        output_path: Path to save redacted PDF.
        patterns: List of (pattern_name, compiled_regex) tuples.
        strip_meta: Whether to strip PDF metadata (default True).

    Returns:
        RedactionResult with aggregated counts across all pages.

    Raises:
        RedactionError: If input file doesn't exist or redaction fails.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise RedactionError(f"Input file not found: {input_path}")

    # Aggregate results
    total_pages = 0
    total_redactions = 0
    redactions_by_pattern: dict[str, int] = {}

    try:
        with pymupdf.open(input_path) as doc:
            for page in doc:
                page_result = redact_page(page, patterns)
                total_pages += 1
                total_redactions += page_result.total_redactions

                # Merge pattern counts
                for pattern_name, count in page_result.redactions_by_pattern.items():
                    redactions_by_pattern[pattern_name] = (
                        redactions_by_pattern.get(pattern_name, 0) + count
                    )

            if strip_meta:
                strip_metadata(doc)

            # Save with garbage=4 to remove unreferenced objects (security critical)
            doc.save(output_path, garbage=4, deflate=True, clean=True)
    except RedactionError:
        raise
    except Exception as e:
        raise RedactionError(f"Failed to process PDF: {e}") from e

    return RedactionResult(
        pages_processed=total_pages,
        total_redactions=total_redactions,
        redactions_by_pattern=redactions_by_pattern,
    )
