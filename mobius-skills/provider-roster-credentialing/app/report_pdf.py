"""
Convert Provider Roster Credentialing report (markdown + images) to PDF.
Uses markdown -> HTML -> weasyprint. Requires: markdown, weasyprint.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Minimal CSS for clean PDF
PDF_CSS = """
@page { margin: 1.5cm; size: Letter; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 11pt;
  line-height: 1.5;
  color: #1a1d21;
}
h1 { font-size: 20pt; margin-top: 0; }
h2 { font-size: 14pt; margin-top: 1.2em; }
h3 { font-size: 12pt; margin-top: 1em; }
table { border-collapse: collapse; margin: 0.8em 0; font-size: 10pt; }
th, td { border: 1px solid #e2e8f0; padding: 6px 10px; text-align: left; }
th { background: #f8fafc; font-weight: 600; }
img { max-width: 100%; height: auto; }
p { margin: 0.5em 0; }
ul { margin: 0.5em 0; padding-left: 1.5em; }
li { margin: 0.25em 0; }
"""


def markdown_to_pdf(
    md_path: Path,
    pdf_path: Path,
    *,
    css: str | None = None,
) -> bool:
    """
    Convert markdown file (with relative image paths) to PDF.

    Args:
        md_path: Path to .md file
        pdf_path: Output .pdf path
        css: Optional custom CSS string. If None, uses default PDF_CSS.

    Returns:
        True if successful.
    """
    try:
        import markdown
        from weasyprint import HTML, CSS
    except ImportError as e:
        logger.warning("markdown or weasyprint not installed; PDF generation skipped: %s", e)
        return False

    md_path = Path(md_path)
    pdf_path = Path(pdf_path)
    if not md_path.exists():
        logger.warning("Markdown file not found: %s", md_path)
        return False

    md_text = md_path.read_text(encoding="utf-8")
    html_content = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code"],
        extension_configs={"tables": {}},
    )

    # Wrap in HTML document
    full_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body>{html_content}</body></html>"""

    # base_url = directory containing the md file, so relative img paths resolve
    base_url = str(md_path.parent.resolve().as_uri()) + "/"

    try:
        html = HTML(string=full_html, base_url=base_url)
        styles = [CSS(string=css or PDF_CSS)]
        html.write_pdf(pdf_path, stylesheets=styles)
        return True
    except Exception as e:
        logger.warning("PDF generation failed: %s", e)
        return False
