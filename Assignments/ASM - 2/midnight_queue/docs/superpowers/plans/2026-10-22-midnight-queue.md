# Midnight Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, test, benchmark, analyse and package the complete Midnight Queue assignment for roll 23I-2581 / section DS-B.

**Architecture:** A focused Python package under `src/midnight_queue/`, separating immutable records and the ranking comparator (`records.py`), data/risk preparation (`data.py`), deterministic C1–C6 inputs (`conditions.py`), custom algorithms (`sorting.py`, `topk.py`), live-feed state machines (`livefeed.py`), measurement (`benchmark.py`, `profiling.py`), and reporting (`plotting.py`, `reporting.py`, `mathcase.py`). A CLI composes these modules; tests use synthetic records and, when present, the real file.

**Tech Stack:** Python 3.11+ (running 3.14), pandas, NumPy, Matplotlib, pytest, reportlab, standard-library subprocess/tracemalloc.

**Spec:** `docs/specification_and_decisions.md` and the authoritative PDF one level above this project.

## Global Constraints

- Seed `s=232581`; K `52`; roll display `23I-2581`; section `DS-B`.
- Risk uses V1–V28 population z-scores computed over the full file.
- Triage key is band desc, Amount desc, Time asc, txn_id asc; `Class` never appears in it.
- C6 is literal band-only; exact-sequence equality is not asserted; band order is.
- No built-in or NumPy sort inside contenders.
- Five-run median only when all five complete; 300 s per-run DNF watchdog.
- Report ≤ 5 pages; dataset excluded from ZIP; no invented change request or measurements.

## Review Focus

- Existing `creditcard.csv` is not modified: loader validates and computes derived fields without mutating source.
- C5 must move exactly 1% of records, not merely choose positions.
- Timed inputs must be copied outside the timer and be identical across contenders.
- C6 must not accidentally acquire a secondary triage key.
- DNF paths must never acquire an invented elapsed time or five-run median.

---

### Task 1: Scaffold and configuration

**Files:** Create `pyproject.toml`, `requirements.txt`, `src/midnight_queue/__init__.py`, `config.py`, `tests/conftest.py`, `data/README.md`.

**Interfaces:** `AssignmentConfig(roll_display: str, seed:int, section:str, k:int)` and `load_config(path=None)`.
- [x] Create directories and metadata.
- [x] Add runtime validation that the displayed roll contains exactly the seed digits and K matches the formula.
- [ ] Test config derivation and invalid rolls.

### Task 2: Records, ranking, data, conditions

**Files:** `records.py`, `data.py`, `conditions.py`, `tests/test_records.py`, `tests/test_conditions.py`, `tests/test_data.py`.

**Interfaces:** `Txn`, `TriageOrder`, `Dataset`, `load_dataset(path)`, `sample_dataset(ds,n,seed)`, `build_conditions(records,seed)`.
- [ ] Write comparator/ordering tests including duplicates and all-equal keys.
- [ ] Write controlled 4-row C1–C6 tests and C5 displacement test.
- [ ] Implement and pass.

### Task 3: Five full-sort contenders

**Files:** `sorting.py`, `tests/test_sorting.py`.

**Interfaces:** `insertion_sort`, `merge_sort`, `naive_quicksort`, `hardened_quicksort`, `heap_sort`, all `(list[Txn], TriageOrder, Counters) -> list[Txn]`.
- [ ] Test empty, one, ordered, reverse, all-equal, duplicates, random permutations against independent reference.
- [ ] Test inversion counting and instrumentation monotonicity.
- [ ] Implement iterative Lomuto quick sort and median-of-three three-way quick sort.

### Task 4: Top-K selectors

**Files:** `topk.py`, `tests/test_topk.py`.

**Interfaces:** `topk_heap`, `topk_buffer`; K=0, 1, n−1, n, >n cases.
- [ ] Compare exact ordered output with the full-sort reference prefix.
- [ ] Implement max-heap-of-worst and sorted bounded buffer.

### Task 5: Live feed

**Files:** `livefeed.py`, `tests/test_livefeed.py`.

**Interfaces:** `window_records`, `run_live_feed`, strategies `rerank`, `heap`, `merge`.
- [ ] Test empty windows, last partial window, exact queue agreement, K>seen.
- [ ] Implement all three and record per-window timings/correctness.

### Task 6: Verification suite

**Files:** `tests/test_reference.py`, `tests/test_edge_cases.py`, `tests/test_c6_policy.py`.
- [ ] Run custom-versus-reference on generated and real sampled data, all conditions.
- [ ] Confirm `Class` perturbation changes no ranking output.
- [ ] Confirm C6 literal policy only checks band order/permutation.

### Task 7: Profiling and benchmark harness

**Files:** `profiling.py`, `benchmark.py`, `tests/test_benchmark.py`.
- [ ] Prediction log written before each round.
- [ ] Subprocess per timed repetition with 300 s watchdog.
- [ ] CSV schema distinguishes run rows, medians, DNFs, extrapolations.
- [ ] Memory measured separately.

### Task 8: Real experiments A–F

**Files:** `scripts/run_all.py`, `results.csv`, `prediction_log.csv`, `outputs/*`.
- [ ] Profile full dataset, build all conditions/sizes, verify all available contenders.
- [ ] Run tournament, Top-K, live-feed, inversions, band groups, fraud capture, memory.
- [ ] Record every failure honestly.

### Task 9: Report, notebook, viva, package

**Files:** `report.md`, `report.pdf`, `Midnight_Queue.ipynb`, `viva_prep.md`, `README.md`, `scripts/package.py`, `Naming.pdf`, `Naming.zip`.
- [ ] Generate required figures with captions and units.
- [ ] Generate ≤5-page PDF and verify page count.
- [ ] Notebook imports the tested package and demonstrates the result.
- [ ] Create ZIP excluding CSV, caches, venvs; inspect contents.
- [ ] Final checklist and commands.

## Self-review

The plan maps every PDF problem to at least one task.  C6's conflict, DNF handling, five-run medians, `Class` restriction, report length and ZIP exclusions are explicit.  Interfaces are consistent: all full sorts take `(items, order, counters)`; both Top-K selectors take `(items, k, order, counters)`; live-feed compares the same `Txn` records through `TriageOrder`.
