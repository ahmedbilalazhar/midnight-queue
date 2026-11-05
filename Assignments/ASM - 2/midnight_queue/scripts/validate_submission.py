"""Audit recorded experiment coverage and generated submission artifacts."""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
import sys
import re
import xml.etree.ElementTree as ET

import nbformat
import numpy as np
import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "src"))
from midnight_queue.config import CONFIG
from midnight_queue.sorting import SORT_ALGORITHMS
from midnight_queue.visuals import METHODS
from midnight_queue.data import EXPECTED_SHA256


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def audit():
    tour = pd.read_csv(ROOT / "outputs/raw/tournament.csv")
    med = tour.loc[tour.record_type.eq("median")]
    dnf = tour.loc[tour.record_type.eq("dnf")]
    expected = set(itertools.product(SORT_ALGORITHMS,[f"C{i}" for i in range(1,7)],CONFIG.sizes))
    keys = ["algorithm","condition","n"]
    measured = set(med[keys].itertuples(index=False,name=None))
    timed_out = set(dnf[keys].itertuples(index=False,name=None))
    require(measured.isdisjoint(timed_out),"A tournament cell is both measured and DNF")
    require(measured | timed_out == expected,"Tournament does not cover all 120 cells")
    require(not med.duplicated(keys).any(),"Duplicate tournament median")
    require(dnf.elapsed_s.isna().all() and dnf.median_s.isna().all(),"DNF has an invented time")
    for row in med.itertuples():
        runs = tour.loc[tour.record_type.eq("run") & tour.algorithm.eq(row.algorithm)
                        & tour.condition.eq(row.condition) & tour.n.eq(row.n)]
        require(len(runs)==5,f"Expected five runs for {row.algorithm}/{row.condition}/{row.n}")
        check_runs(runs,row)
        require(runs.correct.astype(str).str.lower().eq("true").all(),"A recorded run failed correctness")
        require(runs.comparisons.nunique()==1 and runs.moves.nunique()==1,
                "Logical counts vary across identical runs")
        require(int(row.comparisons)==int(runs.comparisons.iloc[0]) and int(row.moves)==int(runs.moves.iloc[0]),
                "Median logical counts disagree with runs")
    memory=tour.loc[tour.record_type.eq("memory")&tour.n.eq(10000)]
    require(len(memory)==30 and not memory.duplicated(["algorithm","condition"]).any(),
            "Expected separate n=10,000 memory observations for all 30 algorithm/condition pairs")
    require(memory.peak_extra_bytes.ge(0).all(),"Invalid memory peak")
    top = pd.read_csv(ROOT / "outputs/raw/topk.csv")
    topmed = top.loc[top.record_type.eq("median")]
    for n,condition in itertools.product((100000,284807),("C1","C2")):
        for k,method in itertools.product((10,50,CONFIG.k,500,2068,5000,n//10),METHODS):
            cell = topmed.loc[topmed.n.eq(n) & topmed.condition.eq(condition)
                              & topmed.k.eq(k) & topmed.algorithm.eq(method)]
            require(len(cell)==1, f"Missing or duplicate Top-K cell: {n}/{condition}/{k}/{method}")
            require(int(cell.run_count.iloc[0])==5,"Top-K median does not represent five runs")
            runs=top.loc[top.record_type.eq("run")&top.n.eq(n)&top.condition.eq(condition)
                         &top.k.eq(k)&top.algorithm.eq(method)]
            check_runs(runs,cell.iloc[0])
    live = pd.read_csv(ROOT / "outputs/raw/livefeed.csv")
    for width,strategy in itertools.product((3600,600),("rerank","heap","merge")):
        cell = live.loc[live.width_s.eq(width)&live.strategy.eq(strategy)]
        summaries = cell.loc[cell.record_type.eq("summary")]
        timeouts = cell.loc[cell.record_type.eq("dnf")]
        require((len(summaries)==1) != (len(timeouts)==1),"Live strategy needs one summary or DNF")
        if len(summaries):
            runs = cell.loc[cell.record_type.eq("run")]
            totals = runs.groupby("repeat").elapsed_s.sum()
            require(len(totals)==5,"Live feed does not contain five repetitions")
            require(int(summaries.run_count.iloc[0])==5,"Live summary lacks five runs")
            recorded=cell.loc[cell.record_type.eq("run_total")].sort_values("repeat")
            require(len(recorded)==5 and set(recorded.repeat)=={1,2,3,4,5},
                    "Each completed live strategy needs five independently recorded totals")
            require(np.allclose(recorded.elapsed_s,totals.sort_index(),rtol=1e-10,atol=1e-10),
                    "Live totals disagree with the sum of algorithm-only windows")
            require(np.isclose(float(summaries.median_s.iloc[0]),np.median(totals),rtol=1e-10),
                    "Live median disagrees with its five raw totals")
            require(recorded.elapsed_s.between(0,300,inclusive="right").all(),"Invalid live total or missed deadline")
            require(cell.record_type.eq("memory").sum()==1,"Live strategy lacks separate memory measurement")
            for _,repeat in runs.groupby("repeat"):
                ordered = repeat.sort_values("window")
                count=48 if width==3600 else 288
                require(len(ordered)==count and set(ordered.window)==set(range(1,count+1)),
                        "Missing or duplicate live publication")
                require(ordered.correct.astype(str).str.lower().eq("true").all(),"Incorrect live publication")
                require(ordered.seen.iloc[-1]==284807,"Live simulation omitted records")
                require(np.allclose(ordered.elapsed_s.cumsum(),ordered.cumulative_s),
                        "Live cumulative curve disagrees with per-window timers")
    pred = pd.read_csv(ROOT / "prediction_log.csv")
    require(pred.prediction_id.nunique()==len(pred)==55,"Prediction log must preserve its 55 original rows")
    require(pred.rationale.notna().all(),"A prediction lacks a rationale")
    historical=pd.read_csv(ROOT/"outputs/audit/before_deep_hardening/prediction_log.csv").fillna("")
    immutable=["prediction_id","predicted_fastest","predicted_slowest","rationale","created_utc"]
    require(pred.fillna("")[immutable].equals(historical[immutable]),"An original forecast was changed after measurement")
    profile=json.loads((ROOT/"outputs/profile.json").read_text())
    require(profile["rows"]==284807 and profile["fraud_count"]==492,"Incorrect dataset dimensions")
    require(profile["sha256"]==EXPECTED_SHA256,"Dataset identity differs from the official file")
    analysis=json.loads((ROOT/"outputs/analysis/data_analysis.json").read_text())
    for n in (1000,10000):
        actual=med.loc[med.algorithm.eq("Naive Quick Sort")&med.condition.eq("C6")&med.n.eq(n)].comparisons.iloc[0]
        require(int(actual)==analysis["c6_band_analysis"][str(n)]["predicted_comparisons_exact_sequence"],
                "C6 exact element model does not match the recorded algorithm")
    notebook = nbformat.read(ROOT / f"{CONFIG.submission_stem}.ipynb",as_version=4)
    nbformat.validate(notebook)
    code = [c for c in notebook.cells if c.cell_type=="code"]
    require(all(c.execution_count is not None for c in code),"Notebook contains unexecuted cells")
    require(not any(o.output_type=="error" for c in code for o in c.outputs),"Notebook has an execution error")
    captions = json.loads((ROOT / "outputs/figures/captions.json").read_text())
    require(len(captions)==15,"Expected 12 detailed figures and three report composites")
    for name in captions:
        for extension in ("png","pdf","svg"):
            file = ROOT / "outputs/figures" / Path(name).with_suffix(f".{extension}")
            require(file.is_file() and file.stat().st_size>1000,f"Missing figure export: {file.name}")
    tex = ROOT / f"{CONFIG.submission_stem}.tex"
    require(tex.is_file(),"Editable TeX source is missing")
    for relative in re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}",tex.read_text(encoding="utf-8")):
        require((ROOT/relative).is_file(),f"Missing portable report image: {relative}")
    pdf = ROOT / f"{CONFIG.submission_stem}.pdf"
    report=PdfReader(pdf)
    pages = len(report.pages)
    require(pages<=5,f"Report exceeds the five-page limit: {pages}")
    report_text="\n".join(p.extract_text() for p in report.pages)
    require("G. Change Request" not in report_text and "pending section" not in report_text,
            "Part G must be omitted from this report as requested")
    require("Bonus: Analyst console" in report_text,"Required bonus console description is missing")
    for name in ("analyst_console/index.html","analyst_console/engine.py","analyst_console/worker.py",
                 "scripts/run_console.py","scripts/demo_round.py","viva_prep.md","docs/assessment_readiness.md"):
        require((ROOT/name).is_file(),f"Missing demo/viva deliverable: {name}")
    console_path=ROOT/"outputs/raw/console.csv"
    if console_path.exists():
        console=pd.read_csv(console_path)
        require(console.record_type.eq("console_run").all(),"Console runs must remain separate from benchmark medians")
        require(console.correct.astype(str).str.lower().eq("true").all(),"A recorded console result failed verification")
        require(console.elapsed_s.between(0,300,inclusive="right").all(),"Invalid console timing")
        require(console.k.ge(1).all() and console.k.le(console.n).all(),"Invalid console capacity")
    junit=ET.parse(ROOT/"outputs/test_results.xml")
    suites=list(junit.getroot().iter("testsuite"))
    require(not any(int(s.get("failures",0))+int(s.get("errors",0)) for s in suites),"Tests failed")
    result = {
        "tournament_cells":len(expected), "completed_medians":len(med),
        "genuine_tournament_dnfs":len(dnf), "topk_required_grid":"complete",
        "live_schedules":2, "prediction_rows":len(pred), "executed_code_cells":len(code),
        "figures":len(captions), "figure_formats":["PNG","PDF","SVG"], "report_pages":pages,
        "automated_tests":sum(int(s.get("tests",0)) for s in suites),
        "bonus_console":"implemented and tested; demonstrate live; credit conditional on A-H completion",
        "viva":"study materials prepared; live performance remains unassessed",
        "part_g":"reserved for the demo; omitted from report at the user's request",
        "results_sha256":hashlib.sha256((ROOT/"results.csv").read_bytes()).hexdigest(),
        "limitations":["C6 band-only ties conflict with the total-order equality requirement; interpretation is disclosed.",
                       "Historical DNF evidence for unchanged quadratic contenders is retained.",
                       "Unchanged Top-K heap/buffer loops retain earlier measurements; revised full sort is freshly measured at every K.",
                       "Concurrent tournament times include scheduling/cache contention and must not be compared directly with serial D/E times."],
    }
    output = ROOT / "outputs/submission_validation.json"
    output.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))


def check_runs(runs,row):
    require(len(runs)==5 and set(runs.repeat)=={1,2,3,4,5},"Missing or duplicated repeat identifier")
    require(np.isfinite(runs.elapsed_s).all() and runs.elapsed_s.between(0,300,inclusive="right").all(),
            "Nonpositive, nonfinite or over-limit completed measurement")
    require(np.isclose(runs.elapsed_s.median(),row.median_s,rtol=1e-10),"Median disagrees with five raw runs")
    require(runs.correct.astype(str).str.lower().eq("true").all(),"Incorrect recorded output")
    require(runs.comparisons.nunique()==runs.moves.nunique()==1,"Nondeterministic logical counts")


if __name__ == "__main__":
    audit()
