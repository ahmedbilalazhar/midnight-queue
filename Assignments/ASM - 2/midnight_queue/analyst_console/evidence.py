"""Read compact dashboard evidence from saved, measured project artifacts."""
import csv
import json
from . import ROOT


def load_runs(root=ROOT,limit=10):
    """Return the most recent recorded console demonstrations, newest first."""
    path=root/"outputs/raw/console.csv"
    if not path.exists(): return []
    with path.open(newline="",encoding="utf-8") as f:
        rows=[row for row in csv.DictReader(f) if row.get("record_type")=="console_run"]
    runs=[]
    def number(value,cast):
        try: return cast(float(value)) if value else None
        except (TypeError,ValueError): return None
    for row in rows[-limit:][::-1]:
        notes=row.get("notes","")
        stamp=notes.rsplit("; ",1)[-1].strip() if "; " in notes else ""
        runs.append(dict(algorithm=row["algorithm"],condition=row["condition"],
                         n=number(row.get("n"),int),k=number(row.get("k"),int),
                         seconds=number(row.get("elapsed_s"),float),
                         comparisons=number(row.get("comparisons"),int),
                         moves=number(row.get("moves"),int),timestamp=stamp,
                         verified=row.get("correct")=="True"))
    return runs


def load_evidence(root=ROOT):
    analysis=json.loads((root/"outputs/analysis/data_analysis.json").read_text(encoding="utf-8"))
    def read(name):
        with (root/"outputs/raw"/name).open(newline="",encoding="utf-8") as f:
            return list(csv.DictReader(f))
    tournament=[]
    batch={}
    for row in read("tournament.csv"):
        if row["record_type"] not in ("median","dnf"): continue
        entry=dict(algorithm=row["algorithm"],condition=row["condition"],n=int(row["n"]),
                   seconds=float(row["median_s"]) if row["record_type"]=="median" else None,
                   comparisons=int(float(row["comparisons"])) if row["comparisons"] else None,
                   moves=int(float(row["moves"])) if row["moves"] else None)
        tournament.append(entry)
        if entry["n"]==284807 and entry["condition"] in ("C1","C2","C3","C4","C5") and entry["seconds"] is not None:
            batch.setdefault(entry["algorithm"],{})[entry["condition"]]=entry["seconds"]
    worst={name:max(cells.values()) for name,cells in batch.items() if len(cells)==5}
    best=min(worst,key=worst.get) if worst else None
    grid={}
    for row in read("topk.csv"):
        if row["record_type"]=="median" and row["k"]:
            grid.setdefault((row["n"],row["condition"],row["k"]),{})[row["algorithm"]]=float(row["median_s"])
    wins={};regrets={};cells=0
    for values in grid.values():
        if len(values)!=3: continue
        cells+=1
        winner=min(values,key=values.get)
        wins[winner]=wins.get(winner,0)+1
        minimum=min(values.values())
        for name,value in values.items(): regrets[name]=max(regrets.get(name,1),value/minimum)
    live=[dict(strategy=r["strategy"],width=int(r["width_s"]),seconds=float(r["median_s"]) if r["record_type"]=="summary" else None)
          for r in read("livefeed.csv") if r["record_type"] in ("summary","dnf")]
    p=analysis["profile"]
    return dict(profile={k:p[k] for k in ("rows","fraud_count","band_counts","fraud_by_band")},
                capture=analysis["fraud_capture"],tournament=tournament,live=live,
                recommendations=dict(batch=best,batch_seconds=worst.get(best),
                    queue=min(regrets,key=regrets.get) if regrets else None,
                    wins=wins,regrets=regrets,comparison_cells=cells),
                provenance="Saved five-run benchmark medians; separate from interactive single runs.")
