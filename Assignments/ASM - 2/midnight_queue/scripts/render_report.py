"""Render the final report for visual inspection and print its page sizes."""
from pathlib import Path
import pymupdf as fitz

root = Path(__file__).resolve().parents[1]
pdf = root / "outputs/latex/23I-2581-A2-DS-B.pdf"
output = root / "outputs/report_preview"
output.mkdir(parents=True,exist_ok=True)
doc = fitz.open(pdf)
for i,page in enumerate(doc,1):
    page.get_pixmap(matrix=fitz.Matrix(1.65,1.65),alpha=False).save(output/f"page_{i}.png")
    (output/f"page_{i}.txt").write_text(page.get_text(),encoding="utf-8")
print(f"Rendered {len(doc)} pages")
