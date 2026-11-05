"""Check measurement boundaries and failures independently of ranking output."""
from pathlib import Path
import importlib
import os
import subprocess
import sys
import json

import pytest

from midnight_queue import livefeed


def test_live_total_equals_window_work_not_verification_wall_time(monkeypatch,make_txn):
    records=[make_txn(1,time=0),make_txn(2,time=100)]
    expected=livefeed.build_expected_queues(records,100,1)
    ticks=iter([0.,1.,3.,100.,104.,200.])
    monkeypatch.setattr(livefeed.time,"perf_counter",lambda: next(ticks))
    result=livefeed.run_live_feed(records,100,1,"heap",expected=expected)
    assert result.total_seconds==6
    assert result.wall_seconds==200
    assert result.rows[-1]["cumulative_s"]==6
    assert all(r["correct"] for r in result.rows)


def test_missing_empty_window_reference_is_an_error(make_txn):
    records=[make_txn(1)]
    with pytest.raises(ValueError,match="Missing reference"):
        livefeed.run_live_feed(records,60,0,"heap",expected={})


def test_deadline_terminates_only_disposable_child():
    root=Path(__file__).resolve().parents[1]
    env=dict(os.environ,PYTHONPATH=str(root/"src"))
    completed=subprocess.run([sys.executable,"-c",
        "import time; from midnight_queue.deadline import algorithm_deadline; "
        "exec('with algorithm_deadline(.03):\\n    time.sleep(2)')"],
        env=env,capture_output=True,timeout=5)
    assert completed.returncode==124


@pytest.mark.parametrize("module",["run_tournament","run_topk","run_livefeed"])
def test_measured_deadline_exit_is_dnf(monkeypatch,module):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/"scripts"))
    runner=importlib.import_module(module)
    monkeypatch.setattr(runner.subprocess,"run",lambda *a,**kw:
                        subprocess.CompletedProcess(a,124,stdout="",stderr=""))
    if module=="run_tournament":
        result=runner._run_worker(Path("unused"),"Insertion Sort",1,False)
    elif module=="run_topk":
        result=runner._run(Path("unused"),"Size-K Heap",2,1,False)
    else:
        result=runner._run(Path("unused"),Path("unused"),"heap",60,1)
    assert result is None


def test_topk_resume_does_not_duplicate_medians_or_measurements(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/"scripts"))
    runner=importlib.import_module("run_topk")
    outcomes=importlib.import_module("refresh_prediction_outcomes")
    monkeypatch.setattr(runner,"PROJECT_ROOT",tmp_path)
    monkeypatch.setattr(outcomes,"reconcile",lambda:None)
    cache=tmp_path/"outputs/cache"
    cache.mkdir(parents=True)
    (cache/"manifest.json").write_text(json.dumps({"sizes":{"10":{"conditions":{"C1":{"cache_file":"unused"}}}}}))
    calls=[]
    def worker(*args,**kwargs):
        calls.append(args)
        return dict(elapsed_s=.1,comparisons=20,moves=30,correct=True)
    monkeypatch.setattr(runner,"_run",worker)
    monkeypatch.setattr(sys,"argv",["run_topk.py","--sizes","10","--conditions","C1"])
    runner.main()
    runner.main()
    rows=runner._read(tmp_path/"outputs/raw/topk.csv")
    # n=10 has two valid capacities: 10 and n/10=1, each for three methods.
    assert len(calls)==30
    assert sum(r["record_type"]=="median" for r in rows)==6
    assert sum(r["record_type"]=="run" for r in rows)==30
