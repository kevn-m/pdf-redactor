"""PDF metadata stripping for redaction."""

import pymupdf


def strip_metadata(doc: pymupdf.Document) -> dict[str, str]:
    """Clear PDF and XMP metadata, returning original for logging.

    Removes all standard PDF metadata fields (title, author, subject, etc.)
    and XMP metadata if present. The original metadata is returned so it
    can be logged for audit purposes.

    Args:
        doc: An open PyMuPDF Document object.

    Returns:
        Dict containing the original metadata before stripping.
    """
    # Capture original metadata
    original = dict(doc.metadata) if doc.metadata else {}

    # Clear standard PDF metadata
    doc.set_metadata({})

    # Clear XMP metadata if present
    if doc.xref_xml_metadata():
        doc.del_xml_metadata()

    return original
