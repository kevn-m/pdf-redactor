"""End-to-end integration tests for the redact CLI."""

from pathlib import Path
from unittest.mock import patch

import pymupdf
import pytest
from click.testing import CliRunner  # noqa: F401 - used via conftest fixture

from redact.cli import main


class TestFullRedactionWorkflow:
    """End-to-end tests for complete redaction workflows."""

    def test_redact_all_pii_types(self, runner: CliRunner, sample_pdf: Path, tmp_path: Path) -> None:
        """Should redact all PII types with --all-patterns."""
        output_path = tmp_path / "redacted.pdf"

        result = runner.invoke(main, [str(sample_pdf), str(output_path), "--all-patterns"])

        assert result.exit_code == 0
        assert output_path.exists()

        # Verify PII is removed
        with pymupdf.open(output_path) as doc:
            text = doc[0].get_text()
            assert "test@example.com" not in text
            assert "0412 345 678" not in text
            assert "123456789" not in text
            assert "123-456" not in text
            assert "123 456 789" not in text
            assert "1234-5678-9012-3456" not in text

    def test_redact_multipage_document(
        self, runner: CliRunner, sample_pdf_multipage: Path, tmp_path: Path
    ) -> None:
        """Should redact PII from all pages."""
        output_path = tmp_path / "redacted.pdf"

        result = runner.invoke(main, [str(sample_pdf_multipage), str(output_path)])

        assert result.exit_code == 0

        with pymupdf.open(output_path) as doc:
            # Page 1
            page1_text = doc[0].get_text()
            assert "email1@test.com" not in page1_text
            assert "0412345678" not in page1_text

            # Page 2
            page2_text = doc[1].get_text()
            assert "email2@test.com" not in page2_text
            assert "987654321" not in page2_text

    def test_metadata_stripped_by_default(
        self, runner: CliRunner, pdf_with_metadata: Path, tmp_path: Path
    ) -> None:
        """Should strip metadata by default."""
        output_path = tmp_path / "redacted.pdf"

        result = runner.invoke(main, [str(pdf_with_metadata), str(output_path)])

        assert result.exit_code == 0

        with pymupdf.open(output_path) as doc:
            assert doc.metadata.get("title") == ""
            assert doc.metadata.get("author") == ""
            assert doc.metadata.get("subject") == ""

    def test_metadata_preserved_with_flag(
        self, runner: CliRunner, pdf_with_metadata: Path, tmp_path: Path
    ) -> None:
        """Should preserve metadata with --no-metadata flag."""
        output_path = tmp_path / "redacted.pdf"

        result = runner.invoke(
            main, [str(pdf_with_metadata), str(output_path), "--no-metadata"]
        )

        assert result.exit_code == 0

        with pymupdf.open(output_path) as doc:
            assert doc.metadata.get("title") == "Test Document"
            assert doc.metadata.get("author") == "Test Author"


class TestEnvVarIntegration:
    """Integration tests for environment variable pattern loading."""

    @pytest.fixture
    def pdf_with_name(self, tmp_path: Path) -> Path:
        """Create a PDF with a name to redact."""
        from conftest import pdf_doc

        pdf_path = tmp_path / "with_name.pdf"
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "Account holder: Kevin Smith")
            page.insert_text((50, 80), "Address: 123 Test Street, Sydney NSW 2000")
            doc.save(pdf_path)
        return pdf_path

    def test_env_var_patterns_redact_custom_pii(
        self, runner: CliRunner, pdf_with_name: Path, tmp_path: Path
    ) -> None:
        """REDACT_* env vars should be used to redact custom PII."""
        output_path = tmp_path / "redacted.pdf"

        with patch.dict(
            "os.environ",
            {
                "REDACT_FULL_NAME": "Kevin Smith",
                "REDACT_ADDRESS": "123 Test Street, Sydney NSW 2000",
            },
        ):
            result = runner.invoke(main, [str(pdf_with_name), str(output_path)])

        assert result.exit_code == 0

        with pymupdf.open(output_path) as doc:
            text = doc[0].get_text()
            assert "Kevin Smith" not in text
            assert "123 Test Street" not in text


class TestConfigFileIntegration:
    """Integration tests for YAML config file loading."""

    @pytest.fixture
    def pdf_with_custom_pattern(self, tmp_path: Path) -> Path:
        """Create a PDF with custom pattern text."""
        from conftest import pdf_doc

        pdf_path = tmp_path / "custom.pdf"
        with pdf_doc() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), "Reference: REF-12345-ABC")
            page.insert_text((50, 80), "Code: SECRET-999")
            doc.save(pdf_path)
        return pdf_path

    def test_yaml_config_patterns_applied(
        self, runner: CliRunner, pdf_with_custom_pattern: Path, tmp_path: Path
    ) -> None:
        """Should apply patterns from YAML config file."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
patterns:
  reference_code:
    regex: "REF-\\\\d{5}-[A-Z]{3}"
    description: "Reference codes"
  secret_code:
    regex: "SECRET-\\\\d{3}"
    description: "Secret codes"
""")
        output_path = tmp_path / "redacted.pdf"

        result = runner.invoke(
            main, [str(pdf_with_custom_pattern), str(output_path), "--config", str(config_path)]
        )

        assert result.exit_code == 0

        with pymupdf.open(output_path) as doc:
            text = doc[0].get_text()
            assert "REF-12345-ABC" not in text
            assert "SECRET-999" not in text


class TestVerboseOutput:
    """Integration tests for verbose output mode."""

    def test_verbose_shows_pattern_info(
        self, runner: CliRunner, sample_pdf: Path, tmp_path: Path
    ) -> None:
        """Verbose mode should show which patterns are being used."""
        output_path = tmp_path / "redacted.pdf"

        result = runner.invoke(
            main, [str(sample_pdf), str(output_path), "--verbose", "--pattern", "email"]
        )

        assert result.exit_code == 0
        # Should mention the pattern or redaction count
        output_lower = result.output.lower()
        assert "email" in output_lower or "pattern" in output_lower

    def test_verbose_shows_redaction_stats(
        self, runner: CliRunner, sample_pdf: Path, tmp_path: Path
    ) -> None:
        """Verbose mode should show redaction statistics."""
        output_path = tmp_path / "redacted.pdf"

        result = runner.invoke(main, [str(sample_pdf), str(output_path), "--verbose"])

        assert result.exit_code == 0
        # Should show some stats about what was processed
        assert "page" in result.output.lower() or "redact" in result.output.lower()


class TestQuietOutput:
    """Integration tests for quiet output mode."""

    def test_quiet_minimal_output_on_success(
        self, runner: CliRunner, sample_pdf: Path, tmp_path: Path
    ) -> None:
        """Quiet mode should have minimal output on success."""
        output_path = tmp_path / "redacted.pdf"

        result = runner.invoke(main, [str(sample_pdf), str(output_path), "--quiet"])

        assert result.exit_code == 0
        # Output should be empty or very minimal
        assert len(result.output.strip()) < 50


class TestErrorHandling:
    """Integration tests for error scenarios."""

    def test_nonexistent_input_file(self, runner: CliRunner, tmp_path: Path) -> None:
        """Should error gracefully for missing input file."""
        output_path = tmp_path / "output.pdf"

        result = runner.invoke(main, ["/nonexistent/file.pdf", str(output_path)])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "does not exist" in result.output.lower()

    def test_corrupted_pdf(self, runner: CliRunner, tmp_path: Path) -> None:
        """Should error gracefully for corrupted PDF."""
        input_path = tmp_path / "corrupted.pdf"
        input_path.write_bytes(b"This is not a valid PDF")
        output_path = tmp_path / "output.pdf"

        result = runner.invoke(main, [str(input_path), str(output_path)])

        assert result.exit_code != 0

    def test_invalid_config_file(
        self, runner: CliRunner, sample_pdf: Path, tmp_path: Path
    ) -> None:
        """Should error gracefully for invalid YAML config."""
        config_path = tmp_path / "invalid.yaml"
        config_path.write_text("this: is: not: valid: yaml: [")
        output_path = tmp_path / "output.pdf"

        result = runner.invoke(
            main, [str(sample_pdf), str(output_path), "--config", str(config_path)]
        )

        assert result.exit_code != 0


class TestOutputFileCreation:
    """Integration tests for output file handling."""

    def test_creates_output_in_same_directory(
        self, runner: CliRunner, sample_pdf: Path
    ) -> None:
        """Should create output file in same directory as input by default."""
        result = runner.invoke(main, [str(sample_pdf)])

        assert result.exit_code == 0
        expected_output = sample_pdf.parent / "sample_redacted.pdf"
        assert expected_output.exists()

    def test_creates_output_in_specified_directory(
        self, runner: CliRunner, sample_pdf: Path, tmp_path: Path
    ) -> None:
        """Should create output file in specified directory."""
        output_dir = tmp_path / "output_dir"
        output_dir.mkdir()
        output_path = output_dir / "result.pdf"

        result = runner.invoke(main, [str(sample_pdf), str(output_path)])

        assert result.exit_code == 0
        assert output_path.exists()


class TestGarbageCollection:
    """Integration tests for PDF garbage collection (security)."""

    def test_original_text_not_recoverable(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Redacted text should not be recoverable from raw PDF bytes."""
        # Create PDF with specific text
        input_path = tmp_path / "input.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "SECRET_CODE_12345678")
        doc.save(input_path)
        doc.close()

        output_path = tmp_path / "output.pdf"

        result = runner.invoke(
            main, [str(input_path), str(output_path), "--pattern", "account_number"]
        )

        assert result.exit_code == 0

        # Read raw bytes and verify original text is gone
        output_bytes = output_path.read_bytes()
        assert b"12345678" not in output_bytes
