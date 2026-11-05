# Assignment compliance review

Reviewed against the supplied manual on 23 October 2026. See the detailed [audit](./deep_audit.md) and generated [validation results](../outputs/submission_validation.json).

| Requirement | Evidence and check |
|---|---|
| Parameters | Roll 23I-2581, seed 232581, DS-B, K=52; configuration tests |
| A: data and risk | Enforced official checksum, 284,807 rows, 492 frauds, full-file population z-scores; Class evaluation only |
| A: profile | Band histogram/counts, Amount ties, Time order and exact triage inversions |
| B: implementations | Five required custom full sorts, heap selector, bounded insertion buffer and three live strategies |
| B: correctness | Exact full-key equality C1-C5; literal C6 band order/permutation; empty, singleton, duplicates, stability, label isolation and adversarial tests |
| C: coverage | All 120 cells have five-run medians or explicit DNF evidence |
| C: timing | Unique repeat IDs, positive finite times <=300 s, correctness, deterministic counts and recomputed medians |
| C: memory | Separate n=10,000 traces for all 30 algorithm/condition pairs; stability and asymptotic space |
| C: figures | Required C2 growth, grouped bars, comparisons, moves and both normalisations; units, legends and captions |
| D: grid | All six required capacities plus K=2,068, both sizes and C1/C2; all three ordered-output methods |
| D: evaluation | Fraud capture curve, minimal half-capture capacity and queue-production costs |
| E: live | Both schedules, every publication verified; five complete simulations per median or explicit DNF; separate memory |
| E: timing consistency | Recorded totals equal window sums; summaries/curves share algorithm-only scope |
| F: derivations | M1-M8, tight 1:9 bound, accepted-buffer/publication costs, corrected exact C6 model |
| H: decisions | Current measured evidence, assumptions and a failure condition for each recommendation |
| Predictions | All 55 original forecasts/rationales/timestamps preserved; revised outcomes and separate prospective revision forecasts |
| Report | At most five pages including appendix; editable TeX plus portable images; AI disclosure |
| Notebook | Every code cell executed without error; required figures and executable assertions |
| ZIP | Source, tests, README, notebook, PDF, TeX/images, logs and results; dataset excluded |
| Bonus console | Seven real contenders, configurable K/input, full queue pagination, runtime/comparisons, verification and cancellation; short report description |
| Viva preparation | Generated current derivations, invariant practice and demo runbook; oral performance remains unassessed |

Part G is reserved for the demo and omitted from the report at the student's explicit request. No future demonstration or viva is claimed complete.

The [assessment map](./assessment_readiness.md) distinguishes prepared evidence from live requirements. Bonus eligibility depends on completing A-H.

The C6 conflict is disclosed in [specification_and_decisions.md](./specification_and_decisions.md). Provenance, censored DNFs, the standby interruption and remaining algorithm limitations are documented in [deep_audit.md](./deep_audit.md).
