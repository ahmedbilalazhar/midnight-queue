"""Refresh affected experiments without fabricating or hiding historical data.

The original campaign is archived. Every new timed cell gets five independent
runs. Existing genuine DNFs for unchanged quadratic algorithms remain valid;
no old median is retained for a changed contender. Predictions are committed
before starting the revised campaign. Staging CSVs permit safe resumption.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from queue import Queue
import shutil
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"scripts")]
from midnight_queue.config import CONFIG
from midnight_queue.results import RESULT_FIELDS, result_row
from midnight_queue.sorting import SORT_ALGORITHMS, STABILITY
from midnight_queue.predictions import tournament_prediction
from run_tournament import _run_worker
from run_topk import _run as topk_worker
from run_livefeed import _run as live_worker

REV=ROOT/"outputs/revision"
RAW=ROOT/"outputs/raw"


def read(path):
    if not path.exists(): return []
    with path.open(newline="",encoding="utf-8") as f: return list(csv.DictReader(f))


def write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".csv.tmp")
    with temp.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def initialize():
    REV.mkdir(parents=True,exist_ok=True)
    meta=REV/"campaign.json"
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT/"src/midnight_queue").glob("*.py")
            if p.name not in ("plotting.py","visuals.py")}
    if meta.exists():
        old=json.loads(meta.read_text())
        if old["source_hashes"] != hashes:
            raise RuntimeError("Algorithm sources changed during staged measurement; archive staging before restarting.")
    else:
        from midnight_queue.environment import environment_info
        meta.write_text(json.dumps({"created_utc":datetime.now(timezone.utc).isoformat(),
                 "source_hashes":hashes,"environment":environment_info(ROOT),
                 "seed":CONFIG.seed,"protocol":"five repetitions; isolated timed workers; exclusive requested CPU slots per C cell",
                 "inherited_dnfs":"Only historical DNF cells for unchanged Insertion/Naive Quick Sort."},indent=2))
    predictions=REV/"predictions.csv"
    if not predictions.exists():
        with predictions.open("w",newline="",encoding="utf-8") as f:
            writer=csv.writer(f)
            writer.writerow(["condition","n","predicted_fastest","predicted_slowest","rationale","created_utc"])
            for n in CONFIG.sizes:
                for c in (f"C{i}" for i in range(1,7)):
                    fast,slow,why=tournament_prediction(c,n)
                    writer.writerow([c,n,fast,slow,why+" Revised hardened sort has a depth-limited heap fallback.",
                                     datetime.now(timezone.utc).isoformat()])
    return json.loads((ROOT/"outputs/cache/manifest.json").read_text())


def note():
    return "deep-hardening revision; source hashes/environment in outputs/revision/campaign.json"


def tournament(manifest,workers):
    path=REV/"tournament.csv"
    rows=read(path) if path.exists() else [
        r for r in read(RAW/"tournament.csv")
        if r["record_type"] in ("dnf","excluded_run","excluded_median") or
           (r["record_type"]=="memory" and r["algorithm"]!="Hardened Quick Sort")]
    done={(r["algorithm"],r["condition"],int(r["n"])) for r in rows if r["record_type"] in ("median","dnf")}
    tasks=[(name,c,n) for n in CONFIG.sizes for c in (f"C{i}" for i in range(1,7))
           for name in SORT_ALGORITHMS if (name,c,n) not in done]
    # Longest-first reduces the tail without changing any data or timer.
    tasks.sort(key=lambda t:(t[0]=="Insertion Sort",t[0]=="Naive Quick Sort",t[2]),reverse=True)
    previous={}
    for task in tasks:
        name,c,n=task
        previous[task]=[r for r in rows if r["record_type"]=="run" and r["algorithm"]==name
                        and r["condition"]==c and int(r["n"])==n]
    import psutil
    allowed=psutil.Process().cpu_affinity() if hasattr(psutil.Process(),"cpu_affinity") else list(range(os.cpu_count() or 1))
    chosen=[c for c in (0,2,4,6) if c in allowed]
    if not chosen: chosen=allowed[:workers]
    slots=Queue()
    for cpu in chosen[:workers]: slots.put(cpu)
    def measure(task):
        name,c,n=task
        cpu=slots.get()
        samples=[]
        try:
            cache=ROOT/manifest["sizes"][str(n)]["conditions"][c]["cache_file"]
            for repeat in range(len(previous[task])+1,6):
                payload=_run_worker(cache,name,300,False,cpu)
                if payload is None:
                    return task,samples,True
                if not payload["correct"]: raise AssertionError(f"Incorrect {task}")
                if samples and any(payload[k]!=samples[0][k] for k in ("comparisons","moves")):
                    raise AssertionError(f"Non-deterministic counters: {task}")
                samples.append(payload)
            return task,samples,False
        finally: slots.put(cpu)
    with ThreadPoolExecutor(max_workers=min(workers,len(chosen))) as pool:
        for completed,future in enumerate(as_completed([pool.submit(measure,t) for t in tasks]),1):
            (name,c,n),samples,dnf=future.result()
            base=dict(problem="C",experiment="full_sort",prediction_id=f"tournament-{c}-n{n}",
                      algorithm=name,condition=c,n=n,stable=STABILITY[name],notes=note())
            for i,s in enumerate(samples,len(previous[(name,c,n)])+1):
                rows.append(result_row(**base,record_type="run",repeat=i,elapsed_s=s["elapsed_s"],
                                       comparisons=s["comparisons"],moves=s["moves"],correct=True,dnf=False))
            all_samples=previous[(name,c,n)]+samples
            if dnf:
                rows.append(result_row(**base,record_type="dnf",repeat=len(all_samples)+1,dnf=True,
                                       dnf_reason="exceeded 300 s measured-run deadline"))
                status="DNF"
            else:
                seconds=statistics.median(float(s["elapsed_s"]) for s in all_samples)
                rows.append(result_row(**base,record_type="median",median_s=seconds,run_count=5,
                                       comparisons=all_samples[0]["comparisons"],moves=all_samples[0]["moves"],
                                       correct=True,dnf=False))
                status=f"{seconds:.4f}s"
            write(path,rows)
            print(f"C [{completed}/{len(tasks)}] {name} {c} n={n:,}: {status}",flush=True)
    # Only the changed hardened contender needs its previous memory rows replaced.
    for c in (f"C{i}" for i in range(1,7)):
        if any(r["record_type"]=="memory" and r["algorithm"]=="Hardened Quick Sort" and r["condition"]==c for r in rows):
            continue
        cache=ROOT/manifest["sizes"]["10000"]["conditions"][c]["cache_file"]
        payload=_run_worker(cache,"Hardened Quick Sort",300,True)
        if payload is None or not payload["correct"]: raise RuntimeError(f"Memory run failed: {c}")
        rows.append(result_row(record_type="memory",problem="C",experiment="full_sort",
                    algorithm="Hardened Quick Sort",condition=c,n=10000,correct=True,stable="unstable",
                    peak_extra_bytes=payload["peak_extra_bytes"],comparisons=payload["comparisons"],
                    moves=payload["moves"],notes=note()))
        write(path,rows)
    shutil.copy2(path,RAW/"tournament.csv")


def topk(manifest):
    path=REV/"topk.csv"
    rows=read(path) if path.exists() else [
        r for r in read(RAW/"topk.csv") if r["algorithm"]!="Full Sort (Hardened Quick Sort)"]
    # Fresh full-sort measurements at EACH K: no unmeasured prefix-cost reuse.
    for n in (100000,284807):
        for c in ("C1","C2"):
            cache=ROOT/manifest["sizes"][str(n)]["conditions"][c]["cache_file"]
            for k in dict.fromkeys((10,50,52,500,5000,n//10,2068)):
                if any(r["record_type"] in ("median","dnf") and r["algorithm"]=="Full Sort (Hardened Quick Sort)"
                       and int(r["n"])==n and r["condition"]==c and int(r["k"])==k for r in rows):
                    continue
                samples=[r for r in rows if r["record_type"]=="run" and r["algorithm"]=="Full Sort (Hardened Quick Sort)"
                         and int(r["n"])==n and r["condition"]==c and int(r["k"])==k]
                base=dict(problem="D",experiment="topk",algorithm="Full Sort (Hardened Quick Sort)",
                          condition=c,n=n,k=k,stable="unstable",notes=note()+"; includes actual K-prefix output")
                for repeat in range(len(samples)+1,6):
                    s=topk_worker(cache,"Full Sort",k,300,False)
                    if s is None: break
                    if not s["correct"]: raise AssertionError(f"Incorrect Top-K {n}/{c}/{k}")
                    samples.append(s)
                    rows.append(result_row(**base,record_type="run",repeat=repeat,elapsed_s=s["elapsed_s"],
                                comparisons=s["comparisons"],moves=s["moves"],correct=True,dnf=False))
                if len(samples)==5:
                    rows.append(result_row(**base,record_type="median",median_s=statistics.median(float(s["elapsed_s"]) for s in samples),
                                run_count=5,comparisons=samples[0]["comparisons"],moves=samples[0]["moves"],correct=True,dnf=False))
                else:
                    rows.append(result_row(**base,record_type="dnf",dnf=True,dnf_reason="exceeded 300 s measured-run deadline"))
                write(path,rows)
                print(f"D full sort {c} n={n:,} K={k}: {len(samples)} completed runs",flush=True)
    shutil.copy2(path,RAW/"topk.csv")


def live(manifest):
    path=REV/"livefeed.csv"
    # Timing scope is corrected for ALL strategies, so all live measurements
    # are refreshed instead of mixing outer-wall and algorithm-only totals.
    rows=read(path)
    cache=ROOT/manifest["sizes"]["284807"]["conditions"]["C1"]["cache_file"]
    for width in (3600,600):
        expected=ROOT/f"outputs/cache/live_expected_{width}.pkl"
        for strategy in ("heap","merge","rerank"):
            if any(r["record_type"] in ("summary","dnf") and int(r["width_s"])==width
                   and r["strategy"]==strategy for r in rows): continue
            totals=[float(r["elapsed_s"]) for r in rows if r["record_type"]=="run_total"
                    and int(r["width_s"])==width and r["strategy"]==strategy]
            base=dict(problem="E",strategy=strategy,n=284807,k=52,width_s=width,notes=note())
            for repeat in range(len(totals)+1,6):
                payload=live_worker(cache,expected,strategy,width,300,False)
                if payload is None: break
                if not payload["correct"]: raise AssertionError("Live publication differs from reference")
                totals.append(payload["elapsed_s"])
                for r in payload["rows"]:
                    rows.append(result_row(**base,record_type="run",experiment="livefeed",repeat=repeat,
                         window=r["window"],elapsed_s=r["elapsed_s"],comparisons=r["comparisons"],
                         moves=r["moves"],correct=r["correct"],dnf=False,seen=r["seen"],
                         window_records=r["window_records"],cumulative_s=r["cumulative_s"],queue_size=r["queue_size"]))
                # Persist the independently measured total of EACH repetition.
                rows.append(result_row(**base,record_type="run_total",experiment="livefeed_total",repeat=repeat,
                                        elapsed_s=payload["elapsed_s"],correct=True,dnf=False))
                write(path,rows)
                print(f"E {width//60}min {strategy} repeat {repeat}: {payload['elapsed_s']:.4f}s",flush=True)
            if len(totals)==5:
                rows.append(result_row(**base,record_type="summary",experiment="livefeed_summary",
                            median_s=statistics.median(totals),run_count=5,correct=True,dnf=False))
                memory=live_worker(cache,expected,strategy,width,1800,True)
                if memory is None or not memory["correct"]: raise RuntimeError("Live memory measurement failed")
                rows.append(result_row(**base,record_type="memory",experiment="livefeed",
                            peak_extra_bytes=memory["peak_extra_bytes"],correct=True))
            else:
                rows.append(result_row(**base,record_type="dnf",experiment="livefeed",repeat=len(totals)+1,
                            dnf=True,dnf_reason="exceeded 300 s measured-simulation deadline"))
            write(path,rows)
    shutil.copy2(path,RAW/"livefeed.csv")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--stage",choices=("all","tournament","topk","live"),default="all")
    p.add_argument("--workers",type=int,default=4)
    args=p.parse_args()
    if not 1<=args.workers<=4: p.error("workers must be between 1 and 4")
    manifest=initialize()
    if args.stage in ("all","tournament"): tournament(manifest,args.workers)
    if args.stage in ("all","topk"): topk(manifest)
    if args.stage in ("all","live"): live(manifest)
    print("Refreshed requested measurements; historical campaign is archived.",flush=True)


if __name__=="__main__":
    from benchmark_host import awake_host
    with awake_host(): main()
