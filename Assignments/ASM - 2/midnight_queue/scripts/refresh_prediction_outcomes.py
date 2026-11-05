"""Reconcile outcomes with current evidence while preserving prior predictions."""
from __future__ import annotations
import csv
from pathlib import Path
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from midnight_queue.predictions import FIELDS


def reconcile():
    frames={p:pd.read_csv(ROOT/f"outputs/raw/{name}.csv")
            for p,name in (("C","tournament"),("D","topk"),("E","livefeed"))}
    path=ROOT/"prediction_log.csv"
    with path.open(newline="",encoding="utf-8") as f: rows=list(csv.DictReader(f))
    for r in rows:
        if r["problem"] not in frames: continue
        frame=frames[r["problem"]]
        key="strategy" if r["problem"]=="E" else "algorithm"
        if r["problem"]=="E":
            frame=frame.loc[frame.width_s.eq(int(r["width_s"]))]
        else:
            frame=frame.loc[frame.n.eq(int(r["n"]))&frame.condition.eq(r["condition"])]
            if r["problem"]=="D": frame=frame.loc[frame.k.eq(int(r["k"]))]
        med=frame.loc[frame.record_type.isin(["median","summary"])]
        dnfs=frame.loc[frame.record_type.eq("dnf"),key].tolist()
        if med.empty: continue
        fast=str(med.loc[med.median_s.idxmin(),key])
        slow=sorted(dnfs) if dnfs else [str(med.loc[med.median_s.idxmax(),key])]
        def normal(name):
            return "Full Sort" if name=="Full Sort (Hardened Quick Sort)" else name
        fast=normal(fast)
        slow=[normal(s) for s in slow]
        a=r["predicted_fastest"]==fast
        b=r["predicted_slowest"] in slow
        outcome=("both correct" if a and b else "fastest correct" if a else "slowest correct" if b else "both wrong")
        if len(dnfs)>1 and b:
            outcome="win OK; censored" if a else "loss censored"
        r.update(actual_fastest=fast,actual_slowest=" | ".join(slow),
                 outcome=outcome,
                 actual_notes=("Reconciled with revised measurements; original prediction/rationale/time preserved. "+
                     ("DNFs are censored at 300 s; their relative speeds are unknown." if dnfs else "")))
    temp=path.with_suffix(".csv.tmp")
    with temp.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    temp.replace(path)
    print(f"Reconciled {len(rows)} original prediction outcomes with current evidence.")


if __name__=="__main__": reconcile()
