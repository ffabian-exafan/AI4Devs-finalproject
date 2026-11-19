"""Tamaños de PDF en uploads. Sin nombres."""

from app.config import get_settings
from pathlib import Path

raiz = Path(get_settings().uploads_dir)
print("existe", raiz.is_dir())
if raiz.is_dir():
    for pdf in raiz.rglob("*.pdf"):
        print(pdf.parent.parent.name, pdf.parent.name, pdf.stat().st_size)
