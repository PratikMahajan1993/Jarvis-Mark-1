"""Local document text for the casual lens. No model, no vision, no Hermes."""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

DRAWING_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",
        ".tif",
        ".tiff",
        ".bmp",
        ".dwg",
        ".dxf",
        ".dwf",
        ".step",
        ".stp",
        ".iges",
        ".igs",
    }
)
TEXT_EXTENSIONS = frozenset({".txt", ".md", ".markdown"})
ALLOWED_EXTENSIONS = TEXT_EXTENSIONS | {".pdf", ".docx"}
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MIN_PAGE_CHARS = 20

DRAWING_REFUSAL = (
    "This is an engineering drawing, or a PDF with no text layer. "
    "Drop it on the orb to open the drawing desk."
)


class ExtractError(Exception):
    def __init__(self, message: str, *, drawing: bool = False) -> None:
        super().__init__(message)
        self.drawing = drawing


def _extension(name: str) -> str:
    return Path(name or "").suffix.lower()


def extract_docx(path: Path) -> str:
    """WordprocessingML via the standard library, same idea as Hermes read_file."""
    try:
        with zipfile.ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise ExtractError(f"Could not read that Word file ({exc}).") from exc
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ExtractError("That Word file has no readable text.") from exc
    paragraphs: list[str] = []
    for para in root.iter(f"{_W_NS}p"):
        line = "".join(node.text or "" for node in para.iter(f"{_W_NS}t")).strip()
        if line:
            paragraphs.append(line)
    text = "\n".join(paragraphs).strip()
    if not text:
        raise ExtractError("That Word file has no readable text.")
    return text


def _pdf_pages_pdftotext(path: Path) -> list[str] | None:
    if shutil.which("pdftotext") is None:
        return None
    try:
        proc = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", str(path), "-"],
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    text = proc.stdout.decode("utf-8", errors="replace")
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def _pdf_via_anydoc(path: Path) -> str:
    try:
        import anydoc
    except ImportError as exc:
        raise ExtractError(
            "No local PDF converter is available (pdftotext or anydoc)."
        ) from exc
    try:
        text = anydoc.to_markdown(str(path))
    except Exception as exc:
        name = type(exc).__name__
        if name == "NeedsOcrError":
            raise ExtractError(DRAWING_REFUSAL, drawing=True) from exc
        raise ExtractError(f"Could not read that PDF ({name}).") from exc
    rendered = str(text or "")
    if "NEEDS OCR" in rendered or not rendered.strip():
        raise ExtractError(DRAWING_REFUSAL, drawing=True)
    return rendered.strip()


def extract_pdf(path: Path) -> str:
    pages = _pdf_pages_pdftotext(path)
    if pages is not None:
        if not any(len(page.strip()) >= _MIN_PAGE_CHARS for page in pages):
            raise ExtractError(DRAWING_REFUSAL, drawing=True)
        return "\n".join(page.strip() for page in pages if page.strip()).strip()
    return _pdf_via_anydoc(path)


def extract_local_text(path: Path, filename: str = "") -> str:
    """Convert one upload. Raises ExtractError for drawings and empty PDFs."""
    ext = _extension(filename or path.name)
    if ext in DRAWING_EXTENSIONS:
        raise ExtractError(DRAWING_REFUSAL, drawing=True)
    if ext not in ALLOWED_EXTENSIONS:
        raise ExtractError("Casual upload accepts pdf, docx, txt, and markdown.")
    if ext in TEXT_EXTENSIONS:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ExtractError(f"Could not read that file ({exc}).") from exc
        if "\x00" in text:
            raise ExtractError(DRAWING_REFUSAL, drawing=True)
        stripped = text.strip()
        if not stripped:
            raise ExtractError("That file has no text.")
        return stripped
    if ext == ".docx":
        return extract_docx(path)
    if ext == ".pdf":
        return extract_pdf(path)
    raise ExtractError("Casual upload accepts pdf, docx, txt, and markdown.")
