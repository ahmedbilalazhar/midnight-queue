"""Print the official specification for a local compliance review."""
from pathlib import Path
import sys
from pypdf import PdfReader

sys.stdout.reconfigure(encoding="utf-8")

root = Path(__file__).resolve().parents[1]
reader = PdfReader(root.parent / "The Midnight Queue - Assignment 2.pdf")
for number, page in enumerate(reader.pages, 1):
    print(f"\n--- PAGE {number} ---\n{page.extract_text()}")
