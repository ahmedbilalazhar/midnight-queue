"""Rebuild visual deliverables without rerunning expensive benchmarks.

Install Tectonic or XeLaTeX separately; this script never downloads executables.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
STEM = "23I-2581-A2-DS-B"


def run(*args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.run(list(map(str,args)),cwd=ROOT,env=env,check=True)


def package():
    """Allow-list deliverables; private data, tools and scratch files stay out."""
    included = [
        ROOT / "src", ROOT / "tests", ROOT / "scripts", ROOT / "docs", ROOT / "analyst_console",
        ROOT / "report", ROOT / "outputs/raw", ROOT / "outputs/analysis",
        ROOT / "outputs/figures", ROOT / "outputs/audit", ROOT / "outputs/revision", ROOT / "outputs/demo",
    ]
    files = []
    for folder in included:
        files.extend(p for p in folder.rglob("*") if p.is_file()
                     and "__pycache__" not in p.parts
                     and p.suffix not in {".bak",".pyc"}
                     and p.stem != "legend_zoom")
    for name in ("README.md","viva_prep.md","requirements.txt","pyproject.toml","results.csv",
                 "prediction_log.csv",f"{STEM}.ipynb",f"{STEM}.tex",f"{STEM}.pdf",
                 "outputs/profile.json","outputs/environment.json",
                 "outputs/submission_validation.json","outputs/test_results.xml"):
        files.append(ROOT / name)
    archive = ROOT / f"{STEM}.zip"
    with ZipFile(archive,"w",ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(set(files)):
            z.write(path,path.relative_to(ROOT).as_posix())
    with ZipFile(archive) as z:
        assert z.testzip() is None
        assert not any("creditcard.csv" in n.lower() or n.startswith("data/") for n in z.namelist())
        assert f"{STEM}.tex" in z.namelist()
    print(f"Created verified submission archive: {archive}")


def execute_notebook():
    """Execute with this builder's interpreter using a temporary kernel spec."""
    import json
    import nbformat
    from nbclient import NotebookClient
    from jupyter_client import KernelManager
    from jupyter_client.kernelspec import KernelSpecManager
    from tempfile import TemporaryDirectory
    path = ROOT / f"{STEM}.ipynb"
    nb = nbformat.read(path,as_version=4)
    with TemporaryDirectory(prefix="midnight-kernel-") as temp:
        kernel = Path(temp) / "midnight-build"
        kernel.mkdir()
        (kernel / "kernel.json").write_text(json.dumps({
            "argv":[sys.executable,"-m","ipykernel_launcher","-f","{connection_file}"],
            "display_name":"Midnight build","language":"python"}))

        class BuildKernelManager(KernelManager):
            def __init__(self,**kwargs):
                super().__init__(kernel_spec_manager=KernelSpecManager(kernel_dirs=[temp]),**kwargs)

        NotebookClient(nb,timeout=900,kernel_name="midnight-build",
                       kernel_manager_class=BuildKernelManager,
                       resources={"metadata":{"path":str(ROOT)}}).execute()
    nbformat.write(nb,path)
    print(f"Executed {len(nb.cells)} notebook cells")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-notebook",action="store_true")
    args = parser.parse_args()
    run(sys.executable,"-m","pytest","-q","--junitxml=outputs/test_results.xml")
    run(sys.executable,"scripts/correct_timeout_classification.py")
    run(sys.executable,"scripts/refresh_prediction_outcomes.py")
    run(sys.executable,"scripts/assemble_results.py")
    run(sys.executable,"scripts/build_viva_guide.py")
    run(sys.executable,"-m","midnight_queue.visuals")
    if not args.skip_notebook:
        run(sys.executable,"scripts/make_notebook.py")
        execute_notebook()
    run(sys.executable,"scripts/build_latex_report.py")
    destination = ROOT / "outputs/latex"
    destination.mkdir(parents=True,exist_ok=True)
    local = ROOT / "outputs/tools/tectonic/tectonic.exe"
    compiler = shutil.which("tectonic") or (str(local) if local.exists() else None)
    if compiler:
        run(compiler,f"{STEM}.tex","--outdir",destination,"--keep-logs")
    elif shutil.which("xelatex"):
        for _ in range(2):
            run("xelatex","-interaction=nonstopmode","-halt-on-error",
                f"-output-directory={destination}",f"{STEM}.tex")
    else:
        raise SystemExit("TeX and images are ready. Install Tectonic or XeLaTeX to compile the PDF.")
    shutil.copy2(destination/f"{STEM}.pdf",ROOT/f"{STEM}.pdf")
    run(sys.executable,"scripts/validate_submission.py")
    package()


if __name__ == "__main__":
    main()
