from pathlib import Path

import nbformat
from nbclient import NotebookClient

root = Path(__file__).resolve().parents[1]
path = root / "23I-2581-A2-DS-B.ipynb"
nb = nbformat.read(path, as_version=4)
client = NotebookClient(
    nb,
    timeout=900,
    kernel_name="python3",
    resources={"metadata": {"path": str(root)}},
)
client.execute()
nbformat.write(nb, path)
print(f"executed {len(nb.cells)} cells")
