# Assessment evidence and remaining live requirements

This maps evidence to the supplied marking scheme. It is not a mark award or
a guarantee of full marks.

| Part | Marks | Evidence | Readiness |
|---|---:|---|---|
| A | 5 | Report A; data profile and fraud-capture analysis | Automated identity checks and reported distribution/tie/order evidence |
| B | 20 | Custom source, correctness/adversarial tests, console using the same code | Tested implementations; C6 interpretation explicitly disclosed |
| C | 10 | 120 cells, raw runs, median checks, counts, memory and six plots | Coverage and evidence validation |
| D | 7 | 84 method/input/K medians, output verification and fraud curve | Required grid plus half-capture K; provenance disclosed |
| E | 7 | Two schedules, every publication, five totals per completed strategy and memory | Timing scopes match; genuine DNF preserved |
| F | 22 | M1–M8 in report and corrected viva derivations | Includes tight 1:9 bound, accepted-record costs and exact C6 model |
| G | 4 | Actual change request plus fresh demo results | Not yet assessable: request is supplied during demo; report omission is intentional |
| H | 5 | Current evidence, assumptions and failure conditions | Updated data-driven choices |
| Viva | 20 | Code understanding and modification in front of examiner | Requires your live performance; practise using the generated guide |
| Bonus | 5 | Local analyst console; report paragraph; UI/API tests | Implemented; demonstrate live; credit conditional on A–H completion |

The written/code categories A–F and H account for 76 allocated marks.
They have evidence, but the examiner decides the score. The remaining core
24 marks are G and the viva. The manual's viva cap still applies, and optional
bonus credit does not compensate for missing required work.

## B: implementation evidence by allocation

| Subpart | Marks | Explain and demonstrate |
|---|---:|---|
| Insertion | 3 | Prefix invariant, explicit shifts, inversion sensitivity and stable equal keys |
| Merge | 4 | Recursion and merging, left-on-equality stability, auxiliary memory |
| Quick | 5 | Exact last-pivot Lomuto, three-way hardened partition, depth guard and smaller-side stack |
| Heap | 4 | Bottom-up linear build, heap invariant, extraction and in-place operation |
| Top-K | 4 | Worst-retained root, replacement, ordered publication, bounded buffer search and shifts |

## F: required method by allocation

| Item | Marks | Required reasoning |
|---|---:|---|
| M1 | 3 | Direct inversion analysis; best, average, worst and actual C5 inversions |
| M2 | 3 | Iteration first, then Master's theorem |
| M3 | 4 | Worst by iteration; best and tight 1:9 bound by recursion tree |
| M4 | 3 | Height sum for build and total extraction cost |
| M5 | 3 | Complete ordered-queue costs; prior crossover prediction versus measured result |
| M6 | 3 | Actual group sizes, within-band term, exact sequence recurrence and count comparison |
| M7 | 2 | All-window costs and a qualified strategy-change comparison |
| M8 | 1 | Auxiliary space of every contender, with log-size quicksort stack |

Known judgement points are documented instead of hidden: literal C6 conflicts
with total-order equality elsewhere; C5 uses a seeded derangement; timing
variation and inherited benchmark provenance are disclosed. Ask the examiner
to confirm their preferred interpretation if they challenge these choices.

Use the [runbook](./demo_runbook.md), [viva guide](../viva_prep.md),
[detailed audit](./deep_audit.md), and generated
[validation results](../outputs/submission_validation.json).
