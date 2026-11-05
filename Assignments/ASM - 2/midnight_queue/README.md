# The Midnight Queue — 23I-2581 (DS-B)

Custom comparison sorts and Top-K selectors for the FAST-NUCES *Design and Analysis
of Algorithms* Assignment 2. The project uses the Kaggle ULB credit-card fraud
file only as an input dataset; the dataset is **not** included in the
submission.

## Polished notebook and editable report

The notebook includes all 12 detailed, captioned figures with a consistent
visual theme, styled tables and executable correctness assertions. Figures
are exported as PNG, vector PDF and SVG.

The editable LaTeX source is [23I-2581-A2-DS-B.tex](./23I-2581-A2-DS-B.tex);
its images are in [report/images/](./report/images/). See
[report/README.md](./report/README.md) for Tectonic and Overleaf instructions.
The compiled PDF stays within the five-page assignment limit.

Rebuild the visual deliverables and submission archive from the saved results:

    python scripts/build_submission.py

The deeper audit added an introspective heap fallback to hardened quicksort,
enforced dataset identity and shared counters, corrected the C6 model, and
unified live timing scopes. Affected experiments were remeasured; original
sources and measurements remain archived. See the [detailed audit](./docs/deep_audit.md)
and [compliance review](./docs/compliance_review.md). Part G is reserved for the
demo and omitted from the report as requested.

## Personal parameters

| Item | Value |
|---|---|
| Roll (display) | 23I-2581 |
| Roll digits / seed | 232581 |
| Section | DS-B |
| Shift capacity | `K = 25 + (232581 mod 226) = 52` |
| Sizes | 1,000; 10,000; 100,000; 284,807 |
| Conditions | C1–C6 as defined in the assignment |

Risk is `sum(z_i^2)` for population-standardised `V1…V28`; band is
`min(9, max(0, floor(log2(risk))))`. The triage key is **band descending,
Amount descending, Time ascending, txn_id ascending**. `Class` is read only
after a queue is built, for evaluation.

## Dataset

Download `creditcard.csv` from
<https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud> and place it at:

```text
data/creditcard.csv
```

Expected file checksum:

```text
SHA-256 76274b691b16a6c49d3f159c883398e03ccd6d1ee12d9d8ee38f4b4b98551a89
284,807 rows; 492 frauds
```

The loader enforces this checksum, row/fraud totals, columns, finite values, binary labels, and ascending
`Time`, but never imputes or drops rows. A Kaggle account is required to
download the file; the repository deliberately does not vendor it.

## Analyst console and viva

Launch the optional local interface from the project root:

~~~powershell
`python scripts/run_console.py`
~~~

Open http://127.0.0.1:8765. Select any required full-sort or Top-K algorithm,
set K, and inspect all queue records through pagination. Runtime, comparisons,
moves and independent verification are shown. Full-file scoring precedes sampling.
The dark dashboard includes a wireframe band profile, actual queue rank-flow
traces, recorded benchmark evidence, transaction inspection, ID/band filters,
and CSV queue export. All profile figures and recommendations use saved project
evidence; the interface does not invent AI predictions, channels or locations.
Cancel stops the active worker. Individual demonstrations are recorded in
[console.csv](./outputs/raw/console.csv), separately from the five-run medians.
Rebuild the deliverables after further demonstrations to consolidate their logs.

The [assessment map](./docs/assessment_readiness.md), corrected generated
[viva guide](./viva_prep.md), and [demo runbook](./docs/demo_runbook.md)
cover each marking category. [demo_round.py](./scripts/demo_round.py) records an
actual official Part G request, prior prediction and five fresh verified runs.
Part G and your oral performance remain live requirements; bonus eligibility
depends on completing A–H.

## Install dependencies

Python 3.11+ is required. The measurements in the report used Python 3.14.0,
NumPy 2.4.3, pandas 3.0.1, Windows 11, and an Intel i7-10610U with 4 physical /
8 logical cores and 31.8 GiB usable RAM (34.12 GB installed).

```powershell
python -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
```

`PYTHONPATH=src` is used because the package is small and can be run directly
from the checkout. `pip install -e ".[dev]"` also works.

## Reproduce

Run from the project root. The order below builds deterministic caches first,
then performs the measurements. The known 300-second DNF attempts are run
four-at-a-time because no elapsed time is reported for a DNF; all timed cells
are run one per requested CPU slot.

```powershell
$env:PYTHONPATH = "src"

python scripts/prepare.py              # profile, deterministic caches, C5 inversions
python -m pytest -q                    # correctness and measurement-integrity tests
python scripts/run_dnf.py              # genuine algorithm-only timeout attempts
python scripts/run_tournament_parallel.py --workers 4
python scripts/measure_memory.py       # tracemalloc rows at n=10,000
python scripts/run_topk.py --extra-k 2068
python scripts/measure_topk_memory.py # tracemalloc rows for the Top-K queue
python scripts/run_livefeed.py --memory
python scripts/analyze_data.py         # A evidence, fraud curve, M6 predictions
python -m midnight_queue.plotting      # all report figures
python scripts/assemble_results.py     # results.csv
python scripts/build_submission.py     # notebook, TeX, PDF, validation and ZIP
```

The full benchmark is intentionally expensive: the DNF phase alone takes about
20 minutes, and a timed-out cell has no fabricated median.
Timed tournament cells run four at a time, on distinct requested logical-CPU slots, so their
absolute times include shared cache/memory contention; compare them with each
other, not with the single-process Top-K or live-feed tables. Do not interrupt
the tournament while its CSV is being written; the runner uses an atomic
temporary file plus a `.bak` copy after every completed cell.

The walkthrough notebook is `23I-2581-A2-DS-B.ipynb`. It uses the prepared
package and shows the profile, a small correctness check, a timed sample, and
the fraud-capture result without rerunning the complete tournament.

## Measured evidence

The report derives recommendations from the current recorded medians, not from
hardcoded historic times. See [results.csv](./results.csv), the report's
recommendations, and [campaign provenance](./outputs/revision/campaign.json).
K=52 captures zero frauds under the required scoring rule; K=2,068 is the minimum
half-capture queue. DNFs have no invented time or median.

To resume the staged revision campaign without discarding valid completed runs:

    python scripts/refresh_experiments.py --stage all

Source hashes prevent mixing measurements after an algorithm changes. The
original 55 forecasts remain unchanged; their outcomes are reconciled with
current measurements. The revision's prospective C forecasts are separate.
Standby-interrupted attempts are identified and retained as audit evidence.

## Layout

```text
src/midnight_queue/       data, conditions, custom sorts, Top-K, live feed,
                          plotting, prediction log, results schema
scripts/                  prepare, benchmark workers, runners, analysis,
                          figure/report builders, results assembler
tests/                    correctness, edge cases, real-data, and property tests
docs/                     specification and decision log
outputs/raw/              machine-readable measurements
outputs/analysis/         A evidence, fraud curve, M6 analysis
outputs/figures/          figures used by the report
prediction_log.csv        predictions written before rounds, outcomes after
results.csv               consolidated measurement table
23I-2581-A2-DS-B.pdf      five-page report
23I-2581-A2-DS-B.zip      submission archive
```

## Implementation notes

- Insertion Sort is in-place with shifting. Merge Sort is top-down and stable.
  Naive Quick Sort is last-element-pivot Lomuto, implemented iteratively with
  an explicit stack so Python's recursion limit cannot crash it. Hardened Quick
  Sort uses median-of-three plus three-way partitioning and an in-place heap
  fallback after twice the binary-log partition depth, guaranteeing worst-case
  O(n log n) time. Heap Sort uses a
  bottom-up binary max-heap. No built-in or NumPy sort appears inside a
  contender; `sorted()` appears only in reference/verification code and in the
  labelled CSV input preparation.
- A key comparison is one call to `TriageOrder.cmp`. An element move is one
  assignment of a transaction reference into an algorithm-controlled slot; a
  swap counts as three moves. Input copying, CSV loading, risk scoring,
  condition construction, and verification are outside the timer.
- Every timed cell is five completed runs and the median; each run receives a
  fresh copy outside the timer. A run over 300 seconds is a DNF. No DNF is
  given a fabricated elapsed time or median.
- C5 moves exactly `floor(0.01 n)` records by a seeded derangement. C6 is the
  literal band-only condition. This creates a disclosed conflict with the
  assignment's statement that the key is total: exact-sequence equality is
  required for C1–C5, while C6 is checked as a permutation with non-increasing
  bands and no secondary-key access. See `docs/specification_and_decisions.md`.
- Part G will be provided during the demo and is omitted from this report as requested.

## Tests

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
```

The suite covers empty input, one record, all-equal keys, duplicate-heavy
records, comparator semantics, Class invariance, every condition, every size,
Top-K boundaries, all live-feed strategies, and real-data ranking checks. The
real-data test is skipped automatically if `data/creditcard.csv` is absent.

## Licence and academic integrity

The dataset is governed by the Kaggle page's licence and is not redistributed.
The code and report are the student's submission. The report contains an
AI-use disclosure; the student must be able to explain and modify every
algorithm and result in the viva.
