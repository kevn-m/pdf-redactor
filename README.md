# PDF Redaction CLI

A command-line tool to securely redact PII (Personally Identifiable Information) from PDF documents using true redaction that removes text from the PDF structure.

## Features

- **True redaction** - Text is removed from PDF structure, not just visually obscured
- **Built-in patterns** - Australian PII patterns (BSB, TFN, phone numbers, etc.)
- **Custom patterns** - Define your own via YAML config or environment variables
- **Metadata stripping** - Removes PDF and XMP metadata by default
- **Secure output** - Saves with `garbage=4` to remove unreferenced objects

## Installation

Requires Python 3.10+

```bash
# Clone the repository
git clone <repository-url>
cd budgeting

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .
```

## Quick Start

```bash
# Redact a PDF with all built-in patterns
uv run redact statement.pdf

# Output: statement_redacted.pdf

# Specify output path (parent directories created automatically)
uv run redact statement.pdf redacted/clean.pdf

# Use specific patterns only
uv run redact statement.pdf -p email -p phone_au

# Verbose output
uv run redact statement.pdf -v
```

## Built-in Patterns

| Pattern | Description | Example Matches |
|---------|-------------|-----------------|
| `account_number` | Bank account numbers (6-12 digits) | `123456789` |
| `card_number` | Credit/debit card numbers | `1234-5678-9012-3456` |
| `bsb` | BSB numbers | `123-456`, `123456` |
| `tfn` | Tax File Numbers | `123 456 789`, `123456789` |
| `email` | Email addresses | `user@example.com` |
| `phone_au` | Australian phone numbers | `0412 345 678`, `+61 412 345 678` |

List all patterns:
```bash
uv run redact --list-patterns
```

## CLI Options

```
Usage: redact [OPTIONS] INPUT_FILE [OUTPUT_FILE]

Options:
  -p, --pattern TEXT     Use specific built-in pattern (repeatable)
  -c, --config PATH      Load patterns from YAML config file
  -a, --all-patterns     Use all built-in patterns (default if none specified)
  -I, --strip-images     Remove all images (barcodes, logos, etc.)
  -M, --no-metadata      Skip metadata stripping
  -v, --verbose          Show detailed output
  -q, --quiet            Suppress non-error output
  -l, --list-patterns    List available patterns and exit
  --version              Show version and exit
  --help                 Show this message and exit
```

## Custom Patterns

### Environment Variables

Set `REDACT_*` environment variables for personal PII:

```bash
# .env file
REDACT_FULL_NAME=John Smith
REDACT_ADDRESS=123 Main St, Sydney NSW 2000
REDACT_ACCOUNT=987654321
```

Copy the example file:
```bash
cp .env.example .env
# Edit .env with your details
```

### YAML Configuration

Create a YAML config file for custom patterns:

```yaml
# patterns.yaml
patterns:
  full_name:
    regex: "${REDACT_FULL_NAME}"
    description: "Account holder name"

  reference_code:
    regex: "REF-\\d{5}-[A-Z]{3}"
    description: "Reference codes"

  custom_id:
    regex: "ID[0-9]{8}"
    description: "Custom ID format"
    enabled: true
```

Use with:
```bash
uv run redact statement.pdf -c patterns.yaml
```

Environment variables in YAML are expanded using `${VAR}` syntax.

## Examples

### Basic Usage

```bash
# Redact with all patterns (default)
uv run redact bank-statement.pdf

# Redact emails only
uv run redact document.pdf -p email

# Redact multiple specific patterns
uv run redact document.pdf -p email -p phone_au -p account_number
```

### With Custom Config

```bash
# Use custom patterns from YAML
uv run redact statement.pdf -c my-patterns.yaml

# Combine built-in and custom patterns
uv run redact statement.pdf -p email -c my-patterns.yaml
```

### Output Options

```bash
# Custom output path
uv run redact input.pdf output/redacted.pdf

# Verbose mode (shows redaction details)
uv run redact statement.pdf -v

# Quiet mode (errors only)
uv run redact statement.pdf -q

# Keep metadata (don't strip)
uv run redact statement.pdf --no-metadata

# Remove all images (barcodes, logos, QR codes)
uv run redact statement.pdf --strip-images
```

## Security Notes

1. **True redaction**: This tool uses PyMuPDF's `add_redact_annot()` + `apply_redactions()` which actually removes text from the PDF structure, not just draws black boxes over it.

2. **Garbage collection**: Output is saved with `garbage=4` which removes unreferenced objects from the PDF, ensuring redacted text cannot be recovered.

3. **Metadata stripping**: PDF and XMP metadata (author, title, creation date, etc.) are stripped by default. Use `--no-metadata` to preserve.

4. **Verify redactions**: After redacting, open the PDF and try to select/copy text from redacted areas. You should not be able to select any text.

5. **Image stripping**: Bank statements often contain barcodes that encode account numbers and other PII. Use `--strip-images` to remove all images including barcodes, logos, and QR codes.

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=redact

# Type checking (if configured)
uv run mypy src/redact
```

## Project Structure

```
src/redact/
├── __init__.py     # Package version
├── cli.py          # Click CLI interface
├── redactor.py     # Core redaction logic
├── patterns.py     # Pattern definitions and loading
├── metadata.py     # PDF metadata stripping
└── secrets.py      # Environment variable handling

config/
└── patterns.yaml   # Default config template

tests/
├── conftest.py         # Shared test fixtures
├── test_cli.py         # CLI tests
├── test_redactor.py    # Redactor tests
├── test_patterns.py    # Pattern tests
├── test_metadata.py    # Metadata tests
├── test_secrets.py     # Secrets tests
└── test_integration.py # End-to-end tests
```

## Limitations

- **Text-based PDFs only**: Does not support OCR for scanned documents (planned for future)
- **Password-protected PDFs**: Not currently supported (planned for future)
- **Single file processing**: Batch processing not yet implemented

## License

MIT
