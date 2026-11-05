"""Keep viva explanations and numerical examples aligned with current evidence."""
from pathlib import Path
import build_report as report
from audit_report_content import evidence

ROOT=Path(__file__).resolve().parents[1]
TEMPLATE=r"""# Viva preparation: The Midnight Queue

Roll 23I-2581; DS-B; seed 232581; K=25+(232581 mod 226)=52.
Generated from current measurements. Use this to practise explaining the code,
not as a script to memorise. The examiner awards the viva marks.

## A two-minute explanation

I standardise V1–V28 over the full official file using population standard
deviations, sum squared z-scores and clip floor(log2 risk) to bands 0–9.
I then rank by band descending, Amount descending, Time ascending and original
one-based transaction ID ascending. Class is evaluation-only.

Five custom full sorts and two Top-K selectors compete on controlled inputs.
The hardened quicksort groups duplicates and switches to an in-place heap
fallback if its partition depth exceeds twice floor(log2 n). Five-run medians,
counts and separate memory traces support the recommendations.

Current overnight choice: {{BATCH}}. Small-K queues and both live schedules
favour the maintained heap. The scoring rule captures zero frauds at K=52;
K=2,068 is the minimum queue capturing 246 of 492 frauds. Sorting faster cannot
repair that scoring/capacity limitation.

## Numbers to locate and explain, not recite blindly

{{TIMES}}

The C2 n=100k, K=10,000 comparison is heap {{HEAP10}} versus full sort {{FULL10}}.
The original full-sort crossover forecast near K=10,000 was wrong at this point.
Timing varies with scheduling/power; counts are deterministic. Explain the
reported nonmonotone Heap/C1 timing rather than forcing it to fit a curve.

## Invariants and code navigation

| Component | Invariant to explain | Source |
|---|---|---|
| Comparator | Negative means left record should be ranked earlier; Class is absent | [records.py](./src/midnight_queue/records.py) |
| Insertion | Before iteration i, prefix [0,i) is sorted; shift only strictly worse entries | [sorting.py](./src/midnight_queue/sorting.py) |
| Merge | Two sorted halves; taking left on equality preserves stability | [sorting.py](./src/midnight_queue/sorting.py) |
| Lomuto | Before j: entries before i compare <= pivot; middle entries compare > pivot | [sorting.py](./src/midnight_queue/sorting.py) |
| Three-way partition | Less-than, equal and greater-than bands surround the unexamined region | [sorting.py](./src/midnight_queue/sorting.py) |
| Introspection | Budget decreases on every partition path; disjoint fallback ranges are heap-sorted | [sorting.py](./src/midnight_queue/sorting.py) |
| Size-K heap | Root is the worst retained record; retained set is the best min(K,seen) | [topk.py](./src/midnight_queue/topk.py) |
| Buffer | Ordered K-prefix; rejection compares once with the worst; acceptance shifts explicitly | [topk.py](./src/midnight_queue/topk.py) |
| Live merge | Previously retained top K plus new records suffices for the next top K | [livefeed.py](./src/midnight_queue/livefeed.py) |

The assignment's min-heap means minimum ranking priority at the root:
(band, Amount, -Time, -txn_id). It is a max-heap under the best-first comparator.
For K=2 with priorities 9 and 7, a new priority 8 must replace 7, leaving 9 and 8.

## Derivations to reproduce on blank paper

1. **Insertion:** Each shift removes one inversion. For n>=1, moves=I+n-1;
   comparisons=I+n-1-z, 0<=z<=n-1. Thus T(n,I)=Theta(n+I).
   Best I=0; random distinct keys E[I]=n(n-1)/4; reverse I=n(n-1)/2.
   Moving 1% of records can create Theta(n²) inversions.
2. **Merge:** Iteration gives T(n)=2^j T(n/2^j)+jcn. Set j=log2 n:
   Theta(n log n). Master: a=b=2, f(n)=Theta(n^{log_b a}), case 2.
3. **Quick:** Worst iteration sums n+(n-1)+...+1=Theta(n²).
   Balanced tree has log2 n levels costing Theta(n) each.
   For 1:9, the first floor(log_10 n) levels each have total size n:
   Omega(n log n). Depth is at most ceil(log_(10/9) n): O(n log n).
   Both bounds are needed for a tight Theta(n log n) proof.
4. **Heap:** Sum height costs: O(n sum_h h/2^(h+1))=O(n);
   visiting internal nodes gives Omega(n), so build is Theta(n).
   Worst-case extraction costs Theta(n log n) overall.
5. **Top-K, 2<=K<=n:** Full sort plus output is O(n log n+K).
   Heap build O(K), scan O(n+A log K), publication O(K log K).
   Buffer O(K log K+n+A(K+log K)), worst O(nK).
   On a random distinct permutation P(accept i)=K/i, so
   E[A]=K(H_n-H_K). Rejected buffer records need no binary search.
   Neither a universal crossover nor a timing constant follows from big-O.
6. **C6:** Within each group, all same-band pairs eventually compare:
   sum_i m_i(m_i-1)/2 is a lower bound. Cross-band work depends on arrival
   sequence, so sizes alone cannot determine the exact count.
   [2,2,1,1] and [1,2,1,2] have the same sizes but cost 6 and 4 comparisons.
   Exact recurrence: C(S)=|S|-1+C(L_p(S))+C(R_p(S)), following actual Lomuto swaps.
   Descending-band model and measured counts agree: 158,620 at 1k and
   16,023,019 at 10k. The old ascending model was wrong; do not quote it.
7. **Live, equal-size windows:** A=sum_j Theta((jn/w) log(jn/w))
   =Theta(nw log n) worst case. B=O(n log K+wK log K).
   C=O(n log(n/w)+wK). The rough w≈n/K comparison omits constants and
   publication terms; it is not a measured universal crossover.
8. **Space:** Insertion/Heap O(1); Merge O(n); both implemented Quick variants
   O(log n) worst-case explicit stack because the smaller side is processed first.
   Top-K selectors O(K); live A O(n), B O(K), C O(n/w+K) for equal windows.
   Retained measurement logs add O(w) bookkeeping; shared input is excluded.

**Why introsort guarantees the bound:** At most 2 floor(log2 n) partition levels
cost O(n log n). Remaining ranges are disjoint, and their heap-sort costs sum
to at most O(n log n). Three-way partitioning alone does not guarantee this.

## Measurement and specification questions

- A comparison is one central comparator call. A slot assignment is a move;
  an actual swap counts three. Scalar/index work is not counted.
- Initial input copying, loading, scoring, construction and verification
  are outside full-sort/Top-K timers. Output ordering and prefix extraction count.
- Live summaries sum algorithm-only window times, exactly as their curves do.
  Memory tracing is separate. One measured run over 300 s makes a DNF cell;
  no median is invented. Human cancellations and system interruptions differ.
- C1 is arrival order; C2 seeded shuffle; C3 ranked; C4 exact reverse;
  C5 floor(0.01n) records deranged among selected positions; C6 band-only C1.
  For q=1, C5 removes/reinserts one record; for q=0 it equals C3.
- C6 does not define a unique row sequence, although another manual clause
  asks for identical total-order outputs. Explain the disclosed interpretation:
  band order and permutation, without secondary-field comparator access.
- A DNF is censored. If two contenders time out, their relative speed is unknown.
- A maintained heap assumes immutable scores. An indexed update or rebuild is
  needed if old scores change. K near n and very small live windows can reverse choices.

## Closed-book practice

Predict first; then run a small instance and explain any disagreement.

1. Trace insertion on priorities [3,1,2]. Count shifts, comparisons and key writes.
2. Trace one Lomuto partition on [2,2,1,1], with band descending.
3. Explain why sorted unique input and all-equal input both hurt naive Lomuto.
4. Draw a 1:9 recursion tree and give both bounds without Master's theorem.
5. Derive a heap replacement on priorities [9,7], then arrival 8, K=2.
6. If only the new window has 3 records and K=52, what must live merge retain?
7. Explain why publication is O(K log K) for the heap, not O(K).
8. Show a stability test with genuinely equal complete keys; different IDs
   are not equal keys.
9. Change a primary comparison direction in a separate practice copy,
   update its independent reference, and diagnose a failing test.
10. Add a test for an empty live window or a capacity boundary and run it.
11. Find one incorrect prediction in the appendix and explain why it was wrong.
12. Open any recorded median and recompute it from its five raw repetitions.

## A practical ten-minute rehearsal

- Minute 0–2: definitions, seed, scoring, Class isolation and the C6 conflict.
- Minute 2–4: trace comparator, insertion, Lomuto and heap replacement.
- Minute 4–6: derive the 1:9 bound and one Top-K/live cost on paper.
- Minute 6–8: demonstrate the console and interpret time versus counts.
- Minute 8–10: change a small test/code path in a practice copy and explain it.

The official viva is 20 marks. Below 50% of that component triggers the manual's
cap on other components. Passing automated tests does not establish your
ability to explain or modify the implementation live.

## Demo navigation

See [demo_runbook.md](./docs/demo_runbook.md) for the console and actual change
request workflow. Part G remains reserved for the demo, outside this report.
"""


def main():
    data=report.load()
    winner,worst,_,_,_=evidence(data)
    lines=["| Measurement | Current value |","|---|---|"]
    lines.extend(f"| Worst full-size C1–C5: {name} | {report.fmt_s(value)} |" for name,value in worst.items())
    for width in (3600,600):
        for strategy in ("rerank","heap","merge"):
            lines.append(f"| {width//60}-minute live {strategy} | {report.fmt_s(report.live_total(data['live'],strategy,width))} |")
    text=TEMPLATE.replace("{{BATCH}}",winner).replace("{{TIMES}}","\n".join(lines))
    for key,method in (("HEAP10","Size-K Heap"),("FULL10","Full Sort (Hardened Quick Sort)")):
        text=text.replace("{{"+key+"}}",report.fmt_s(report.topk_time(data["topk"],method,100000,10000)))
    (ROOT/"viva_prep.md").write_text(text,encoding="utf-8")
    print("Updated viva_prep.md from current measured evidence.")


if __name__=="__main__": main()
