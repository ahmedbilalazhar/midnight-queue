"""Measure an actual demo change request without rewriting frozen benchmarks."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analyst_console import ROOT
from analyst_console.engine import ALGORITHMS,CONDITIONS,prepare_records,run_worker,DeadlineError
from midnight_queue.config import CONFIG
from midnight_queue.results import RESULT_FIELDS,result_row
from midnight_queue.environment import environment_info


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-file",type=Path,required=True,help="Actual official request text")
    parser.add_argument("--prediction",required=True,help="Your prediction and reason, before measuring")
    parser.add_argument("--job",choices=("queue","batch","live"),default="queue")
    parser.add_argument("--algorithm",default="Size-K Heap")
    parser.add_argument("--n",type=int,default=1000)
    parser.add_argument("--condition",choices=CONDITIONS,default="C1")
    parser.add_argument("--k",type=int,default=CONFIG.k)
    parser.add_argument("--width",type=int,default=3600)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    if not args.request_file.exists() or not args.request_file.read_text(encoding="utf-8").strip():
        parser.error("Supply the actual official request; no request is invented")
    if not args.prediction.strip(): parser.error("Write a prediction before running")
    allowed=("heap","merge","rerank") if args.job=="live" else ALGORITHMS
    if args.algorithm not in allowed: parser.error("Algorithm must be one of "+", ".join(allowed))
    if args.job=="batch" and args.algorithm not in ALGORITHMS[:5]:
        parser.error("A batch job requires a full-sort contender")
    k=args.n if args.job=="batch" else args.k
    if not 1<=args.n<=CONFIG.sizes[-1] or not 1<=k<=args.n or args.width<=0:
        parser.error("Require 1<=K<=n<=284807 and positive window width")
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder=args.output or ROOT/"outputs/demo"/stamp
    if folder.exists() and any(folder.iterdir()): parser.error("Choose an empty output folder to preserve prior evidence")
    folder.mkdir(parents=True,exist_ok=True)
    metadata=dict(created_utc=stamp,official_request=args.request_file.read_text(encoding="utf-8"),
        request_sha256=hashlib.sha256(args.request_file.read_bytes()).hexdigest(),
        prediction=args.prediction,seed=CONFIG.seed,n=args.n,k=k,condition=args.condition,
        job=args.job,algorithm=args.algorithm,width=args.width,environment=environment_info(ROOT),
        note="Real demo measurements, separate from the report's original campaign. Interpret the official constraint before selecting these parameters.",
        source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/"src/midnight_queue").glob("*.py")})
    (folder/"request_and_prediction.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    records=prepare_records(args.n,args.condition)
    rows=[]
    base=dict(problem="G",experiment="demo_change_request",algorithm=args.algorithm,
              condition=args.condition,n=args.n,k=k,width_s=args.width if args.job=="live" else "")
    for repeat in range(1,6):
        try:
            result=run_worker(records,args.algorithm,k,mode=args.job,width=args.width)
        except DeadlineError:
            rows.append(result_row(**base,record_type="dnf",repeat=repeat,dnf=True,dnf_reason="300 s algorithm deadline"))
            break
        rows.append(result_row(**base,record_type="run",repeat=repeat,elapsed_s=result["elapsed_s"],
            comparisons=result["comparisons"],moves=result["moves"],correct=True,dnf=False,queue_size=result["queue_size"]))
        if "publications" in result:
            (folder/f"publications_repeat_{repeat}.json").write_text(json.dumps(result["publications"],indent=2),encoding="utf-8")
        print(f"Repeat {repeat}: {result['elapsed_s']:.6f} s, {result['comparisons']:,} comparisons",flush=True)
        with (folder/"measurements.csv").open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=RESULT_FIELDS);writer.writeheader();writer.writerows(rows)
    completed=[r for r in rows if r["record_type"]=="run"]
    if len(completed)==5:
        if len({(r["comparisons"],r["moves"]) for r in completed})!=1:
            raise RuntimeError("Counts changed between identical runs")
        rows.append(result_row(**base,record_type="median",median_s=statistics.median(r["elapsed_s"] for r in completed),
            run_count=5,comparisons=completed[0]["comparisons"],moves=completed[0]["moves"],correct=True,dnf=False))
    with (folder/"measurements.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=RESULT_FIELDS);writer.writeheader();writer.writerows(rows)
    print(f"Saved actual request, prior prediction, source hashes and measurements to {folder}")


if __name__=="__main__": main()
