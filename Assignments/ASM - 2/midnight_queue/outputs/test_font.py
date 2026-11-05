import matplotlib
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

arial = Path(r"C:\Windows\Fonts\arial.ttf")
dejavu = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans.ttf"
pdfmetrics.registerFont(TTFont("ArialTest", str(arial)))
pdfmetrics.registerFont(TTFont("DejaVuTest", str(dejavu)))
c = canvas.Canvas(str(Path(__file__).with_name("test_font.pdf")))
text = "Design and Analysis of Algorithms · Assignment 2 · Roll 23I-2581 · K = 52 — Θ(n log n) ≈ 2×"
c.setFont("ArialTest", 12)
c.drawString(40, 760, "ARIAL: " + text)
c.setFont("DejaVuTest", 12)
c.drawString(40, 730, "DEJAVU: " + text)
c.save()
print("wrote test_font.pdf")
