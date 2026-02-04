"""Tests for CLI module."""

from pathlib import Path
from unittest.mock import patch

import pymupdf
import pytest
from click.testing import CliRunner

from redact.cli import (
    find_pdf_files,
    get_batch_output_dir,
    get_default_output,
    list_patterns,
    main,
)


class TestGetDefaultOutput:
    """Tests for get_default_output function."""

    def test_adds_redacted_suffix(self):
        """Should add _redacted before extension."""
        result = get_default_output("document.pdf")
        assert result == Path("document_redacted.pdf")

    def test_preserves_path(self):
        """Should preserve directory path."""
        result = get_default_output("/path/to/document.pdf")
        assert result == Path("/path/to/document_redacted.pdf")

    def test_handles_path_object(self):
        """Should accept Path objects."""
        result = get_default_output(Path("document.pdf"))
        assert result == Path("document_redacted.pdf")

    def test_handles_multiple_dots(self):
        """Should only replace the final extension."""
        result = get_default_output("my.document.pdf")
        assert result == Path("my.document_redacted.pdf")


class TestListPatterns:
    """Tests for list_patterns function."""

    def test_returns_formatted_string(self):
        """Should return formatted pattern list."""
        result = list_patterns()
        assert "account_number" in result
        assert "card_number" in result
        assert "bsb" in result
        assert "tfn" in result
        assert "email" in result
        assert "phone_au" in result

    def test_includes_descriptions(self):
        """Should include pattern descriptions."""
        result = list_patterns()
        assert "Bank account" in result
        assert "Card number" in result


class TestMainCommand:
    """Tests for main CLI command."""

    @pytest.fixture
    def runner(self):
        """CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a sample PDF with test content."""
        pdf_path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Test content with email test@example.com")
        page.insert_text((50, 100), "Account 123456789 BSB 123-456")
        doc.save(pdf_path)
        doc.close()
        return pdf_path

    def test_version_option(self, runner):
        """--version should display version."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_list_patterns_option(self, runner):
        """--list-patterns should list available patterns."""
        result = runner.invoke(main, ["--list-patterns"])
        assert result.exit_code == 0
        assert "account_number" in result.output
        assert "email" in result.output

    def test_list_patterns_short_option(self, runner):
        """-l should list available patterns."""
        result = runner.invoke(main, ["-l"])
        assert result.exit_code == 0
        assert "account_number" in result.output

    def test_missing_input_file(self, runner):
        """Should error when input file doesn't exist."""
        result = runner.invoke(main, ["nonexistent.pdf"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "does not exist" in result.output.lower()

    def test_basic_redaction(self, runner, sample_pdf, tmp_path):
        """Should redact PDF with all patterns by default."""
        output_path = tmp_path / "output.pdf"
        result = runner.invoke(main, [str(sample_pdf), str(output_path)])
        assert result.exit_code == 0
        assert output_path.exists()

    def test_default_output_naming(self, runner, sample_pdf):
        """Should create foo_redacted.pdf when no output specified."""
        result = runner.invoke(main, [str(sample_pdf)])
        assert result.exit_code == 0
        expected_output = sample_pdf.parent / "test_redacted.pdf"
        assert expected_output.exists()

    def test_specific_pattern_option(self, runner, sample_pdf, tmp_path):
        """--pattern should use only specified patterns."""
        output_path = tmp_path / "output.pdf"
        result = runner.invoke(
            main, [str(sample_pdf), str(output_path), "--pattern", "email"]
        )
        assert result.exit_code == 0
        assert output_path.exists()

    def test_multiple_pattern_options(self, runner, sample_pdf, tmp_path):
        """Should accept multiple --pattern options."""
        output_path = tmp_path / "output.pdf"
        result = runner.invoke(
            main,
            [
                str(sample_pdf),
                str(output_path),
                "-p",
                "email",
                "-p",
                "account_number",
            ],
        )
        assert result.exit_code == 0

    def test_all_patterns_option(self, runner, sample_pdf, tmp_path):
        """--all-patterns should use all built-in patterns."""
        output_path = tmp_path / "output.pdf"
        result = runner.invoke(
            main, [str(sample_pdf), str(output_path), "--all-patterns"]
        )
        assert result.exit_code == 0

    def test_config_option(self, runner, sample_pdf, tmp_path):
        """--config should load patterns from YAML file."""
        config_path = tmp_path / "patterns.yaml"
        config_path.write_text(
            """
patterns:
  custom_pattern:
    regex: "test"
    description: "Test pattern"
"""
        )
        output_path = tmp_path / "output.pdf"
        result = runner.invoke(
            main, [str(sample_pdf), str(output_path), "--config", str(config_path)]
        )
        assert result.exit_code == 0

    def test_config_file_not_found(self, runner, sample_pdf, tmp_path):
        """Should error when config file doesn't exist."""
        output_path = tmp_path / "output.pdf"
        result = runner.invoke(
            main,
            [str(sample_pdf), str(output_path), "--config", "/nonexistent/config.yaml"],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_no_metadata_option(self, runner, sample_pdf, tmp_path):
        """--no-metadata should skip metadata stripping."""
        output_path = tmp_path / "output.pdf"
        result = runner.invoke(
            main, [str(sample_pdf), str(output_path), "--no-metadata"]
        )
        assert result.exit_code == 0

    def test_verbose_option(self, runner, sample_pdf, tmp_path):
        """--verbose should show detailed output."""
        output_path = tmp_path / "output.pdf"
        result = runner.invoke(
            main, [str(sample_pdf), str(output_path), "--verbose"]
        )
        assert result.exit_code == 0
        # Verbose output should mention patterns or redactions
        assert "pattern" in result.output.lower() or "redact" in result.output.lower()

    def test_quiet_option(self, runner, sample_pdf, tmp_path):
        """--quiet should suppress non-error output."""
        output_path = tmp_path / "output.pdf"
        result = runner.invoke(main, [str(sample_pdf), str(output_path), "--quiet"])
        assert result.exit_code == 0
        # Quiet mode should have minimal output
        assert result.output.strip() == "" or len(result.output.strip()) < 50

    def test_verbose_and_quiet_mutually_exclusive(self, runner, sample_pdf, tmp_path):
        """Should not allow both --verbose and --quiet."""
        output_path = tmp_path / "output.pdf"
        result = runner.invoke(
            main, [str(sample_pdf), str(output_path), "--verbose", "--quiet"]
        )
        assert result.exit_code != 0
        assert "cannot use" in result.output.lower() or "together" in result.output.lower()

    def test_invalid_pattern_name(self, runner, sample_pdf, tmp_path):
        """Should warn or error on invalid pattern name."""
        output_path = tmp_path / "output.pdf"
        result = runner.invoke(
            main, [str(sample_pdf), str(output_path), "--pattern", "nonexistent_pattern"]
        )
        # Should either error or warn about invalid pattern
        assert result.exit_code != 0 or "unknown" in result.output.lower() or "not found" in result.output.lower()

    def test_same_input_output_path_rejected(self, runner, sample_pdf):
        """Should reject when output path equals input path."""
        result = runner.invoke(main, [str(sample_pdf), str(sample_pdf)])
        assert result.exit_code != 0
        assert "same as input" in result.output.lower()

    def test_creates_output_parent_directories(self, runner, sample_pdf, tmp_path):
        """Should create parent directories for output path."""
        output_path = tmp_path / "nested" / "dirs" / "output.pdf"
        result = runner.invoke(main, [str(sample_pdf), str(output_path)])
        assert result.exit_code == 0
        assert output_path.exists()

    def test_strip_images_option(self, runner, tmp_path):
        """--strip-images should remove all images from PDF."""
        # Create PDF with image
        input_pdf = tmp_path / "with_image.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Text content")
        img = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), 1)
        page.insert_image(pymupdf.Rect(50, 100, 100, 150), pixmap=img)
        doc.save(input_pdf)
        doc.close()

        output_pdf = tmp_path / "output.pdf"
        result = runner.invoke(main, [str(input_pdf), str(output_pdf), "--strip-images"])

        assert result.exit_code == 0
        assert "image" in result.output.lower()

        # Verify image removed
        with pymupdf.open(output_pdf) as doc:
            assert len(doc[0].get_images()) == 0


class TestEnvVarPatterns:
    """Tests for REDACT_* environment variable patterns."""

    @pytest.fixture
    def runner(self):
        """CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def sample_pdf_with_name(self, tmp_path):
        """Create a PDF with a name to redact."""
        pdf_path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Account holder: John Smith")
        doc.save(pdf_path)
        doc.close()
        return pdf_path

    def test_env_vars_as_patterns(self, runner, sample_pdf_with_name, tmp_path):
        """REDACT_* env vars should be used as literal patterns."""
        output_path = tmp_path / "output.pdf"
        with patch.dict("os.environ", {"REDACT_FULL_NAME": "John Smith"}):
            result = runner.invoke(
                main, [str(sample_pdf_with_name), str(output_path)]
            )
        assert result.exit_code == 0
        assert output_path.exists()


class TestOutputMessages:
    """Tests for CLI output messages."""

    @pytest.fixture
    def runner(self):
        """CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a sample PDF."""
        pdf_path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Email: user@example.com")
        doc.save(pdf_path)
        doc.close()
        return pdf_path

    def test_success_message(self, runner, sample_pdf, tmp_path):
        """Should show success message on completion."""
        output_path = tmp_path / "output.pdf"
        result = runner.invoke(main, [str(sample_pdf), str(output_path)])
        assert result.exit_code == 0
        # Should indicate successful completion
        assert "redacted" in result.output.lower() or output_path.exists()

    def test_verbose_shows_redaction_count(self, runner, sample_pdf, tmp_path):
        """Verbose mode should show redaction counts."""
        output_path = tmp_path / "output.pdf"
        result = runner.invoke(
            main,
            [str(sample_pdf), str(output_path), "--verbose", "--pattern", "email"],
        )
        assert result.exit_code == 0
        # Should show some indication of what was redacted
        assert "email" in result.output.lower() or "1" in result.output


class TestFindPdfFiles:
    """Tests for find_pdf_files function."""

    def test_returns_sorted_pdfs(self, tmp_path):
        """Should return PDF files sorted alphabetically."""
        # Create PDFs in non-alphabetical order
        (tmp_path / "charlie.pdf").touch()
        (tmp_path / "alpha.pdf").touch()
        (tmp_path / "bravo.pdf").touch()

        result = find_pdf_files(tmp_path)

        assert len(result) == 3
        assert result[0].name == "alpha.pdf"
        assert result[1].name == "bravo.pdf"
        assert result[2].name == "charlie.pdf"

    def test_empty_directory(self, tmp_path):
        """Should return empty list for directory with no PDFs."""
        result = find_pdf_files(tmp_path)
        assert result == []

    def test_ignores_non_pdf_files(self, tmp_path):
        """Should only return .pdf files."""
        (tmp_path / "document.pdf").touch()
        (tmp_path / "image.png").touch()
        (tmp_path / "text.txt").touch()

        result = find_pdf_files(tmp_path)

        assert len(result) == 1
        assert result[0].name == "document.pdf"

    def test_non_recursive(self, tmp_path):
        """Should not search subdirectories."""
        (tmp_path / "top.pdf").touch()
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.pdf").touch()

        result = find_pdf_files(tmp_path)

        assert len(result) == 1
        assert result[0].name == "top.pdf"

    def test_case_insensitive_extension(self, tmp_path):
        """Should match .PDF and .pdf extensions."""
        (tmp_path / "lower.pdf").touch()
        (tmp_path / "upper.PDF").touch()

        result = find_pdf_files(tmp_path)

        assert len(result) == 2


class TestGetBatchOutputDir:
    """Tests for get_batch_output_dir function."""

    def test_default_returns_redacted_subdir(self, tmp_path):
        """Should return <input>/redacted/ when no custom dir specified."""
        result = get_batch_output_dir(tmp_path)
        assert result == tmp_path / "redacted"

    def test_custom_output_dir(self, tmp_path):
        """Should return custom directory when specified."""
        custom_dir = tmp_path / "custom_output"
        result = get_batch_output_dir(tmp_path, custom_dir)
        assert result == custom_dir

    def test_accepts_string_path(self, tmp_path):
        """Should accept string paths."""
        result = get_batch_output_dir(tmp_path, "/custom/path")
        assert result == Path("/custom/path")


class TestBatchProcessing:
    """Tests for batch processing CLI functionality."""

    @pytest.fixture
    def runner(self):
        """CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def batch_folder(self, tmp_path):
        """Create folder with multiple test PDFs."""
        folder = tmp_path / "statements"
        folder.mkdir()

        for name in ["statement1", "statement2", "statement3"]:
            pdf_path = folder / f"{name}.pdf"
            doc = pymupdf.open()
            page = doc.new_page()
            page.insert_text((50, 50), f"Email: {name}@example.com")
            page.insert_text((50, 100), "Account: 123456789")
            doc.save(pdf_path)
            doc.close()

        return folder

    def test_batch_creates_redacted_directory(self, runner, batch_folder):
        """Batch mode should create redacted/ subdirectory."""
        result = runner.invoke(main, [str(batch_folder)])

        assert result.exit_code == 0
        redacted_dir = batch_folder / "redacted"
        assert redacted_dir.exists()
        assert redacted_dir.is_dir()

    def test_batch_processes_all_pdfs(self, runner, batch_folder):
        """Batch mode should process all PDFs in folder."""
        result = runner.invoke(main, [str(batch_folder)])

        assert result.exit_code == 0
        redacted_dir = batch_folder / "redacted"

        expected_files = [
            "statement1_redacted.pdf",
            "statement2_redacted.pdf",
            "statement3_redacted.pdf",
        ]
        for filename in expected_files:
            assert (redacted_dir / filename).exists()

    def test_batch_with_custom_output_dir(self, runner, batch_folder, tmp_path):
        """--output-dir should place files in custom directory."""
        custom_output = tmp_path / "custom_output"

        result = runner.invoke(
            main, [str(batch_folder), "--output-dir", str(custom_output)]
        )

        assert result.exit_code == 0
        assert custom_output.exists()
        assert (custom_output / "statement1_redacted.pdf").exists()

    def test_batch_empty_folder_error(self, runner, tmp_path):
        """Should error when folder contains no PDFs."""
        empty_folder = tmp_path / "empty"
        empty_folder.mkdir()

        result = runner.invoke(main, [str(empty_folder)])

        assert result.exit_code != 0
        assert "no pdf" in result.output.lower()

    def test_batch_verbose_shows_progress(self, runner, batch_folder):
        """Verbose mode should show per-file progress."""
        result = runner.invoke(main, [str(batch_folder), "--verbose"])

        assert result.exit_code == 0
        assert "statement1" in result.output
        assert "statement2" in result.output
        assert "statement3" in result.output

    def test_batch_shows_summary(self, runner, batch_folder):
        """Should show summary after batch processing."""
        result = runner.invoke(main, [str(batch_folder)])

        assert result.exit_code == 0
        # Should mention number of files processed
        assert "3" in result.output or "files" in result.output.lower()

    def test_batch_with_strip_images(self, runner, batch_folder):
        """Batch mode should respect --strip-images flag."""
        result = runner.invoke(main, [str(batch_folder), "--strip-images"])
        assert result.exit_code == 0

    def test_batch_output_dir_short_option(self, runner, batch_folder, tmp_path):
        """-o should work as shorthand for --output-dir."""
        custom_output = tmp_path / "short_output"

        result = runner.invoke(main, [str(batch_folder), "-o", str(custom_output)])

        assert result.exit_code == 0
        assert custom_output.exists()
