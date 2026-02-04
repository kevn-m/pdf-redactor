"""Tests for redact.metadata module."""

from contextlib import contextmanager

import pymupdf
import pytest

from redact.metadata import strip_metadata


@contextmanager
def pdf_doc():
    """Context manager for creating and cleaning up test PDFs."""
    doc = pymupdf.open()
    try:
        yield doc
    finally:
        doc.close()


class TestStripMetadata:
    """Tests for strip_metadata function."""

    def test_returns_original_metadata(self) -> None:
        """Should return the original metadata before stripping."""
        with pdf_doc() as doc:
            doc.new_page()
            original_metadata = {
                "title": "Test Document",
                "author": "John Smith",
                "subject": "Test Subject",
                "keywords": "test, metadata",
                "creator": "Test Creator",
                "producer": "Test Producer",
            }
            doc.set_metadata(original_metadata)

            result = strip_metadata(doc)

            assert result["title"] == "Test Document"
            assert result["author"] == "John Smith"
            assert result["subject"] == "Test Subject"
            assert result["keywords"] == "test, metadata"
            assert result["creator"] == "Test Creator"
            assert result["producer"] == "Test Producer"

    def test_clears_pdf_metadata(self) -> None:
        """Should clear all PDF metadata fields."""
        with pdf_doc() as doc:
            doc.new_page()
            doc.set_metadata({
                "title": "Secret Title",
                "author": "Secret Author",
            })

            strip_metadata(doc)

            # Metadata should be cleared
            metadata = doc.metadata
            assert metadata.get("title") == ""
            assert metadata.get("author") == ""

    def test_handles_empty_metadata(self) -> None:
        """Should handle PDF with no metadata gracefully."""
        with pdf_doc() as doc:
            doc.new_page()
            # No metadata set

            result = strip_metadata(doc)

            # Should return empty or default metadata dict
            assert isinstance(result, dict)

    def test_clears_xmp_metadata(self) -> None:
        """Should clear XMP metadata if present."""
        with pdf_doc() as doc:
            doc.new_page()

            # Set XMP metadata
            xmp_data = """<?xml version="1.0" encoding="UTF-8"?>
            <x:xmpmeta xmlns:x="adobe:ns:meta/">
                <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
                    <rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/">
                        <dc:title>Secret XMP Title</dc:title>
                    </rdf:Description>
                </rdf:RDF>
            </x:xmpmeta>"""
            doc.set_xml_metadata(xmp_data)

            # Verify XMP was set
            assert doc.xref_xml_metadata() > 0

            strip_metadata(doc)

            # XMP should be deleted - xref_xml_metadata returns 0 when no XMP exists
            assert doc.xref_xml_metadata() == 0

    def test_handles_no_xmp_metadata(self) -> None:
        """Should handle PDF without XMP metadata gracefully."""
        with pdf_doc() as doc:
            doc.new_page()
            # No XMP metadata set

            # Should not raise an error
            result = strip_metadata(doc)

            assert isinstance(result, dict)

    def test_metadata_cleared_after_save(self, tmp_path) -> None:
        """Should ensure metadata is cleared when document is saved."""
        pdf_path = tmp_path / "test.pdf"

        # Create and save a PDF with metadata
        with pdf_doc() as doc:
            doc.new_page()
            doc.set_metadata({
                "title": "Original Title",
                "author": "Original Author",
            })
            doc.save(pdf_path)

        # Open, strip metadata, and save
        output_path = tmp_path / "output.pdf"
        with pymupdf.open(pdf_path) as doc:
            strip_metadata(doc)
            doc.save(output_path, garbage=4)

        # Verify metadata is cleared in saved file
        with pymupdf.open(output_path) as doc:
            metadata = doc.metadata
            assert metadata.get("title") == ""
            assert metadata.get("author") == ""

    def test_returns_dict_type(self) -> None:
        """Should return a dict (not some other mapping type)."""
        with pdf_doc() as doc:
            doc.new_page()
            doc.set_metadata({"title": "Test"})

            result = strip_metadata(doc)

            assert type(result) is dict

    def test_preserves_document_content(self) -> None:
        """Should not affect the actual document content."""
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "Test content that should remain")
            doc.set_metadata({"title": "To be stripped"})

            strip_metadata(doc)

            # Content should still be there
            text = doc[0].get_text()
            assert "Test content that should remain" in text

    def test_multiple_calls_idempotent(self) -> None:
        """Calling strip_metadata multiple times should be safe."""
        with pdf_doc() as doc:
            doc.new_page()
            doc.set_metadata({"title": "Test"})

            # First call
            result1 = strip_metadata(doc)
            # Second call on already-stripped doc
            result2 = strip_metadata(doc)

            # First call should have had metadata
            assert result1.get("title") == "Test"
            # Second call should have empty metadata
            assert result2.get("title") == ""
