"""Server-side PDF export for stored HTML reports."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class PdfExportError(RuntimeError):
    """Raised when the server cannot render a PDF report."""


def render_pdf_from_html(html: str) -> bytes:
    """Render report HTML to PDF bytes with a headless Chrome/Chromium binary."""
    browser_path = _find_browser_path()
    if browser_path is None:
        raise PdfExportError("Chrome or Chromium is required to export PDF reports.")

    with tempfile.TemporaryDirectory(prefix="thermal-report-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        html_path = tmp_path / "report.html"
        pdf_path = tmp_path / "report.pdf"
        html_path.write_text(html, encoding="utf-8")

        command = [
            browser_path,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--print-to-pdf-no-header",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0 or not pdf_path.exists():
            details = (result.stderr or result.stdout).strip()
            raise PdfExportError(details or "PDF export failed.")
        return pdf_path.read_bytes()


def _find_browser_path() -> str | None:
    configured_path = os.environ.get("THERMAL_PDF_BROWSER_PATH")
    if configured_path:
        return configured_path

    for command in (
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
        "chrome",
    ):
        resolved = shutil.which(command)
        if resolved:
            return resolved

    mac_chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if mac_chrome.exists():
        return str(mac_chrome)

    return None
