"""Launch the optional analyst console from the project checkout."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analyst_console.server import main
if __name__=="__main__": main()
