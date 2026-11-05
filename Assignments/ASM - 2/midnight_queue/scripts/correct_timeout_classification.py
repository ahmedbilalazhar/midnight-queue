"""Apply the assignment's 300 s rule to historical completed observations.

Original numeric values and predictions are preserved, with invalidated rows
explicitly labelled excluded_run/excluded_median. A DNF gets no invented time.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "src"))
from midnight_queue.results import RESULT_FIELDS, result_row


def main():
    path = ROOT / "outputs/raw/tournament.csv"
    with path.open(newline="",encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    bad = {}
    for row in rows:
        if row["record_type"] == "run" and float(row["elapsed_s"]) > 300:
            key = (row["algorithm"],row["condition"],row["n"])
            bad.setdefault(key,[]).append(float(row["elapsed_s"]))
    if not bad:
        print("Recorded tournament already follows the 300 s classification rule.")
        return
    audit = ROOT / "outputs/audit"
    audit.mkdir(parents=True,exist_ok=True)
    for source in (path,ROOT/"results.csv",ROOT/"prediction_log.csv"):
        target = audit / f"{source.stem}_before_timeout_fix.csv"
        if not target.exists():
            shutil.copy2(source,target)
    changed = []
    for key,seconds in bad.items():
        algorithm,condition,n = key
        for row in rows:
            if (row["algorithm"],row["condition"],row["n"]) == key and row["record_type"] in ("run","median"):
                row["record_type"] = "excluded_" + row["record_type"]
                row["notes"] = (row["notes"]+"; excluded from official results: cell contains "
                                "runs over 300 s; historical values retained for audit").strip("; ")
        rows.append(result_row(
            record_type="dnf",problem="C",experiment="full_sort",
            prediction_id=f"tournament-{condition}-n{n}",algorithm=algorithm,condition=condition,n=n,
            dnf=True,dnf_reason="historical completed run exceeded 300 s; reclassified under assignment rule",
            notes="Not a new watchdog attempt. Historical parallel runner lacked a per-run watchdog; "
                  "original observations remain as excluded rows and in outputs/audit/.",
        ))
        changed.append({"algorithm":algorithm,"condition":condition,"n":int(n),
                        "observed_over_limit_seconds":seconds})
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w",newline="",encoding="utf-8") as stream:
        writer = csv.DictWriter(stream,fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)
    (audit/"timeout_correction.json").write_text(json.dumps({
        "reason":"Assignment ground rule 5: any single run above 300 seconds is DNF.",
        "changed_cells":changed,
        "original_tournament_sha256":hashlib.sha256((audit/"tournament_before_timeout_fix.csv").read_bytes()).hexdigest(),
        "values_preserved":True,"new_benchmark_measurement":False,
    },indent=2),encoding="utf-8")
    print(f"Reclassified {len(bad)} over-limit cell(s); numeric observations preserved.")


if __name__ == "__main__":
    main()
