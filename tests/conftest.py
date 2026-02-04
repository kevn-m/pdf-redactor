"""Shared test fixtures for redact package."""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pymupdf
import pytest
from click.testing import CliRunner


@contextmanager
def pdf_doc() -> Generator[pymupdf.Document, None, None]:
    """Context manager for creating and cleaning up test PDFs.

    Yields an empty PyMuPDF document that is automatically closed
    when the context exits, even if an exception occurs.

    Usage:
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "Test content")
    """
    doc = pymupdf.open()
    try:
        yield doc
    finally:
        doc.close()


def create_pdf_with_text(text: str) -> pymupdf.Document:
    """Create a PDF document with the given text.

    Note: Caller is responsible for closing the returned document.

    Args:
        text: Text to insert at position (50, 50) on the first page.

    Returns:
        A PyMuPDF document with one page containing the text.
    """
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    return doc


@pytest.fixture
def empty_pdf(tmp_path: Path) -> Path:
    """Create an empty PDF file (single blank page).

    Returns the path to the saved PDF file.
    """
    pdf_path = tmp_path / "empty.pdf"
    with pdf_doc() as doc:
        doc.new_page()
        doc.save(pdf_path)
    return pdf_path


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Create a sample PDF with synthetic PII for testing.

    Contains various PII types that match built-in patterns:
    - Email address
    - Phone number (AU format)
    - Account number
    - BSB
    - TFN
    - Card number

    Returns the path to the saved PDF file.
    """
    pdf_path = tmp_path / "sample.pdf"
    with pdf_doc() as doc:
        page = doc.new_page()
        # Insert various PII types
        page.insert_text((50, 50), "Email: test@example.com")
        page.insert_text((50, 80), "Phone: 0412 345 678")
        page.insert_text((50, 110), "Account: 123456789")
        page.insert_text((50, 140), "BSB: 123-456")
        page.insert_text((50, 170), "TFN: 123 456 789")
        page.insert_text((50, 200), "Card: 1234-5678-9012-3456")
        doc.save(pdf_path)
    return pdf_path


@pytest.fixture
def sample_pdf_multipage(tmp_path: Path) -> Path:
    """Create a multi-page PDF with PII on each page.

    Returns the path to the saved PDF file.
    """
    pdf_path = tmp_path / "multipage.pdf"
    with pdf_doc() as doc:
        # Page 1
        page1 = doc.new_page()
        page1.insert_text((50, 50), "Page 1: email1@test.com")
        page1.insert_text((50, 80), "Phone: 0412345678")

        # Page 2
        page2 = doc.new_page()
        page2.insert_text((50, 50), "Page 2: email2@test.com")
        page2.insert_text((50, 80), "Account: 987654321")

        doc.save(pdf_path)
    return pdf_path


@pytest.fixture
def pdf_with_metadata(tmp_path: Path) -> Path:
    """Create a PDF with metadata set.

    Returns the path to the saved PDF file.
    """
    pdf_path = tmp_path / "with_metadata.pdf"
    with pdf_doc() as doc:
        doc.new_page()
        doc.set_metadata({
            "title": "Test Document",
            "author": "Test Author",
            "subject": "Test Subject",
            "creator": "Test Creator",
        })
        doc.save(pdf_path)
    return pdf_path


@pytest.fixture
def runner() -> CliRunner:
    """CLI test runner for Click commands."""
    return CliRunner()
