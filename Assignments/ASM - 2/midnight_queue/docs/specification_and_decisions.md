# Specification and Decision Log

**Project:** The Midnight Queue — Ranking Suspicious Transactions at Scale  
**Student roll (display):** 23I-2581  
**Seed / roll digits:** 232581  
**Section:** DS-B  
**Shift capacity:** K = 25 + (232581 mod 226) = 52

## Authoritative source

`../The Midnight Queue - Assignment 2.pdf` (8 pages, FAST-NUCES Islamabad Campus,
Design and Analysis of Algorithms, BS DS & AI, Assignment 2).  The PDF is the
authoritative specification.  This file records decisions where the PDF is
silent or internally inconsistent.

## Fixed requirements copied from the PDF

- Dataset: Kaggle `mlg-ulb/creditcardfraud`, expected file `creditcard.csv`.
- Columns: `Time`, `V1`…`V28`, `Amount`, `Class`.
- `txn_id`: original CSV row number, starting at 1.
- Risk: population-standardised `V1`…`V28`, then sum of the 28 squared z-scores.
- Band: `min(9, max(0, floor(log2(risk))))`.
- Triage order: band descending, Amount descending, Time ascending, txn_id
  ascending.
- `Class` is evaluation-only and is never part of a score or sort key.
- Conditions C1–C6, sizes 1,000 / 10,000 / 100,000 / 284,807.
- All randomness seeded with `s`.
- Custom implementations only for the contenders; `sorted()` and NumPy sort
  are reference/baseline only.
- Five timed repetitions when all complete; median reported.
- A run over 300 s is DNF; largest completed n and a justified extrapolation
  must be reported.
- Report at most five pages.

## Decisions

### D1 — Standard deviation convention

Use the **population** standard deviation (`ddof=0`) over all 284,807 rows.
This is the standard z-score convention and avoids sample-size-dependent
feature scaling.  The very large population makes the ddof=0/ddof=1 numerical
difference negligible, but the choice is fixed and tested.

### D2 — Zero variance / zero risk / invalid values

- A feature with zero standard deviation contributes `z=0`; a constant feature
  carries no anomalous information.  This branch is documented and tested.
- `risk=0` has no finite base-2 logarithm; it is assigned band 0.  This is the
  only mathematically necessary extension of the normal definition.
- Non-finite values, missing required columns, duplicate/missing IDs, negative
  Time, non-binary Class, or an unsorted raw Time column are rejected at load
  time.  No silent imputation is performed.

### D3 — Sampling

For each n, sample `n` rows uniformly without replacement using a fresh
`numpy.random.default_rng(232581)` stream, then restore ascending Time order
(ties by `txn_id`).  The same sampled records feed all six conditions at that n.
The full-file condition uses all records.  Sizes are independently sampled, as
the PDF does not require nested samples.

### D4 — Condition construction

- C1: sampled rows in Time/txn_id order.
- C2: C1 permuted with `default_rng(232581)`.
- C3: C1 sorted by the full triage key.
- C4: exact reverse of C3.
- C5: C3 with exactly `floor(0.01 n)` selected records
  relocated.  The selected records' positions are shuffled among themselves
  until no selected record stays in its original slot, so exactly a 1% block
  changes position.  The same seeded RNG drives the choice.
  For a single selected record, remove/reinsert it at a different index; for
  fewer than 100 input records the floor is zero and C5 equals C3.
- C6: C1 order, but the contender comparator uses **band only**.  This is the
  literal PDF definition.

C3 is preparation, not a benchmark contender.  It uses a deterministic
reference key function; custom contenders still receive the resulting list.

### D5 — C6 tie conflict (material, disclosed)

The PDF calls the triage order total and demands identical outputs, but C6
defines the sort key as `band` alone, producing massive ties.  The literal C6
experiment is retained.  Correctness for C6 is defined as:

1. every output is a permutation of the input;
2. bands are non-increasing; and
3. no `Amount`, `Time`, `txn_id`, or `Class` value is consulted by the C6
   comparator.

Exact row-sequence equality is **not** required for literal C6 because
unstable algorithms can legitimately order equal-band records differently.
A separately labelled stable-band reference may be used for reproducibility
testing only; it is not mixed into the literal C6 benchmark.  The tournament
uses literal band-only comparison.

### D6 — Instrumentation

- **Key comparison:** one call to the centralized ranking comparator `cmp(a,b)`.
- **Element move:** one assignment of a transaction record into an
  algorithm-controlled list position.  A swap is three element moves.
- Scalar variables, loop counters and comparisons of indices are not moves.
- Merge-sort writes into its auxiliary buffer and writes back both count.
- Top-K counters include selection, heap construction, and production of the
  final ordered K records, because the queue itself must be ordered.
- Timers exclude CSV I/O, standardisation, condition construction and the
  correctness check.  Each timed run receives a fresh copy outside the timer.
- Peak extra memory is measured with `tracemalloc` in separate runs so that
  allocation tracing does not contaminate timing.

### D7 — Insertion sort / naive quicksort

Insertion sort is implemented in place with a custom comparator.  Naive quick
sort is exactly last-element-pivot Lomuto, implemented iteratively with an
explicit stack to avoid Python recursion-limit failures while preserving the
specified partition sequence.  Hardened quick sort uses median-of-three pivot
selection plus three-way partitioning and an in-place heap fallback after
2 floor(log2 n) partitions on a path. This guarantees O(n log n) worst-case
time; comparisons use the same counter. The prescribed naive algorithm is unchanged.

### D8 — Top-K output

A queue means an ordered top-K sequence, not an unordered set.  Both Top-K
methods return the retained records in triage order.  Heap selection extracts
the retained heap; the bounded buffer remains sorted.  Consequently their
counts include final-output ordering.

### D9 — DNF

A subprocess watchdog enforces 300 seconds per individual timed run.  A timeout
is written as `DNF` with no invented elapsed time.  If the first run times out,
no five-run median is claimed.  Completed smaller sizes remain; extrapolation
is explicitly labelled and kept separate from measurements.

### D10 — C6 numerical interpretation

Risk is computed once per sampled record.  C6 changes only the comparator, so
its band values are identical to C1's for the same records.

### D11 — Report

The report is generated from measured artifacts.  If any required run is
unavailable, the report says so. Part G is reserved for the demo and omitted
from the report at the student's explicit request; no request is invented.

### D12 — AI disclosure

The report will truthfully disclose the AI assistant used for implementation,
testing, experiment orchestration, analysis and drafting, and will state that
the student must verify and be able to explain all submitted work.

## Unresolved / external inputs

- Part G will be provided during the demo and is outside this report.
- Viva date: not supplied.
- Report author name: roll and section supplied; full name not requested.
