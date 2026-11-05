"""Console jobs use the actual custom algorithms in disposable workers."""
from __future__ import annotations
import csv
from datetime import datetime,timezone
from functools import lru_cache
import json
from pathlib import Path
import pickle
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Lock,Event

from . import ROOT
from midnight_queue.config import CONFIG,DEFAULT_DATA_PATH
from midnight_queue.conditions import build_conditions
from midnight_queue.data import load_dataset,sample_records
from midnight_queue.results import RESULT_FIELDS,result_row
from midnight_queue.sorting import SORT_ALGORITHMS

ALGORITHMS=tuple(SORT_ALGORITHMS)+("Size-K Heap","Bounded Insertion Buffer")
CONDITIONS=("C1","C2","C3","C4","C5")


class BusyError(RuntimeError): pass
class CancelledError(RuntimeError): pass
class DeadlineError(RuntimeError): pass


def validate_request(params):
    if not isinstance(params,dict): raise ValueError("A JSON object is required")
    if params.get("algorithm") not in ALGORITHMS: raise ValueError("Choose a listed algorithm")
    if params.get("condition") not in CONDITIONS: raise ValueError("Choose C1 to C5")
    n,k=params.get("n"),params.get("k")
    if type(n) is not int or n not in CONFIG.sizes: raise ValueError("Choose a required input size")
    if type(k) is not int or not 1<=k<=n: raise ValueError("K must be a whole number from 1 to the input size")
    request_id=params.get("request_id")
    if not isinstance(request_id,str) or not 1<=len(request_id)<=80: raise ValueError("Missing run identifier")
    return params


@lru_cache(maxsize=1)
def official_records():
    return load_dataset(DEFAULT_DATA_PATH).records


def prepare_records(n,condition):
    # Full-file standardisation always precedes sampling and construction.
    sample=sample_records(official_records(),n,CONFIG.seed)
    return build_conditions(sample,CONFIG.seed)[condition].records


def run_worker(records,algorithm,k,*,timeout=300,started=None,mode="queue",width=3600):
    """Input transfer, initial copying and verification are outside the timer."""
    with TemporaryDirectory(prefix="midnight-console-") as temp:
        job=Path(temp)/"input.pkl"
        with job.open("wb") as f:
            pickle.dump(dict(records=records,algorithm=algorithm,k=k,timeout=timeout,mode=mode,width=width),f)
        process=subprocess.Popen([sys.executable,"-m","analyst_console.worker",str(job)],
                                 cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding="utf-8")
        try:
            if started: started(process)
            try:
                out,err=process.communicate(timeout=timeout+120)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("Worker preparation/verification exceeded its envelope; no algorithm DNF inferred") from exc
            if process.returncode==124: raise DeadlineError(f"DNF: algorithm exceeded {timeout:g} seconds")
            if process.returncode: raise RuntimeError(err[-1200:] or "Worker stopped without a result")
            result=json.loads(out)
            if result["elapsed_s"]>timeout: raise DeadlineError(f"DNF: algorithm exceeded {timeout:g} seconds")
            if not result["correct"]: raise RuntimeError("Queue differs from the trusted reference")
            return result
        finally:
            if process.poll() is None: process.kill()
            process.communicate()


class ConsoleService:
    def __init__(self,prepare=prepare_records,log_path=ROOT/"outputs/raw/console.csv"):
        self.prepare=prepare
        self.log_path=log_path
        self.lock=Lock()
        self.request_id=None
        self.process=None
        self.cancelled=Event()

    def cancel(self,request_id):
        with self.lock:
            if self.request_id!=request_id or request_id is None: return False
            self.cancelled.set()
            if self.process and self.process.poll() is None: self.process.terminate()
            return True

    def run(self,params):
        validate_request(params)
        with self.lock:
            if self.request_id is not None: raise BusyError("Another queue is running. Wait or cancel that run.")
            self.request_id=params["request_id"]
            self.cancelled.clear()
        def started(process):
            with self.lock:
                self.process=process
                if self.cancelled.is_set(): process.terminate()
        try:
            records=self.prepare(params["n"],params["condition"])
            if self.cancelled.is_set(): raise CancelledError("Run cancelled; no timing result recorded")
            try:
                result=run_worker(records,params["algorithm"],params["k"],started=started)
            except Exception:
                if self.cancelled.is_set(): raise CancelledError("Run cancelled; no timing result recorded") from None
                raise
            result.update(algorithm=params["algorithm"],condition=params["condition"],n=len(records),k=params["k"])
            if self.log_path:
                self.log_path.parent.mkdir(parents=True,exist_ok=True)
                exists=self.log_path.exists()
                with self.log_path.open("a",newline="",encoding="utf-8") as f:
                    writer=csv.DictWriter(f,fieldnames=RESULT_FIELDS)
                    if not exists: writer.writeheader()
                    writer.writerow(result_row(record_type="console_run",problem="Bonus",experiment="analyst_console",
                        algorithm=params["algorithm"],condition=params["condition"],n=len(records),k=params["k"],
                        elapsed_s=result["elapsed_s"],comparisons=result["comparisons"],moves=result["moves"],
                        correct=True,dnf=False,queue_size=result["queue_size"],
                        notes=f"single demo run; excluded from five-run medians; {datetime.now(timezone.utc).isoformat()}"))
            return result
        finally:
            with self.lock:
                self.process=None
                self.request_id=None
