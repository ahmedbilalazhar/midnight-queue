# Deeper algorithm and evidence audit

Reviewed against the supplied manual on 23 October 2026. Part G is reserved for the demo and omitted from the report at the student's request.

| Step | Weakness and consequence | Repair and evidence |
|---|---|---|
| A: dataset | The loader computed a checksum without enforcing it, allowing a different dataset to pass. | Default loading enforces the official SHA-256 and row/fraud totals; synthetic tests explicitly opt out. See [data.py](../src/midnight_queue/data.py). |
| A: evaluation | Class leakage or hidden secondary fields could improve apparent results unfairly. | Label-perturbation and field-spy tests verify Class isolation and literal C6 behavior. The prescribed ranking is unchanged. |
| B: quicksort | Median-of-three plus three-way partitioning still permits quadratic adversarial splits. | Introspective depth budget with in-place heap fallback guarantees O(n log n) worst-case time and O(log n) stack. Forced bad-pivot and range-preservation tests exercise the safeguard. See [sorting.py](../src/midnight_queue/sorting.py). |
| B: counters | Different counter objects silently split comparisons from moves. | All public sorts/selectors reject mismatched counters. Stability tests use genuinely equal complete keys and object identity. |
| B: Top-K | Heap/buffer initialization copied a slice twice; noninteger capacities failed inconsistently. | One initial slice and consistent integer-index validation; comparator loops are preserved. See [topk.py](../src/midnight_queue/topk.py). |
| C: deadlines | Full-C5 insertion runs of 349.820 and 497.862 seconds were included in an old median. Preparation failures could also masquerade as DNFs. | Over-limit observations are excluded and archived; the cell is DNF. Algorithm-only child deadlines are separate from the process envelope. Worker errors now propagate. |
| C: repeats | A run-count label alone does not establish five valid observations. | Checks cover unique repeat IDs, positive finite times, correctness, deterministic counts and recomputed medians. Completed tournament cells were remeasured. |
| C: standby | Modern Standby interrupted four full-size cells on 23 October, 11:23:24-11:38:17 PKT. | Power events are archived. Attempts are classified as interruptions rather than algorithm DNFs; valid runs are retained and missing repetitions remeasured. See [campaign.json](../outputs/revision/campaign.json). |
| D: complete cost | One full-sort time was reused at every K, omitting actual prefix extraction, and could create duplicate medians on resumption. | Full sort is freshly measured at each K including prefix-copy time/moves. The runner resumes persisted repetitions without duplicating completed cells. |
| D: decisions | One winning corner can hide severe slowdown elsewhere. | Current recommendations derive from grid wins and worst regret. Unchanged heap/buffer comparison loops retain explicitly identified earlier measurements. |
| E: timing | Old summaries included verification/logging while curves summed algorithm-only timers. | Both now use the same window-time sum; five independent totals are saved and checked. All live strategies were remeasured. See [livefeed.py](../src/midnight_queue/livefeed.py). |
| E: reference | Missing expected queues defaulted to an empty list and could validate an empty publication falsely. | Missing references raise an error even when K=0. Verification remains outside timing. |
| F: C6 model | The exact model used ascending partitioning while the contender ranked bands descending. | Corrected descending Lomuto simulation exactly matches measured counts: 158,620 at 1k and 16,023,019 at 10k. The within-band group term is a lower bound; cross-band work depends on the sequence. A four-record counterexample gives 6 versus 4 comparisons for identical group sizes, so group sizes alone cannot determine the exact count. |
| F: derivations | An upper bound alone does not prove a tight 1:9 result; output publication and accepted insertions also cost work. | Both bounds, ordered publication, accepted-record costs, exact C6 recurrence and crossover qualifications are included. |
| H: stale prose | Hardcoded winners/times can contradict revised implementations. | Recommendations and outcomes derive from current evidence. Original forecasts, rationales and timestamps are preserved; prospective revision forecasts are separate. |
| Deliverables | Compilation alone does not verify five pages, image portability or an executed notebook. | Automated checks cover these requirements, figure exports and dataset exclusion from the submission ZIP. |

## Intentional limitations and boundaries

- Insertion sort remains quadratic on highly inverted data. The required shifting implementation is retained; use it for ranked or genuinely low-inversion data.
- Naive last-pivot Lomuto remains quadratic on sorted, reversed and duplicate-heavy inputs. The explicit stack prevents recursion failures without changing the required algorithm.
- The bounded buffer shifts O(K) references per accepted record. Small-corner wins do not establish general superiority. Near-full capacity needs a fresh comparison.
- The maintained heap assumes immutable scores; revising old scores requires indexed updates or rebuilding, which this implementation does not claim.
- The fixed ranking places zero frauds in K=52. This is a scoring/capacity limitation. K=2,068 is the minimum half-capture queue (246 of 492). Changing the assignment key or ranking using Class would invalidate the experiment.
- Literal C6 compares only bands while the manual elsewhere asks for identical total-order output. Equal-band order is unspecified. C6 checks permutation preservation and descending bands without inventing secondary keys.
- Tournament workers use concurrent requested CPU slots and share scheduling/cache resources. Heap/C1 has a nonmonotone time median (100k slower than full size) even while comparison counts grow; this timing clash is disclosed. Growth conclusions use operation counts rather than forcing noisy elapsed times to fit theory. D/E workers run serially; compare within tables. Historical DNFs for unchanged quadratic contenders and unchanged heap/buffer results are explicitly identified.

## Verification and reproduction

[build_submission.py](../scripts/build_submission.py) runs tests, regenerates figures, executes the notebook, compiles the editable TeX, validates and packages saved evidence. It does not silently rerun expensive benchmarks.

[refresh_experiments.py](../scripts/refresh_experiments.py) records source hashes, environment, staging CSVs and five repetitions per completed cell. [validate_submission.py](../scripts/validate_submission.py) checks raw evidence. Earlier sources and measurements remain in [before_deep_hardening/](../outputs/audit/before_deep_hardening/).

Repeated standby events later interrupted a full-sort Top-K cell and live-feed
cells. Their earlier records remain archived and are rechecked under a temporary
system-awake request. The request is released on exit and does not change the
machine's power plan. Censored results are distinguished from programming errors.

CPU slots are reserved for the duration of each tournament cell. Assigning slots
by submission index, as the earlier runner did, could put two overlapping jobs on
one requested CPU after a short cell finished; both runners now allocate slots
until the corresponding cell completes.

Part G and the viva remain demo-time responsibilities; no future demonstration is claimed complete.
