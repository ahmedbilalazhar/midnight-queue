"""Regression coverage for the historical parallel-runner timeout defect."""
import importlib
from pathlib import Path
import subprocess
import pytest


def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return importlib.import_module("run_tournament"), importlib.import_module("run_tournament_parallel")


@pytest.mark.parametrize("module",["run_tournament","run_topk","run_livefeed"])
def test_outer_process_timeout_is_not_algorithm_dnf(monkeypatch,module):
    modules(monkeypatch)
    runner=importlib.import_module(module)
    def timeout(*args,**kwargs):
        raise subprocess.TimeoutExpired(args[0],kwargs["timeout"])
    monkeypatch.setattr(runner.subprocess,"run",timeout)
    with pytest.raises(RuntimeError,match="DNF is unproven"):
        if module=="run_tournament":
            runner._run_worker(Path("unused"),"Insertion Sort",1,False)
        elif module=="run_topk":
            runner._run(Path("unused"),"Size-K Heap",2,1,False)
        else:
            runner._run(Path("unused"),Path("unused"),"heap",60,1)


def test_parallel_cell_stops_after_first_timeout(monkeypatch):
    serial,parallel = modules(monkeypatch)
    calls = []
    def worker(*args,**kwargs):
        calls.append(args)
        return None
    monkeypatch.setattr(serial,"_run_worker",worker)
    output = parallel.run_cell(dict(cache="unused",algorithm="Insertion Sort",
                                   condition="C5",n=1000,repeats=5,timeout=1))
    assert output["dnf"] is True
    assert output["elapsed"] == []
    assert len(calls) == 1


def test_parallel_cell_requires_five_completed_repetitions(monkeypatch):
    serial,parallel = modules(monkeypatch)
    def worker(*args,**kwargs):
        return dict(correct=True,elapsed_s=.1,comparisons=10,moves=20)
    monkeypatch.setattr(serial,"_run_worker",worker)
    output = parallel.run_cell(dict(cache="unused",algorithm="Merge Sort",
                                   condition="C2",n=10,repeats=5,timeout=1))
    assert output["dnf"] is False
    assert output["elapsed"] == [.1]*5
