"""Screenshot -> text using Tesseract OCR (free, open source). English + Hindi."""
from __future__ import annotations

import io
import logging
import os
import shutil

from PIL import Image, ImageOps

log = logging.getLogger("scamshield.ocr")

# Windows installers usually don't add Tesseract to PATH, so also look in the default folders.
WINDOWS_PATHS = (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                 r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe")


def _find_tesseract() -> str | None:
    found = os.getenv("TESSERACT_CMD") or shutil.which("tesseract")
    if found:
        return found
    return next((p for p in WINDOWS_PATHS if os.path.exists(p)), None)


class OCRUnavailable(RuntimeError):
    pass


def image_to_text(data: bytes) -> str:
    try:
        import pytesseract
        cmd = _find_tesseract()
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
        pytesseract.get_tesseract_version()
    except Exception as exc:
        raise OCRUnavailable("Tesseract OCR is not installed on this server.") from exc

    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("L")  # grayscale improves accuracy
    if img.width < 1000:  # small screenshots: upscale so letters are readable
        scale = 1000 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    langs = "eng+hin"
    try:
        available = set(pytesseract.get_languages(config=""))
        langs = "+".join(l for l in ("eng", "hin") if l in available) or "eng"
    except Exception:
        langs = "eng"
    return pytesseract.image_to_string(img, lang=langs).strip()
