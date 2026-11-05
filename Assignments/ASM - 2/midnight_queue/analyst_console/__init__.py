"""Optional local analyst interface; measured algorithm sources stay unchanged."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
