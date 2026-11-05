# Editable report and figures

The main LaTeX file is [23I-2581-A2-DS-B.tex](../23I-2581-A2-DS-B.tex).
All image paths are relative to that file and point to [images/](./images/).
Each figure has a vector PDF for sharp typesetting and a high-resolution PNG
for convenient insertion elsewhere. SVG copies are in
[outputs/figures/](../outputs/figures/).

Compile from the project root with Tectonic:

    tectonic 23I-2581-A2-DS-B.tex

On Overleaf, upload the main TeX file and this folder, preserving the
directory structure, and press **Recompile**. The default **pdfLaTeX**
compiler works without any settings. **XeLaTeX** and **LuaLaTeX** are also
supported: they use Arial when installed, with TeX Gyre Heros as a portable
fallback.

To reproduce all visuals, the executed notebook, the report and the ZIP from
the already-recorded measurements:

    python scripts/build_submission.py

This command needs the development dependencies and Tectonic, pdfLaTeX,
XeLaTeX or LuaLaTeX. It runs the tests, but does not repeat the expensive
benchmark tournament. Note that it regenerates a plain TeX export; the
hand-tuned Overleaf version is the file committed at the project root.

The report has five pages, including the complete prediction-log appendix.
Part G is reserved for the demo and omitted from this report as requested.
