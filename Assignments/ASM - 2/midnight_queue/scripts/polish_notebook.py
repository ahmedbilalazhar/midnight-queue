"""Apply the shared visual narrative to the reproducible notebook generator."""
from __future__ import annotations

import nbformat as nbf


SETUP = '''
from html import escape
from midnight_queue.visuals import main as build_figures

# Rebuild only visual assets from the recorded CSVs, never the benchmarks.
build_figures()
figure_dir = ROOT / "outputs" / "figures"
captions = json.loads((figure_dir / "captions.json").read_text(encoding="utf-8"))

def show_figure(name):
    """Embed a sharp PNG and its evidence-backed caption in this notebook."""
    display(Image(filename=str(figure_dir / name), width=1100))
    display(HTML('<p style="font:13px/1.6 sans-serif;color:#5b7080;'
                 'border-left:3px solid #008c95;padding:8px 14px;margin:0 0 24px">'
                 + escape(captions[name]) + '</p>'))

def style_table(frame):
    """Use one accessible table style without changing the underlying numbers."""
    return (frame.style.format(precision=4, na_rep="—")
            .set_table_styles([
                {"selector":"th", "props":[("background-color","#18364b"),
                  ("color","white"),("padding","10px 12px"),("text-align","left")]},
                {"selector":"td", "props":[("padding","9px 12px"),
                  ("border-bottom","1px solid #e3eaf0")]},
                {"selector":"tr:nth-child(even)", "props":[("background-color","#f4f8fb")]},
                {"selector":"table", "props":[("font-family","sans-serif"),
                  ("font-size","13px"),("border-collapse","collapse")]},
            ]))
'''

DISCLOSURE = '''> **AI-use disclosure.** The original project records assistance from OpenCode
> with DeepSeek V4.1 Flash for implementation, tests, experiment orchestration,
> analysis and drafting. OpenAI Codex helped revise the visualisation code,
> notebook presentation, compliance checks and editable LaTeX report in this
> revision, then hardened quicksort, corrected the C6 model and timing scopes,
> and reran affected experiments. Historical observations are archived;
> over-limit C5 insertion runs remain excluded under the 300-second rule.
> The student must verify
> the submission and be able to explain and modify the algorithms in the viva.'''


def polish_notebook(nb):
    """Add all required charts next to the section that explains their evidence."""
    import re
    # Keep the walkthrough in assignment order: B, C, D, E, F, H.
    c_start=next(i for i,c in enumerate(nb.cells) if c.cell_type=="markdown" and c.source.startswith("## C. The measured"))
    c_end=next(i for i in range(c_start+1,len(nb.cells)) if nb.cells[i].cell_type=="markdown" and nb.cells[i].source.startswith("## F."))
    tournament_cells=nb.cells[c_start:c_end]
    del nb.cells[c_start:c_end]
    d_start=next(i for i,c in enumerate(nb.cells) if c.cell_type=="markdown" and c.source.startswith("## D."))
    nb.cells[d_start:d_start]=tournament_cells
    first = nb.cells[0]
    first.source = re.sub(r"> \*\*AI-use disclosure\.\*\*.*", DISCLOSURE,
                          first.source, flags=re.S)
    first.source = first.source.replace(
        "# The Midnight Queue — 23I-2581 — DS-B",
        "# The Midnight Queue\n### Ranking suspicious transactions at scale · 23I-2581 · DS-B")
    card = nbf.v4.new_code_cell('''display(HTML("""
<div style="background:#18364b;color:white;padding:28px 32px;border-radius:12px;
            font-family:sans-serif;margin:12px 0 24px">
  <div style="color:#9dd6d5;font-size:12px;letter-spacing:2px">ALGORITHMS · EVIDENCE · DECISIONS</div>
  <div style="font-size:27px;font-weight:700;margin:10px 0 16px">The cost of finding the right queue</div>
  <div style="display:flex;gap:45px;flex-wrap:wrap">
    <div><b style="font-size:24px">284,807</b><br><span style="color:#cbd9e2">transactions</span></div>
    <div><b style="font-size:24px">52</b><br><span style="color:#cbd9e2">cases per shift</span></div>
    <div><b style="font-size:24px">2,068</b><br><span style="color:#cbd9e2">cases to capture 50% of frauds</span></div>
  </div>
</div>"""))''')
    insertions = {
        "## A.": [("07_band_distribution.png",)],
        "## C.": [("01_time_vs_n_C2.png", "02_time_by_condition_n10000.png"),
                     ("03_comparisons_vs_n_C2.png", "04_moves_vs_n_C2.png"),
                     ("05_time_nlogn_vs_n_C2.png", "06_time_n2_vs_n_C2.png")],
        "## D.": [("09_topk_cost.png",)],
        "## E.": [("10_livefeed_1h.png", "11_livefeed_10min.png")],
        "## H.": [("12_c5_inversions.png",)],
    }
    cells = []
    setup_done = False
    for cell in nb.cells:
        if cell.cell_type == "code":
            cell.source = cell.source.replace("from IPython.display import Image, display",
                                              "from IPython.display import Image, HTML, display")
            cell.source = cell.source.replace(
                'ROOT = Path.cwd()\nif not (ROOT / "src").exists() and (ROOT.parent / "src").exists():\n    ROOT = ROOT.parent',
                'ROOT = next((p for p in (Path.cwd(), *Path.cwd().parents)\n'
                '             if (p / "src" / "midnight_queue").is_dir()), None)\n'
                'if ROOT is None:\n    raise RuntimeError("Open this notebook from the midnight_queue project folder.")')
            cell.source = cell.source.replace(
                'pd.DataFrame(rows).sort_values("elapsed_s")',
                'assert all(row["correct"] for row in rows), "A sorting contender disagrees with the reference"\n'
                'style_table(pd.DataFrame(rows).sort_values("elapsed_s"))')
            cell.source = cell.source.replace("assert q_full == q_heap == q_buf",
                "assert q_full == q_heap == q_buf == sorted(check, key=triage_key)[:k]")
            cell.source = cell.source.replace('display(Image(filename=str(ROOT / "outputs" / "figures" / "08_fraud_capture.png"), width=620))',
                                              'show_figure("08_fraud_capture.png")')
            cell.source = cell.source.replace("slice_10k.round(4)", "style_table(slice_10k)")
            if cell.source.endswith("pd.DataFrame(rows)"):
                cell.source = cell.source[:-len("pd.DataFrame(rows)")] + "style_table(pd.DataFrame(rows))"
            if cell.source.splitlines()[-1] in ("preview", "queue_preview"):
                before, final = cell.source.rsplit("\n", 1)
                cell.source = before + f"\nstyle_table({final})"
        cells.append(cell)
        for prefix,groups in insertions.items():
            if cell.cell_type=="markdown" and cell.source.startswith(prefix):
                for names in groups:
                    for name in names:
                        cells.append(nbf.v4.new_code_cell(f'show_figure("{name}")'))
        if not setup_done and cell.cell_type == "code" and "sys.path.insert" in cell.source:
            cells.extend([nbf.v4.new_code_cell(SETUP.strip()),card])
            setup_done = True
    cells.append(nbf.v4.new_markdown_cell('''## Editable report and figure exports

The editable report is **23I-2581-A2-DS-B.tex** in the project root.
Its relative image paths point to **report/images/**; each chart is available
as a vector PDF and a high-resolution PNG. The complete figure collection also
includes SVG exports in **outputs/figures/**.

Part G is reserved for the demo and omitted from the report as requested.
The assignment's C6 tie conflict and the interpretation used are documented in
**docs/specification_and_decisions.md**. No missing requirement or timeout is hidden.'''))
    cells.append(nbf.v4.new_markdown_cell('''## Bonus analyst console and live preparation

From the project root, run **python scripts/run_console.py** and open
**http://127.0.0.1:8765**. Choose any required full sort or Top-K selector,
set K, and inspect every queued record through pagination. The interface
shows actual runtime, comparisons and moves, and verifies its output.
Single demonstrations stay separate from the report's five-run medians.

The corrected **viva_prep.md** explains invariants, M1-M8, current measurements
and hands-on practice. **docs/demo_runbook.md** explains how to demonstrate
the console and measure the actual Part G request when it arrives.
Part G remains reserved for the demo; viva marks require your live explanation
and code modification. Bonus credit is conditional on completing A-H.'''))
    nb.cells = cells
    return nb
