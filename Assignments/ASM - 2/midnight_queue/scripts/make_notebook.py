"""Build the executed-walkthrough notebook used in the submission.

The notebook is deliberately cheap: it loads the real file once, demonstrates
the comparator and correctness on a 1,000-record sample, runs Top-K on a
10,000-record sample, and then reads the frozen benchmark CSVs for the report
numbers.  It never reruns the tournament.
"""

from __future__ import annotations

import nbformat as nbf
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "23I-2581-A2-DS-B.ipynb"

nb = nbf.v4.new_notebook()
nb.metadata = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3.14"},
}

cells = []


def md(text: str) -> None:
    cells.append(nbf.v4.new_markdown_cell(text.strip()))


def code(text: str) -> None:
    cells.append(nbf.v4.new_code_cell(text.strip()))


md(
    r"""
# The Midnight Queue — 23I-2581 — DS-B

**Design and Analysis of Algorithms — Assignment 2**

| Parameter | Value |
|---|---|
| Roll (display) | 23I-2581 |
| Seed | 232581 |
| Section | DS-B |
| Shift capacity | $K = 25 + (232581 \bmod 226) = 52$ |
| Sizes | 1,000 · 10,000 · 100,000 · 284,807 |
| Dataset | Kaggle `mlg-ulb/creditcardfraud` (`creditcard.csv`, not redistributed) |

This notebook is a **walkthrough**, not the benchmark harness.  It loads the
real file, demonstrates the risk score, the four-field comparator and the
custom contenders on small samples, then reads the frozen five-run medians in
`outputs/raw/` and `results.csv`.  The complete tournament takes tens of
minutes and is reproduced with the commands in `README.md`; rerunning it here
would only duplicate measurements.

**What is live in this notebook:** the dataset checksum/profile, a 1,000-record
sorting check, a 10,000-record Top-K check, and the fraud-capture table.
**What is read from disk:** every tournament, Top-K, live-feed and memory
number.  Those are the numbers printed in the report.

> **AI-use disclosure.** I used OpenCode with a DeepSeek V4.1 Flash model to
> help implement the package, write and run tests, orchestrate measurements,
> analyse outputs and draft the report.  I ran the code, checked the
> correctness tests and raw CSVs, and I can explain and modify every algorithm
> and every number reported here.
"""
)

md(
    r"""
## 0. Setup and personal parameters

`src/` is added to `sys.path` so the notebook runs from a plain checkout
without installation.  The `CONFIG` object validates that the roll digits,
seed and $K$ are mutually consistent.
"""
)

code(
    r"""
from pathlib import Path
import json
import sys
import time

ROOT = Path.cwd()
if not (ROOT / "src").exists() and (ROOT.parent / "src").exists():
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
from IPython.display import Image, display

from midnight_queue.config import CONFIG
from midnight_queue.data import dataset_profile, load_dataset, sample_records
from midnight_queue.records import Counters, TriageOrder, triage_key
from midnight_queue.sorting import SORT_ALGORITHMS
from midnight_queue.topk import topk_buffer, topk_heap

print(f"roll={CONFIG.roll_display}  seed={CONFIG.seed}  section={CONFIG.section}")
print(f"K={CONFIG.k}  sizes={CONFIG.sizes}")
print(f"project root: {ROOT}")
"""
)

md(
    r"""
## A. Know your data

Risk is the sum of 28 squared population z-scores over `V1…V28`:

$$ r_i = \sum_{j=1}^{28} z_{ij}^2, \qquad
   b_i = \min(9,\max(0,\lfloor \log_2 r_i \rfloor)). $$

The score never reads `Amount`, `Time`, `txn_id` or `Class`.  Loading the full
file validates the schema, finite values, binary labels and ascending `Time`,
then computes the score for every row.  It takes roughly 10–20 seconds.
"""
)

code(
    r"""
data_path = ROOT / "data" / "creditcard.csv"
if not data_path.exists():
    raise FileNotFoundError(
        "Place creditcard.csv at data/creditcard.csv (see README.md)."
    )

started = time.perf_counter()
dataset = load_dataset(data_path)
profile = dataset_profile(dataset)
print(f"loaded {dataset.n:,} rows in {time.perf_counter() - started:.1f}s")
print(f"sha256 = {dataset.sha256}")
print(f"frauds = {dataset.fraud_count}")
assert dataset.n == 284_807 and dataset.fraud_count == 492
assert dataset.sha256 == "76274b691b16a6c49d3f159c883398e03ccd6d1ee12d9d8ee38f4b4b98551a89"
"""
)

code(
    r"""
def band_count(mapping, band):
    return mapping.get(band, mapping.get(str(band), 0))


band_rows = []
for band in range(10):
    band_rows.append(
        {
            "band": band,
            "transactions": band_count(profile["band_counts"], band),
            "frauds": band_count(profile["fraud_by_band"], band),
        }
    )
band_table = pd.DataFrame(band_rows)
band_table["share of row count"] = (
    band_table["transactions"] / dataset.n
).map(lambda v: f"{v:.2%}")
band_table
"""
)

code(
    r"""
print(f"distinct Amount values: {profile['distinct_amounts']:,}")
print(f"top-10 Amount share:    {profile['top10_amount_share']:.3%}")
print("top Amount values:")
for item in profile["top10_amounts"][:5]:
    print(f"  {item['amount']:>8.2f}  x{item['count']:,}")
"""
)

md(
    r"""
**Reading.**  Bands 0–1 are empty in this file; the top band (9) has only 862
transactions but 161 frauds.  Fraud is concentrated at high risk, yet the raw
file is sorted by `Time`, which is unrelated to the triage order.  That is why
a full sort is needed before taking the first $K$.

The four-field key is **band descending, Amount descending, Time ascending,
txn_id ascending**.  `Class` is evaluation-only.
"""
)

md(
    r"""
## Demo: build a 10,000-record C1 input and rank it

`sample_records` uses `numpy.random.default_rng(232581)`, samples without
replacement, then restores `(Time, txn_id)` order.  The result is condition C1
(arrival order) for that size.  The same records are shared by all conditions
in the real harness; C2 shuffles them and C3 ranks them, etc.
"""
)

code(
    r"""
records = sample_records(dataset.records, 10_000, CONFIG.seed)
print(f"sampled {len(records):,} records; first/last Time = "
      f"{records[0].time:.0f} / {records[-1].time:.0f}")
print(f"first five txn_ids: {[t.txn_id for t in records[:5]]}")

reference = sorted(records, key=triage_key)  # reference only, not a contender
preview = pd.DataFrame(
    [
        {
            "rank": i + 1,
            "txn_id": t.txn_id,
            "band": t.band,
            "Amount": round(t.amount, 2),
            "Time": round(t.time, 1),
            "risk": round(t.risk, 4),
            "Class": t.label,
        }
        for i, t in enumerate(reference[:10])
    ]
)
preview
"""
)

md(
    r"""
## B. Correctness and cost of the custom contenders

All five full-sort contenders implement the same interface.  A comparison is
one call to `TriageOrder.cmp`; a move is one record assignment (a swap counts
as three).  No built-in or NumPy sort appears inside any contender.

The check below uses **1,000 records**, not 10,000, so that quadratic
contenders finish quickly.  It verifies exact sequence equality and reports an
illustrative single run.  The report uses five-run medians from the frozen
harness; these numbers are not substituted for them.
"""
)

code(
    r"""
small = records[:1_000]
expected = sorted(small, key=triage_key)  # reference only

rows = []
for name, algorithm in SORT_ALGORITHMS.items():
    counters = Counters()
    order = TriageOrder("triage", counters)
    work = list(small)  # fresh input copy, outside the timer
    start = time.perf_counter()
    output = algorithm(work, order, counters)
    elapsed = time.perf_counter() - start
    rows.append(
        {
            "contender": name,
            "correct": output == expected,
            "elapsed_s": round(elapsed, 4),
            "comparisons": counters.comparisons,
            "moves": counters.moves,
        }
    )
pd.DataFrame(rows).sort_values("elapsed_s")
"""
)

md(
    r"""
## D. Top-K: full sort vs size-K heap vs bounded buffer

At $K=52$ the heap keeps only 52 candidates; the buffer maintains a sorted
52-record list and shifts on acceptance; the full sort orders all 10,000
records and takes a prefix.  All three must return the **same ordered queue**.
"""
)

code(
    r"""
k = CONFIG.k
check = records[:10_000]

def timed(make_output):
    counters = Counters()
    order = TriageOrder("triage", counters)
    start = time.perf_counter()
    output = make_output(order, counters)
    return time.perf_counter() - start, output, counters

work_full = list(check)
def full_queue(order,counters):
    SORT_ALGORITHMS["Hardened Quick Sort"](work_full,order,counters)
    output=work_full[:k]
    counters.moves+=len(output)
    return output
t_full, q_full, c_full = timed(full_queue)
t_heap, q_heap, c_heap = timed(lambda order, counters: topk_heap(check, k, order, counters))
t_buf, q_buf, c_buf = timed(lambda order, counters: topk_buffer(check, k, order, counters))

assert q_full == q_heap == q_buf
print(f"all three queues identical: {len(q_heap)} records")
pd.DataFrame(
    [
        {"method": "hardened sort + prefix", "elapsed_s": round(t_full, 4),
         "comparisons": c_full.comparisons, "moves": c_full.moves},
        {"method": "size-K heap", "elapsed_s": round(t_heap, 4),
         "comparisons": c_heap.comparisons, "moves": c_heap.moves},
        {"method": "bounded buffer", "elapsed_s": round(t_buf, 4),
         "comparisons": c_buf.comparisons, "moves": c_buf.moves},
    ]
)
"""
)

code(
    r"""
queue_preview = pd.DataFrame(
    [
        {"rank": i + 1, "txn_id": t.txn_id, "band": t.band,
         "Amount": round(t.amount, 2), "Time": t.time, "Class": t.label}
        for i, t in enumerate(q_heap[:10])
    ]
)
print(f"frauds in the whole 10,000 sample: {sum(t.label for t in check)}")
print(f"frauds in this K=52 queue: {sum(t.label for t in q_heap)}")
queue_preview
"""
)

md(
    r"""
## Fraud capture versus $K$

The curve is computed once on the full file by `scripts/analyze_data.py` and
read here from `outputs/analysis/fraud_curve.csv`.  It uses `Class` only after
the queue is built.
"""
)

code(
    r"""
curve = pd.read_csv(ROOT / "outputs" / "analysis" / "fraud_curve.csv")
required = [10, 50, 52, 500, 5000, 28480]
curve.set_index("k").loc[required].reset_index()
"""
)

code(
    r"""
half = curve[curve.fraction >= 0.5].iloc[0]
print(f"smallest K reaching 50% capture: {int(half.k):,} "
      f"({int(half.frauds_captured)}/{int(half.total_frauds)} frauds)")
print(f"K=52 captures {int(curve.loc[curve.k == 52, 'frauds_captured'].iloc[0])} frauds")
display(Image(filename=str(ROOT / "outputs" / "figures" / "08_fraud_capture.png"), width=620))
"""
)

md(
    r"""
## E. Live feed

The full 48-hour file is split into consecutive `Time` windows.  After every
window the committed queue is the top 52 of all records seen so far.
**A** re-ranks the whole prefix; **B** offers each new record to a maintained
size-52 heap; **C** sorts the new window and merges it into the current queue.
The table below is read from the five-run summaries in `outputs/raw/livefeed.csv`.
A strategy that exceeded the 300 s watchdog has no summary row; the DNF table
below it makes that explicit rather than showing a missing number.
"""
)

code(
    r"""
live_path = ROOT / "outputs" / "raw" / "livefeed.csv"
if live_path.exists():
    live = pd.read_csv(live_path)
    summaries = live[live.record_type == "summary"].copy()
    summaries["width"] = summaries["width_s"].map({3600: "1 hour", 600: "10 min"})
    display(
        summaries.pivot_table(
            index="width", columns="strategy", values="median_s", aggfunc="first"
        ).round(3)
    )
    dnf_live = live[(live.record_type == "dnf") & (live.experiment == "livefeed")]
    if len(dnf_live):
        display(dnf_live[["strategy", "width_s", "dnf_reason"]])
else:
    print("livefeed.csv is not present; run scripts/run_livefeed.py --memory")
"""
)

md(
    r"""
## C. The measured tournament (read from disk)

Every cell is the median of five completed runs.  `DNF` means a genuine
300-second timeout; it is never given a time or a median.  The table shows the
report's representative slice at $n=10{,}000$.
"""
)

code(
    r"""
tour = pd.read_csv(ROOT / "outputs" / "raw" / "tournament.csv")
med = tour[tour.record_type == "median"].copy()
for col in ("n", "median_s", "comparisons", "moves"):
    med[col] = pd.to_numeric(med[col], errors="coerce")

slice_10k = med[med.n == 10_000].pivot_table(
    index="algorithm", columns="condition", values="median_s", aggfunc="first"
)
slice_10k.round(4)
"""
)

code(
    r"""
dnf = tour[tour.record_type == "dnf"]
print(f"timed median cells: {len(med)}")
print(f"genuine DNF cells:  {len(dnf)}")
dnf[["algorithm", "condition", "n", "dnf_reason"]].sort_values(
    ["algorithm", "condition", "n"]
).reset_index(drop=True)
"""
)

md(
    r"""
## F. The mathematical case: M6 on C6

C6 is the assignment's literal **band-only** comparator.  It has huge ties, so
exact sequence equality with a total-order reference is impossible without
adding an illegal secondary key.  A literal C6 result is validated as a
permutation with non-increasing bands and with no access to Amount, Time,
txn_id or Class.  This is the disclosed specification clash recorded in
`docs/specification_and_decisions.md`.

For Naive Quick Sort (last-pivot Lomuto), a one-band block of size $m$ costs
$m(m-1)/2$ comparisons.  Grouping the actual band sizes gives the prediction
below; the 10,000 exact-sequence simulation is shown for comparison.
"""
)

code(
    r"""
analysis = json.loads(
    (ROOT / "outputs" / "analysis" / "data_analysis.json").read_text()
)
m6 = analysis["c6_band_analysis"]
rows = []
for n in ("1000", "10000", "100000", "284807"):
    item = m6[n]
    sub = med[(med.algorithm == "Naive Quick Sort") &
              (med.condition == "C6") & (med.n == int(n))]
    rows.append(
        {
            "n": int(n),
            "band sizes": ", ".join(str(v) for v in item["band_sizes"].values()),
            "group formula": item["predicted_comparisons_group_formula"],
            "exact element model": item["predicted_comparisons_exact_sequence"],
            "measured": int(sub.comparisons.iloc[0]) if len(sub) else "DNF",
        }
    )
pd.DataFrame(rows)
"""
)

md(
    r"""
## H. Recommendation

The recommendation is derived from the measured tables above and
from `results.csv`; see Section H of the PDF for the full argument, including
the assumptions under which each recommendation would fail.
"""
)

code(
    r"""
report = ROOT / "23I-2581-A2-DS-B.pdf"
results = ROOT / "results.csv"
print(f"report exists: {report.exists()}  ({report})")
print(f"results.csv exists: {results.exists()}  ({results})")
if results.exists():
    res = pd.read_csv(results)
    print(f"results rows: {len(res):,}")
    display(res.head(3))
"""
)

md(
    r"""
## Reproduction

From the project root, with `$env:PYTHONPATH = "src"`:

```powershell
python scripts/prepare.py
python -m pytest -q
python scripts/run_dnf.py
python scripts/run_tournament_parallel.py --workers 4
python scripts/measure_memory.py
python scripts/run_topk.py --extra-k 2068
python scripts/measure_topk_memory.py
python scripts/run_livefeed.py --memory
python scripts/analyze_data.py
python -m midnight_queue.plotting
python scripts/assemble_results.py
python scripts/build_submission.py
```

The dataset is **not** included in the submission archive.  Place
`creditcard.csv` under `data/` before running the notebook or the harness.
"""
)

nb.cells = cells
from polish_notebook import polish_notebook
nb = polish_notebook(nb)
nbf.write(nb, OUT)
print(f"wrote {OUT} with {len(nb.cells)} cells")
