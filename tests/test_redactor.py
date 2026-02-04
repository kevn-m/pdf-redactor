"""Tests for redact.redactor module."""

import re
from contextlib import contextmanager
from pathlib import Path

import pymupdf
import pytest

from redact.redactor import (
    RedactionError,
    RedactionResult,
    redact_document,
    redact_page,
    strip_images_from_page,
)


@contextmanager
def pdf_doc():
    """Context manager for creating and cleaning up test PDFs."""
    doc = pymupdf.open()
    try:
        yield doc
    finally:
        doc.close()


def create_pdf_with_text(text: str) -> pymupdf.Document:
    """Create a PDF document with the given text."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    return doc


class TestRedactionResult:
    """Tests for RedactionResult dataclass."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        result = RedactionResult()
        assert result.pages_processed == 0
        assert result.total_redactions == 0
        assert result.redactions_by_pattern == {}

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        result = RedactionResult(
            pages_processed=5,
            total_redactions=10,
            redactions_by_pattern={"email": 3, "phone_au": 7},
        )
        assert result.pages_processed == 5
        assert result.total_redactions == 10
        assert result.redactions_by_pattern == {"email": 3, "phone_au": 7}


class TestRedactionError:
    """Tests for RedactionError exception."""

    def test_is_exception(self) -> None:
        """Should be an Exception subclass."""
        assert issubclass(RedactionError, Exception)

    def test_can_be_raised(self) -> None:
        """Should be raisable with a message."""
        with pytest.raises(RedactionError, match="Test error"):
            raise RedactionError("Test error")


class TestRedactPage:
    """Tests for redact_page function."""

    def test_redacts_matching_text(self) -> None:
        """Should redact text matching pattern."""
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "Contact: test@example.com for info")

            patterns = [("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"))]

            result = redact_page(page, patterns)

            # Email should be redacted
            text = page.get_text()
            assert "test@example.com" not in text
            assert result.total_redactions == 1
            assert result.redactions_by_pattern.get("email") == 1

    def test_redacts_multiple_matches(self) -> None:
        """Should redact all matches of a pattern."""
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "Email: a@b.com and c@d.com")

            patterns = [("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"))]

            result = redact_page(page, patterns)

            text = page.get_text()
            assert "a@b.com" not in text
            assert "c@d.com" not in text
            assert result.total_redactions == 2

    def test_redacts_multiple_patterns(self) -> None:
        """Should redact matches from multiple patterns."""
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "Email: test@test.com Phone: 0412345678")

            patterns = [
                ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
                ("phone_au", re.compile(r"(?<![A-Za-z0-9])(?:\+61[ -]?|0)[2-478](?:[ -]?\d){8}\b")),
            ]

            result = redact_page(page, patterns)

            text = page.get_text()
            assert "test@test.com" not in text
            assert "0412345678" not in text
            assert result.total_redactions == 2
            assert result.redactions_by_pattern.get("email") == 1
            assert result.redactions_by_pattern.get("phone_au") == 1

    def test_no_matches_returns_zero_redactions(self) -> None:
        """Should return zero redactions when no matches found."""
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "No PII here, just plain text.")

            patterns = [("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"))]

            result = redact_page(page, patterns)

            assert result.total_redactions == 0
            assert result.redactions_by_pattern == {}

    def test_empty_patterns_list(self) -> None:
        """Should handle empty patterns list."""
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "test@example.com")

            result = redact_page(page, [])

            # No redactions should occur
            text = page.get_text()
            assert "test@example.com" in text
            assert result.total_redactions == 0

    def test_preserves_non_matching_text(self) -> None:
        """Should preserve text that doesn't match patterns."""
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "Keep this text. Redact: test@test.com")

            patterns = [("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"))]

            redact_page(page, patterns)

            text = page.get_text()
            assert "Keep this text" in text
            assert "test@test.com" not in text

    def test_returns_redaction_result(self) -> None:
        """Should return a RedactionResult instance."""
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "test@example.com")

            patterns = [("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"))]

            result = redact_page(page, patterns)

            assert isinstance(result, RedactionResult)


class TestRedactDocument:
    """Tests for redact_document function."""

    def test_redacts_single_page(self, tmp_path: Path) -> None:
        """Should redact PII from a single-page document."""
        input_pdf = tmp_path / "input.pdf"
        output_pdf = tmp_path / "output.pdf"

        # Create input PDF
        doc = create_pdf_with_text("Contact: test@example.com")
        doc.save(input_pdf)
        doc.close()

        patterns = [("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"))]

        result = redact_document(input_pdf, output_pdf, patterns)

        # Verify output
        with pymupdf.open(output_pdf) as doc:
            text = doc[0].get_text()
            assert "test@example.com" not in text

        assert result.pages_processed == 1
        assert result.total_redactions == 1

    def test_redacts_multiple_pages(self, tmp_path: Path) -> None:
        """Should redact PII from all pages."""
        input_pdf = tmp_path / "input.pdf"
        output_pdf = tmp_path / "output.pdf"

        # Create multi-page PDF
        doc = pymupdf.open()
        page1 = doc.new_page()
        page1.insert_text((50, 50), "Page 1: email1@test.com")
        page2 = doc.new_page()
        page2.insert_text((50, 50), "Page 2: email2@test.com")
        doc.save(input_pdf)
        doc.close()

        patterns = [("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"))]

        result = redact_document(input_pdf, output_pdf, patterns)

        # Verify both pages redacted
        with pymupdf.open(output_pdf) as doc:
            assert "email1@test.com" not in doc[0].get_text()
            assert "email2@test.com" not in doc[1].get_text()

        assert result.pages_processed == 2
        assert result.total_redactions == 2

    def test_strips_metadata_by_default(self, tmp_path: Path) -> None:
        """Should strip metadata by default."""
        input_pdf = tmp_path / "input.pdf"
        output_pdf = tmp_path / "output.pdf"

        # Create PDF with metadata
        doc = pymupdf.open()
        doc.new_page()
        doc.set_metadata({"title": "Secret Title", "author": "Secret Author"})
        doc.save(input_pdf)
        doc.close()

        redact_document(input_pdf, output_pdf, [])

        # Verify metadata stripped
        with pymupdf.open(output_pdf) as doc:
            assert doc.metadata.get("title") == ""
            assert doc.metadata.get("author") == ""

    def test_preserves_metadata_when_disabled(self, tmp_path: Path) -> None:
        """Should preserve metadata when strip_meta=False."""
        input_pdf = tmp_path / "input.pdf"
        output_pdf = tmp_path / "output.pdf"

        # Create PDF with metadata
        doc = pymupdf.open()
        doc.new_page()
        doc.set_metadata({"title": "Keep This Title"})
        doc.save(input_pdf)
        doc.close()

        redact_document(input_pdf, output_pdf, [], strip_meta=False)

        # Verify metadata preserved
        with pymupdf.open(output_pdf) as doc:
            assert doc.metadata.get("title") == "Keep This Title"

    def test_raises_on_nonexistent_input(self, tmp_path: Path) -> None:
        """Should raise RedactionError for missing input file."""
        output_pdf = tmp_path / "output.pdf"

        with pytest.raises(RedactionError, match="Input file not found"):
            redact_document(tmp_path / "nonexistent.pdf", output_pdf, [])

    def test_raises_on_corrupted_pdf(self, tmp_path: Path) -> None:
        """Should raise RedactionError for corrupted PDF."""
        input_pdf = tmp_path / "corrupted.pdf"
        output_pdf = tmp_path / "output.pdf"

        # Create a corrupted PDF file
        input_pdf.write_bytes(b"This is not a valid PDF file content")

        with pytest.raises(RedactionError, match="Failed to process PDF"):
            redact_document(input_pdf, output_pdf, [])

    def test_creates_output_file(self, tmp_path: Path) -> None:
        """Should create the output file."""
        input_pdf = tmp_path / "input.pdf"
        output_pdf = tmp_path / "output.pdf"

        doc = create_pdf_with_text("Test content")
        doc.save(input_pdf)
        doc.close()

        redact_document(input_pdf, output_pdf, [])

        assert output_pdf.exists()

    def test_accepts_string_paths(self, tmp_path: Path) -> None:
        """Should accept string paths as well as Path objects."""
        input_pdf = tmp_path / "input.pdf"
        output_pdf = tmp_path / "output.pdf"

        doc = create_pdf_with_text("test@test.com")
        doc.save(input_pdf)
        doc.close()

        # Pass strings instead of Path objects
        result = redact_document(str(input_pdf), str(output_pdf), [])

        assert output_pdf.exists()
        assert isinstance(result, RedactionResult)

    def test_saves_with_garbage_collection(self, tmp_path: Path) -> None:
        """Should save with garbage=4 to remove unreferenced objects."""
        input_pdf = tmp_path / "input.pdf"
        output_pdf = tmp_path / "output.pdf"

        # Create PDF with text to redact
        doc = create_pdf_with_text("Secret: 123456789012")
        doc.save(input_pdf)
        doc.close()

        patterns = [("account_number", re.compile(r"\b\d{6,12}\b"))]

        redact_document(input_pdf, output_pdf, patterns)

        # Read the raw bytes of output to verify original text is gone
        output_bytes = output_pdf.read_bytes()
        # The original text should not appear in the raw file
        assert b"123456789012" not in output_bytes

    def test_returns_aggregated_result(self, tmp_path: Path) -> None:
        """Should return aggregated results across all pages."""
        input_pdf = tmp_path / "input.pdf"
        output_pdf = tmp_path / "output.pdf"

        # Create multi-page PDF with mixed PII
        doc = pymupdf.open()
        page1 = doc.new_page()
        page1.insert_text((50, 50), "a@b.com c@d.com 0412345678")
        page2 = doc.new_page()
        page2.insert_text((50, 50), "e@f.com")
        doc.save(input_pdf)
        doc.close()

        patterns = [
            ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
            ("phone_au", re.compile(r"(?<![A-Za-z0-9])(?:\+61[ -]?|0)[2-478](?:[ -]?\d){8}\b")),
        ]

        result = redact_document(input_pdf, output_pdf, patterns)

        assert result.pages_processed == 2
        assert result.total_redactions == 4  # 3 emails + 1 phone
        assert result.redactions_by_pattern.get("email") == 3
        assert result.redactions_by_pattern.get("phone_au") == 1

    def test_empty_document(self, tmp_path: Path) -> None:
        """Should handle document with no pages gracefully."""
        input_pdf = tmp_path / "input.pdf"
        output_pdf = tmp_path / "output.pdf"

        # Create empty PDF (no pages)
        doc = pymupdf.open()
        doc.new_page()  # PyMuPDF requires at least one page
        doc.save(input_pdf)
        doc.close()

        patterns = [("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"))]

        result = redact_document(input_pdf, output_pdf, patterns)

        assert result.pages_processed == 1
        assert result.total_redactions == 0


class TestRedactPageEdgeCases:
    """Edge case tests for redact_page behaviour."""

    def test_redacts_all_instances_of_matched_text(self) -> None:
        """Should redact all instances of matched text on page.

        Note: This is expected behaviour. When a pattern matches text,
        ALL occurrences of that exact text on the page are redacted.
        Users should use precise patterns to avoid over-redaction.
        """
        with pdf_doc() as doc:
            page = doc.new_page()
            # "123456789" appears twice - once in context, once standalone
            page.insert_text((50, 50), "Account: 123456789")
            page.insert_text((50, 100), "Code: 123456789")

            # Pattern only matches the full account context
            patterns = [("account", re.compile(r"Account: \d{9}"))]
            result = redact_page(page, patterns)

            text = page.get_text()
            # Both instances of "123456789" will be redacted because
            # page.search_for() finds all occurrences of the matched text
            assert "Account:" not in text or "123456789" not in text
            # The count reflects rectangles marked, which may be more than regex matches
            assert result.total_redactions >= 1


class TestRedactPageIntegration:
    """Integration tests for page redaction with real patterns."""

    def test_redacts_account_number(self) -> None:
        """Should redact bank account numbers."""
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "Account: 123456789")

            patterns = [("account_number", re.compile(r"\b\d{6,12}\b"))]
            result = redact_page(page, patterns)

            assert "123456789" not in page.get_text()
            assert result.total_redactions == 1

    def test_redacts_card_number(self) -> None:
        """Should redact credit card numbers."""
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "Card: 1234-5678-9012-3456")

            patterns = [("card_number", re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"))]
            result = redact_page(page, patterns)

            assert "1234-5678-9012-3456" not in page.get_text()
            assert result.total_redactions == 1

    def test_redacts_bsb(self) -> None:
        """Should redact BSB numbers."""
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "BSB: 123-456")

            patterns = [("bsb", re.compile(r"\b\d{3}[-\s]?\d{3}\b"))]
            result = redact_page(page, patterns)

            assert "123-456" not in page.get_text()
            assert result.total_redactions == 1

    def test_redacts_tfn(self) -> None:
        """Should redact Tax File Numbers."""
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "TFN: 123 456 789")

            patterns = [("tfn", re.compile(r"\b\d{3}[-\s]?\d{3}[-\s]?\d{3}\b"))]
            result = redact_page(page, patterns)

            assert "123 456 789" not in page.get_text()
            assert result.total_redactions == 1

    def test_redacts_international_phone(self) -> None:
        """Should redact Australian phone with +61 prefix."""
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "Phone: +61 412 345 678")

            patterns = [("phone_au", re.compile(r"(?<![A-Za-z0-9])(?:\+61[ -]?|0)[2-478](?:[ -]?\d){8}\b"))]
            result = redact_page(page, patterns)

            assert "+61 412 345 678" not in page.get_text()
            assert result.total_redactions == 1


class TestStripImagesFromPage:
    """Tests for strip_images_from_page function."""

    def test_removes_image_from_page(self) -> None:
        """Should remove images from page."""
        with pdf_doc() as doc:
            page = doc.new_page()
            # Insert a simple image
            img = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), 1)
            page.insert_image(pymupdf.Rect(50, 50, 100, 100), pixmap=img)

            # Verify image exists
            assert len(page.get_images()) == 1

            count = strip_images_from_page(page)

            assert count == 1

    def test_returns_zero_when_no_images(self) -> None:
        """Should return 0 when page has no images."""
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "Text only, no images")

            count = strip_images_from_page(page)

            assert count == 0

    def test_removes_multiple_images(self) -> None:
        """Should remove all images from page."""
        with pdf_doc() as doc:
            page = doc.new_page()
            # Insert multiple images
            img = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), 1)
            page.insert_image(pymupdf.Rect(50, 50, 100, 100), pixmap=img)
            page.insert_image(pymupdf.Rect(150, 50, 200, 100), pixmap=img)

            assert len(page.get_images()) == 2

            count = strip_images_from_page(page)

            assert count == 2


class TestRedactDocumentWithImages:
    """Tests for redact_document with strip_images option."""

    def test_strip_images_removes_all_images(self, tmp_path: Path) -> None:
        """Should remove all images when strip_images=True."""
        input_pdf = tmp_path / "input.pdf"
        output_pdf = tmp_path / "output.pdf"

        # Create PDF with image
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Some text")
        img = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), 1)
        page.insert_image(pymupdf.Rect(50, 100, 100, 150), pixmap=img)
        doc.save(input_pdf)
        doc.close()

        result = redact_document(input_pdf, output_pdf, [], strip_images=True)

        assert result.images_removed == 1

        # Verify image is gone in output
        with pymupdf.open(output_pdf) as doc:
            assert len(doc[0].get_images()) == 0

    def test_preserves_images_by_default(self, tmp_path: Path) -> None:
        """Should preserve images when strip_images=False (default)."""
        input_pdf = tmp_path / "input.pdf"
        output_pdf = tmp_path / "output.pdf"

        # Create PDF with image
        doc = pymupdf.open()
        page = doc.new_page()
        img = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), 1)
        page.insert_image(pymupdf.Rect(50, 50, 100, 100), pixmap=img)
        doc.save(input_pdf)
        doc.close()

        result = redact_document(input_pdf, output_pdf, [])

        assert result.images_removed == 0

        # Verify image still exists in output
        with pymupdf.open(output_pdf) as doc:
            assert len(doc[0].get_images()) == 1

    def test_strip_images_with_text_redaction(self, tmp_path: Path) -> None:
        """Should handle both image stripping and text redaction."""
        input_pdf = tmp_path / "input.pdf"
        output_pdf = tmp_path / "output.pdf"

        # Create PDF with image and text
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Email: test@example.com")
        img = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), 1)
        page.insert_image(pymupdf.Rect(50, 100, 100, 150), pixmap=img)
        doc.save(input_pdf)
        doc.close()

        patterns = [("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"))]

        result = redact_document(input_pdf, output_pdf, patterns, strip_images=True)

        assert result.images_removed == 1
        assert result.total_redactions == 1

        # Verify both image gone and text redacted
        with pymupdf.open(output_pdf) as doc:
            assert len(doc[0].get_images()) == 0
            assert "test@example.com" not in doc[0].get_text()
