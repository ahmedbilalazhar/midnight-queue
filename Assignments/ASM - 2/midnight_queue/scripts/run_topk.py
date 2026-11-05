"""Run Problem D: full sort vs size-K heap vs bounded insertion buffer."""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

from midnight_queue.config import CONFIG, PROJECT_ROOT
from midnight_queue.predictions import add_prediction, update_outcome
from midnight_queue.results import RESULT_FIELDS, result_row

CONDITIONS = ("C1", "C2")
SIZES = (100_000, 284_807)
METHODS = ("Size-K Heap", "Bounded Insertion Buffer")


def _read(path: Path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    if path.exists():
        path.with_suffix(".csv.bak").write_bytes(path.read_bytes())
    os.replace(tmp, path)


def _k_values(n: int, extra: list[int] | None = None) -> list[int]:
    values = [10, 50, CONFIG.k, 500, 5000, n // 10]
    values.extend(extra or [])
    # preserve order while removing duplicates
    return list(dict.fromkeys(v for v in values if 0 < v <= n))


def _run(cache: Path, method: str, k: int, timeout: int, memory: bool):
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "topk_worker.py"),
        "--cache",
        str(cache),
        "--method",
        method,
        "--k",
        str(k),
        "--timeout",
        str(timeout),
    ]
    if memory:
        command.append("--memory")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout+120,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Worker exceeded its preparation/verification envelope; algorithm DNF is unproven") from exc
    if completed.returncode==124:
        return None
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-2000:])
    payload=json.loads(completed.stdout.strip().splitlines()[-1])
    if not memory and payload["elapsed_s"]>timeout:
        return None
    if not payload["correct"]:
        raise RuntimeError("Top-K result differs from the trusted reference")
    return payload


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--repeats",type=int,default=5)
    parser.add_argument("--timeout",type=int,default=300)
    parser.add_argument("--sizes",default="100000,284807")
    parser.add_argument("--conditions",default="C1,C2")
    parser.add_argument("--extra-k",default="")
    parser.add_argument("--memory",action="store_true")
    parser.add_argument("--no-memory",dest="memory",action="store_false")
    args=parser.parse_args()
    if args.repeats<1 or args.timeout<=0: parser.error("positive repeats and timeout required")
    manifest=json.loads((PROJECT_ROOT/"outputs/cache/manifest.json").read_text())
    path=PROJECT_ROOT/"outputs/raw/topk.csv"
    rows=_read(path)
    extra=[int(x) for x in args.extra_k.split(",") if x]
    methods={"Full Sort (Hardened Quick Sort)":"Full Sort",**{m:m for m in METHODS}}
    for n in map(int,args.sizes.split(",")):
        for condition in args.conditions.split(","):
            cache=PROJECT_ROOT/manifest["sizes"][str(n)]["conditions"][condition]["cache_file"]
            for k in _k_values(n,extra):
                add_prediction(PROJECT_ROOT/"prediction_log.csv",
                    prediction_id=f"topk-{condition}-n{n}-k{k}",problem="D",
                    round_id=f"D_{condition}_n{n}_k{k}",condition=condition,n=n,k=k,
                    predicted_fastest="Size-K Heap" if k<=5000 else "Full Sort",
                    predicted_slowest="Bounded Insertion Buffer",
                    rationale="Heap limits retained state to K; buffer shifting grows with K; full sort becomes competitive near full capacity.")
                for name,worker_name in methods.items():
                    def same(r):
                        return (r.get("experiment")=="topk" and r.get("algorithm")==name
                                and r.get("condition")==condition and str(r.get("n"))==str(n)
                                and str(r.get("k"))==str(k))
                    base=dict(problem="D",experiment="topk",algorithm=name,condition=condition,n=n,k=k,
                              notes="complete ordered queue, including actual prefix extraction for full sort")
                    finished=any(same(r) and r["record_type"] in ("median","dnf") for r in rows)
                    if not finished:
                        # An interrupted cell resumes from persisted repetitions.
                        samples=[r for r in rows if same(r) and r["record_type"]=="run"]
                        for repeat in range(len(samples)+1,args.repeats+1):
                            try:
                                payload=_run(cache,worker_name,k,args.timeout,False)
                            except Exception:
                                _write(path,rows)
                                raise
                            if payload is None:
                                rows.append(result_row(**base,record_type="dnf",repeat=repeat,dnf=True,
                                    dnf_reason=f"exceeded {args.timeout}s algorithm-only deadline"))
                                break
                            if samples and any(int(float(samples[0][key]))!=payload[key] for key in ("comparisons","moves")):
                                raise RuntimeError("Counters differ across repetitions")
                            row=result_row(**base,record_type="run",repeat=repeat,correct=True,dnf=False,
                                           **{key:payload[key] for key in ("elapsed_s","comparisons","moves")})
                            rows.append(row)
                            samples.append(row)
                            _write(path,rows)
                            print(f"{condition} n={n} K={k} {name} rep {repeat}: {payload['elapsed_s']:.4f}s",flush=True)
                        if len(samples)==args.repeats:
                            rows.append(result_row(**base,record_type="median",run_count=len(samples),
                                median_s=statistics.median(float(r["elapsed_s"]) for r in samples),
                                comparisons=samples[0]["comparisons"],moves=samples[0]["moves"],correct=True,dnf=False))
                        _write(path,rows)
                    if args.memory and not any(same(r) and r["record_type"]=="memory" for r in rows):
                        mem=_run(cache,worker_name,k,args.timeout,True)
                        if mem is None: raise RuntimeError("Memory worker did not complete")
                        rows.append(result_row(**base,record_type="memory",peak_extra_bytes=mem["peak_extra_bytes"],correct=True))
                        _write(path,rows)
    from refresh_prediction_outcomes import reconcile
    reconcile()


if __name__=="__main__": main()
