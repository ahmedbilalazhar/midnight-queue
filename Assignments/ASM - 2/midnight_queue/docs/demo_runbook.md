# Demo and viva runbook

Part G is reserved for the demo and stays out of the report as requested.
The actual official request and your live explanation cannot be completed in
advance. Bonus eligibility depends on A–H being complete.

## Before the session

1. Put the official dataset in the documented location and run the tests.
2. Open the five-page report, executed notebook and [viva guide](../viva_prep.md).
3. Start the console from the project root:

~~~powershell
python scripts/run_console.py
~~~

Open http://127.0.0.1:8765. The VS Code task is named
"Midnight Queue: analyst console". The UI uses the same custom contenders;
it does not replace them with a sorting library.

## A three-minute bonus demonstration

1. Choose Size-K Heap, n=1,000, C1, K=52. Build the queue.
   Point out risk band, Amount, Time, ID, runtime and comparison count.
   Show that the queue is verified against an independent reference.
2. Move to the second page: every one of the K records is accessible.
3. Keep n, condition and K identical; choose Merge Sort and rebuild.
   Compare both the time and the key-comparison count. The queue should agree.
4. Set K=500 and explain how heap publication and buffer shifting change.
5. Use n=1,000 and C3, then C4, with Insertion Sort. Predict before running.
   Explain the difference using inversions. Keep large quadratic cases out
   of the short demo; if shown, demonstrate cancellation and the DNF rule.
6. State that console runs are individual demonstrations logged separately,
   whereas the report uses medians of five runs.

The interface accepts all five full sorts plus the heap and bounded buffer,
four required sizes, C1–C5, and 1<=K<=n. All output uses the full triage key.
C6's band-only experiment and tie ambiguity are demonstrated in the notebook,
tests and raw tournament instead.

## When the official Part G request arrives

1. Save its exact text in a local UTF-8 text file. Read the constraint aloud:
   what changed, which job is affected, and what must remain fixed?
2. Identify which assumption your earlier recommendation used. State what you
   predict will still hold and what might change before measuring.
3. For changed K, n, input condition or window width, use
   [demo_round.py](../scripts/demo_round.py). Supply the actual request file
   and your own prediction. Example command structure, with values chosen
   after reading the official request:

~~~powershell
python scripts/demo_round.py --request-file official_request.txt --prediction "My prediction and reason" --job queue --algorithm "Size-K Heap" --n 1000 --condition C1 --k 52
~~~

   This is a command template, not an invented change request or completed G.
   Replace its parameters to match the actual constraint.

4. The runner writes the request, a prior prediction, source hashes, seed,
   five raw verified runs and their median in a new timestamped directory.
   A single timeout creates a DNF instead of a false median.
5. Run alternatives with matching inputs and timing scopes in separate output
   directories. Compare batch counts with batch counts and complete queue
   counts with complete queue counts; queue prefix copies count as moves.
6. For a live job choose --job live, --algorithm heap, merge or rerank, and
   the requested --width and --k. It verifies every published queue and saves
   each run's window measurements.
7. If the request changes the comparator, risk definition or old-record
   mutability, edit and test the appropriate code first. The parameter runner
   alone does not implement such a request. Preserve the old source/results;
   remeasure changed contenders rather than relabelling old observations.
8. Explain the outcome: which original conclusion survives, which changes,
   the fresh evidence, and one remaining assumption. Do not infer an ordering
   between multiple censored DNFs.

## Evidence to show the examiner

| Part | Open and explain |
|---|---|
| A | Band histogram/table, Amount ties, Class distribution, arrival order and inversions |
| B | Comparator and one invariant for each implementation; tests and a failure-handling example |
| C | Six required plots, 120-cell coverage, five raw repeats and separate memory |
| D | All 28 input/K points for three methods; winning corners and K=2,068 capture/cost |
| E | Both schedules, algorithm-only totals/curves, separate memory, and the 10-minute re-rank DNF |
| F | Derive M1–M8 on paper, including both bounds for 1:9 and exact C6 sequence dependence |
| G | The actual request, your prior prediction, fresh results, revised conclusion |
| H | Merge Sort batch and heap queue/live choices, evidence, assumptions and reversal conditions |
| Bonus | Change algorithm and K in the console; show actual records, time and comparisons |
| Viva | Trace an unseen input and make a small tested code change without relying on this sheet |
