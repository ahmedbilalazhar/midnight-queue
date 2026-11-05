"""Derive report claims from current measured evidence, not stale prose."""
from __future__ import annotations

import re
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
from reportlab.platypus import Paragraph, Table

ROOT=Path(__file__).resolve().parents[1]


def test_count():
    path=ROOT/"outputs/test_results.xml"
    if path.exists():
        return sum(int(s.get("tests",0)) for s in ET.parse(path).getroot().iter("testsuite"))
    raise RuntimeError("Run pytest with --junitxml=outputs/test_results.xml before generating the report")


def evidence(data):
    med=data["med"]
    batch=med.loc[med.n.eq(284807)&med.condition.isin(["C1","C2","C3","C4","C5"])]
    worst=batch.groupby("algorithm").filter(lambda g: len(g)==5).groupby("algorithm").median_s.max()
    batch_winner=worst.idxmin()
    top=data["topk"].loc[data["topk"].record_type.eq("median")].copy()
    for c in ("n","k","median_s"): top[c]=pd.to_numeric(top[c],errors="coerce")
    grid=top.loc[top.k.notna()].pivot(index=["n","condition","k"],columns="algorithm",values="median_s").dropna()
    regrets=grid.div(grid.min(axis=1),axis=0).max()
    wins=grid.idxmin(axis=1).value_counts()
    return batch_winner,worst,grid,regrets,wins


def refine_story(story,data,report):
    batch,worst,grid,regrets,wins=evidence(data)
    med,tour,ana=data["med"],data["tour"],data["ana"]
    top,live=data["topk"],data["live"]
    heap="Size-K Heap"
    selected=regrets.idxmin()
    n_tests=test_count()
    new=[]
    for item in story:
        if isinstance(item,Table) and item._cellvalues[0][:3]==["Job","Ship","Measured evidence"]:
            item._cellvalues[1][1:]=[batch,f"lowest full-size worst case: {report.fmt_s(worst[batch])}"]
            item._cellvalues[2][1:]=[selected,f"wins {int(wins.get(selected,0))}/{len(grid)} cells; max regret {regrets[selected]:.2f}x"]
            item._cellvalues[3][2]=f"{report.fmt_s(report.live_total(live,'heap',3600))} (60 min), {report.fmt_s(report.live_total(live,'heap',600))} (10 min)"
        if not isinstance(item,Paragraph):
            new.append(item)
            continue
        s=item.text
        if s.startswith("<b>Correctness and the C6 clash."):
            s=re.sub(r"suite has \d+ ","suite has "+str(n_tests)+" ",s)
            s=s.replace("clash; the official change request was not supplied, so no change is invented.",
                        "clash. The literal band-only comparator is retained and tested without secondary-field access.")
            s=s.replace("Exact sequence equality is impossible there without adding an illegal secondary key.",
                        "Band-only comparison does not define a unique row sequence; a full-key reference would impose extra criteria.")
        elif s.startswith("The package "):
            s=s.replace("median-of-three plus three-way partition",
                "median-of-three, three-way partition and a depth-limited in-place heap fallback")
            s += " The fallback guarantees worst-case O(n log n) time without altering the required naive Lomuto contender."
        elif s.startswith("Five full-sort contenders"):
            s=(f"Five contenders x six conditions x four sizes: {len(med)} valid medians and "
               f"{int(tour.record_type.eq('dnf').sum())} DNFs cover all 120 cells. "
               "Current completed cells were remeasured with five isolated repetitions, fresh copies outside the timer, "
               "and up to four concurrent cells using exclusive requested logical-CPU slots. "
               "Algorithm-only deadlines exclude preparation and verification. Historical DNF evidence for unchanged "
               "quadratic contenders is retained and identified in the raw notes. The shared legend applies to all six panels.")
        elif s.startswith("<b>A clash worth stating."):
            c1=med.loc[med.algorithm.eq("Insertion Sort")&med.condition.eq("C1")&med.n.eq(10000)].iloc[0]
            c4=med.loc[med.algorithm.eq("Insertion Sort")&med.condition.eq("C4")&med.n.eq(10000)].iloc[0]
            s=(f"<b>Theory versus measurement.</b> At 10k, insertion C1/C4 makes {int(c1.comparisons):,}/"
               f"{int(c4.comparisons):,} comparisons, with medians "
               f"{report.fmt_s(c1.median_s)}/{report.fmt_s(c4.median_s)}; counts match the inversion model.")
            h100=med.loc[med.algorithm.eq("Heap Sort")&med.condition.eq("C1")&med.n.eq(100000)].iloc[0]
            hfull=med.loc[med.algorithm.eq("Heap Sort")&med.condition.eq("C1")&med.n.eq(284807)].iloc[0]
            if h100.median_s>hfull.median_s:
                s+=(f" Clash: Heap/C1 falls from {report.fmt_s(h100.median_s)} at 100k "
                    f"to {report.fmt_s(hfull.median_s)} at full size while comparisons rise "
                    f"{report.fmt_count(h100.comparisons)} to {report.fmt_count(hfull.comparisons)}. "
                    "Power/scheduling was uncontrolled; growth conclusions use counts, and recommendations use these observed medians.")
        elif s.startswith("Table C4."):
            s=("Table C4. Largest completed sizes and explicit quadratic projections from their measured medians. "
               "Projections are not observations; DNFs have no median. All raw repetitions are in results.csv.")
        elif s.startswith("Three ways to produce the ordered K-queue"):
            s=("Three custom ways produce the same ordered queue: hardened full sort plus the K-prefix, "
               "a size-K heap with its worst retained case at the root, and a bounded binary-search insertion buffer. "
               "The heap is a min-heap of priority (band, Amount, -Time, -txn_id), equivalently a max-heap under the best-first comparator. "
               "The full sort is now measured at every K, including its actual prefix copy. Heap/buffer comparison loops "
               "are unchanged; their earlier five-run measurements remain identified by provenance. The grid is "
               "K={10,50,52,500,2068,5000,n/10}, both required sizes and C1/C2. Class is evaluated only after ranking.")
        elif s.startswith("<b>Fraud capture."):
            points=ana["fraud_capture"]["points"]
            winners=grid.idxmin(axis=1)
            corners=[f"{c}/{'full' if n==284807 else '100k'}/K={int(k)}"
                     for (n,c,k),name in winners.items() if name=="Bounded Insertion Buffer"]
            boundary=("The buffer wins only "+", ".join(corners)+
                      "; full sort wins no measured cell. " if corners and not wins.get("Full Sort (Hardened Quick Sort)",0)
                      else "The grid identifies winners at tested points, not a continuous crossover. ")
            s=(f"<b>Fraud capture.</b> K=52 captures {points['52']['frauds']} of 492 frauds; "
               f"the minimum half-capture queue is K={ana['fraud_capture']['k_half']:,}. "
               f"K=500 captures {points['500']['frauds']}, K=5,000 captures {points['5000']['frauds']}, "
               f"and K=10,000 captures {points['10000']['frauds']}. "
               f"Over {len(grid)} measured grid cells, the size-K heap wins {int(wins.get(heap,0))}; "
               f"its worst regret is {regrets[heap]:.2f}x. "+boundary+"A small computationally cheap queue can still miss every fraud: "
               "capacity and ranking quality must be justified separately.")
        elif s.startswith("The file is split into consecutive Time windows"):
            s=("Consecutive Time windows start at the first transaction. After each window, each strategy publishes "
               "the top K of all records seen: A re-ranks the prefix, B updates its maintained heap, C sorts the new "
               "window and merges its ranked candidates. Every publication is verified after its timer stops. "
               "All strategies were remeasured in this revision. Simulation totals and curves now use the same sum "
               "of algorithm-only window times; five individual totals are retained. Memory is measured separately.")
        elif s.startswith("Table E1 (left)"):
            s=("Table E1: median of five algorithm-only simulation totals. Table E2: peak extra memory in a separate "
               "trace. Shared windows are prepared before tracing. Retained measurement rows add O(w) bookkeeping "
               "to the streaming heap's O(K) algorithmic state. A timed-out strategy has no median.")
        elif s.startswith("Fig. E1."):
            s=("Fig. E1. Median cumulative algorithm time at each publication across five completed simulations; "
               "left: 60-minute windows, right: 10-minute windows, K=52. Only completed five-run strategies have curves.")
        elif s.startswith("Table P1."):
            s=("Table P1. Original forecasts with revised outcomes: 24 C rounds and 31 D/E/F rows. "
               "M5 is the crossover forecast discussed in M5. DNFs have no measured times and are not ordered among themselves.")
        elif s.startswith("<b>Artifacts."):
            res=pd.read_csv(ROOT/"results.csv")
            counts=res.record_type.value_counts()
            s=(f"<b>Artifacts.</b> results.csv contains {len(res):,} rows: "
               f"{counts.get('run',0):,} run/window rows, {counts.get('run_total',0)} simulation totals, "
               f"{counts.get('median',0)} medians, {counts.get('summary',0)} live summaries, "
               f"{counts.get('memory',0)} memory observations, {counts.get('dnf',0)} DNFs, "
               f"{counts.get('extrapolation',0)} labelled quadratic projections, "
               f"{counts.get('interrupted',0)} interrupted attempts, {counts.get('console_run',0)} single console demonstrations and "
               f"{counts.get('excluded_run',0)+counts.get('excluded_median',0)} excluded historical observations. "
               "The 55 original forecasts remain in prediction_log.csv. The executed notebook demonstrates "
               "scoring, ranking correctness and fraud capture; README.md supplies reproduction commands.")
        elif s.startswith("<b>M3"):
            s += (" For a tight 1:9 bound, the first floor(log_10 n) levels each contain total size n, "
                  "giving Omega(n log n); depth at most ceil(log_(10/9) n) gives O(n log n).")
        elif s.startswith("<b>M5"):
            h=report.topk_time(top,"Size-K Heap",100000,10000)
            f=report.topk_time(top,"Full Sort (Hardened Quick Sort)",100000,10000)
            s=(" <b>M5 — Top-K.</b> For 2&lt;=K&lt;=n: full sort plus prefix is O(n log n + K). "
               "Heap build is O(K), scan O(n+A log K) for A replacements, publication O(K log K); "
               "worst O(n log K + K log K). Buffer cost is O(K log K+n+A(K+log K)), worst O(nK). "
               "Under a random distinct-key permutation, P(accept i)=K/i and E[A]=K(H_n-H_K). "
               f"The original n=100k crossover forecast near K=10,000 "
               f"{'was wrong' if h<f else 'is supported at this measured point'} on C2: "
               f"heap {report.fmt_s(h)}, full sort {report.fmt_s(f)}. "
               "The ideal comparison (n+K)log K=n log n ignores constants and acceptance rate; "
               "the measured grid establishes no universal crossover.").strip()
        elif s.startswith("<b>M7"):
            s=("<b>M7 — Live feed.</b> For w equal-size windows and K>=2, worst-case costs are "
               "A: sum_j Theta((jn/w) log(jn/w))=Theta(nw log n); "
               "B: O(n log K+wK log K), including each ordered publication; "
               "C: O(n log(n/w)+wK). Comparing selection/sorting terms gives w≈n/K, "
               "about 5,477 windows here. This ignores constants and publication terms; "
               "it is a guide, not a measured crossover.")
        elif s.startswith("<b>M6"):
            a=ana["c6_band_analysis"]
            observations=[]
            for n in (1000,10000):
                measured=med.loc[med.algorithm.eq("Naive Quick Sort")&med.condition.eq("C6")&med.n.eq(n)].comparisons.iloc[0]
                exact=a[str(n)]["predicted_comparisons_exact_sequence"]
                if int(measured)!=int(exact):
                    raise ValueError("The exact C6 model does not match the recorded contender")
                observations.append(f"n={n:,}: model=measured={int(measured):,}")
            s=("<b>M6 — Naive Quick Sort on C6.</b> In a one-band block of size m, every last-pivot split "
               "removes one pivot and costs (m-1)+(m-2)+...+1=m(m-1)/2 comparisons. Summing these within-band "
               "pairs gives the group term; cross-band work depends on the actual pivot sequence. "
               f"The descending-band element model now matches exactly ({'; '.join(observations)}). "
               "The former model had used an ascending partition and was incorrect. Group-only predictions are "
               f"{report.fmt_count(a['100000']['predicted_comparisons_group_formula'])} at 100k and "
               f"{report.fmt_count(a['284807']['predicted_comparisons_group_formula'])} at full size, both DNFs. "
               "Three-way partitioning processes equal bands together; introspection protects against bad distinct-key splits.")
        elif s.startswith("<b>1. Overnight full-day batch"):
            observed="; ".join(f"{name}: {report.fmt_s(value)}" for name,value in worst.items())
            s=(f"<b>1. Overnight batch: ship {batch}.</b> Lowest worst completed time across C1–C5 "
               f"at full size wins. Worst medians: {observed}. Hardened Quick Sort now has an in-place heap "
               "fallback after twice the binary-log depth, guaranteeing O(n log n) worst-case time and O(log n) stack. "
               "The choice assumes the unknown next batch resembles the tested conditions; it is wrong for an already "
               f"ranked batch, where insertion sort takes {report.fmt_s(report.get_time(med,'Insertion Sort','C3',284807))}.")
        elif s.startswith("<b>2. Shift queue"):
            values="; ".join(f"{name}: max regret {ratio:.2f}x" for name,ratio in regrets.items())
            s=(f"<b>2. Shift queue: ship {selected}.</b> Across the {len(grid)} measured cells it minimises worst "
               f"slowdown relative to the winner: {values}. The recommendation assumes K is small relative to n and "
               "scores do not change after arrival. It can be wrong near full capacity, or for a fixed small corner "
               "where another method is a few milliseconds faster. Changing scores require an update/rebuild mechanism. "
               "The operational K=52 queue still contains no frauds; the half-capture capacity must be considered separately.")
        elif s.startswith("<b>3. Live refresh"):
            totals=[]
            chosen=[]
            for width in (3600,600):
                times={name:report.live_total(live,name,width) for name in ("rerank","heap","merge")}
                available={k:v for k,v in times.items() if v is not None}
                winner=min(available,key=available.get)
                chosen.append(winner)
                totals.append(f"{width//60} min: "+", ".join(f"{k} {report.fmt_s(v)}" for k,v in times.items()))
            strategy="maintained size-K heap" if all(c=="heap" for c in chosen) else "the measured winner for each window width"
            s=(f"<b>3. Live refresh: ship {strategy}.</b> Algorithm-only totals: {'; '.join(totals)}. "
               "A maintained heap touches new records once and avoids re-ranking history. This assumes immutable scores "
               "and windows large enough to amortise publication. Very small windows or K near n can favour window merge. "
               "The w≈n/K comparison is a rough guide, not a measured universal crossover.")
        elif s.startswith("Each prediction was written"):
            s += (" Original forecasts and their timestamps are preserved; outcomes now use revised measurements. "
                  "A vertical bar joins censored DNFs: their relative speeds are unknown. "
                  "The revised campaign's prospective C forecasts are stored separately in outputs/revision/predictions.csv.")
        elif s=="AI-use disclosure":
            new.append(Paragraph("Bonus: Analyst console",report.h2))
            new.append(Paragraph(
                "The local analyst console launches with <font face='Courier'>python scripts/run_console.py</font>. "
                "Choose any of the five full sorts or either Top-K selector, set K, input size and condition, "
                "then inspect every queued transaction by paginated risk band, Amount and Time. "
                "Each run displays algorithm-only time, comparisons and moves, verifies the ordered queue, "
                "and supports cancelling its isolated worker. Single demonstration measurements are logged separately "
                "from five-run medians. It uses the same algorithms and scoring as the report.",report.body))
        elif s.startswith("I used OpenCode"):
            s=("The original project records OpenCode with DeepSeek V4.1 Flash assistance for implementation, "
               "tests, experiment orchestration, analysis and drafting. OpenAI Codex revised visualisations, "
               "notebook presentation, compliance checks and the editable LaTeX report; then hardened quicksort, "
               "corrected the C6 model and timing scopes, expanded tests, reran affected experiments, "
               "and added the analyst console and viva practice materials. "
               "Historical measurements remain archived, including excluded over-limit C5 insertion runs. "
               "The student must verify the submission and be able to explain and modify it in the viva.")
        new.append(Paragraph(s,item.style))
    return new
