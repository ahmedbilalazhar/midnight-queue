"""Exercise real queue workers, API boundaries, cancellation and demo logging."""
import csv
from http.server import ThreadingHTTPServer
import json
import threading
import time
from types import SimpleNamespace
from urllib.request import Request,urlopen
from urllib.error import HTTPError

import pytest
from analyst_console.engine import (ALGORITHMS,ConsoleService,validate_request,run_worker,
                                    CancelledError,BusyError,DeadlineError)
from analyst_console.server import make_handler
from midnight_queue.records import triage_key
from analyst_console.worker import measure


def parameters(**kwargs):
    return dict(algorithm="Size-K Heap",n=1000,k=52,condition="C1",request_id="test-run",**kwargs)


@pytest.fixture
def records(make_txn):
    return [make_txn(i,band=i%8,amount=(i*17)%31,time=i//3) for i in range(1,1001)]


@pytest.mark.parametrize("algorithm",ALGORITHMS)
def test_each_console_algorithm_returns_the_same_verified_ordered_queue(records,tmp_path,algorithm):
    service=ConsoleService(prepare=lambda n,c:records,log_path=tmp_path/"console.csv")
    params=parameters();params["algorithm"]=algorithm
    result=service.run(params)
    expected=sorted(records,key=triage_key)[:52]
    assert result["correct"] and result["queue_size"]==52
    assert [t["txn_id"] for t in result["queue"]]==[t.txn_id for t in expected]
    assert all({"txn_id","band","amount","time","risk"}==set(r) for r in result["queue"])
    assert result["elapsed_s"]>0 and result["comparisons"]>0
    row=list(csv.DictReader((tmp_path/"console.csv").open()))[0]
    assert row["record_type"]=="console_run" and not row["median_s"]
    assert float(row["elapsed_s"])==result["elapsed_s"]


@pytest.mark.parametrize("changes",[{"k":0},{"k":1001},{"k":2.5},{"k":True},
                                     {"n":-1},{"algorithm":"sorted"},{"condition":"C6"}])
def test_bad_console_parameters_are_rejected(changes):
    params=parameters();params.update(changes)
    with pytest.raises(ValueError): validate_request(params)


def test_console_worker_enforces_its_algorithm_deadline(records):
    with pytest.raises(DeadlineError):
        run_worker(records,"Insertion Sort",52,timeout=.001)


def test_console_rejects_a_completed_observation_above_the_deadline(records,monkeypatch):
    from analyst_console import engine
    payload=json.dumps(dict(elapsed_s=2,correct=True))
    fake=SimpleNamespace(returncode=0,communicate=lambda **kw:(payload,""),poll=lambda:0)
    monkeypatch.setattr(engine.subprocess,"Popen",lambda *a,**kw:fake)
    with pytest.raises(DeadlineError):
        run_worker(records,"Merge Sort",52,timeout=1)


def test_demo_batch_and_queue_use_their_respective_move_definitions(make_txn):
    rows=[make_txn(i,amount=a) for i,a in enumerate((3,1,2),1)]
    batch=measure(rows,"Insertion Sort",3,mode="batch",timeout=None)
    queue=measure(rows,"Insertion Sort",2,mode="queue",timeout=None)
    assert batch["moves"]==3 and queue["moves"]==5
    assert batch["comparisons"]==queue["comparisons"]==3
    assert batch["queue_size"]==3 and queue["queue_size"]==2


def test_console_cancellation_stops_worker_and_does_not_log_a_timing(make_txn,tmp_path):
    records=[make_txn(i,band=1,amount=i) for i in range(1,100001)]
    service=ConsoleService(prepare=lambda n,c:records,log_path=tmp_path/"console.csv")
    params=parameters();params.update(n=100000,algorithm="Insertion Sort")
    errors=[]
    def run():
        try: service.run(params)
        except Exception as exc: errors.append(exc)
    thread=threading.Thread(target=run);thread.start()
    try:
        deadline=time.monotonic()+10
        while service.process is None and time.monotonic()<deadline: time.sleep(.01)
        assert service.process is not None
        assert service.cancel("another-run") is False
        with pytest.raises(BusyError): service.run(parameters())
        assert service.cancel("test-run") is True
        thread.join(5)
        assert not thread.is_alive() and isinstance(errors[0],CancelledError)
        assert not (tmp_path/"console.csv").exists()
    finally:
        service.cancel("test-run");thread.join(5)


def test_http_console_serves_the_ui_and_rejects_invalid_requests(records,tmp_path):
    service=ConsoleService(prepare=lambda n,c:records,log_path=tmp_path/"console.csv")
    server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(service))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f"http://127.0.0.1:{server.server_port}"
    def request(params,origin=base):
        return Request(base+"/api/run",json.dumps(params).encode(),headers={"Content-Type":"application/json","Origin":origin})
    try:
        assert b"Queue capacity K" in urlopen(base).read()
        assert "text/css" in urlopen(base+"/style.css").headers["Content-Type"]
        assert "javascript" in urlopen(base+"/app.js").headers["Content-Type"]
        assert len(json.load(urlopen(base+"/api/config"))["algorithms"])==7
        assert json.load(urlopen(request(parameters())))["correct"]
        bad=parameters();bad["k"]=-1
        with pytest.raises(HTTPError) as exc: urlopen(request(bad))
        assert exc.value.code==400
        with pytest.raises(HTTPError) as exc: urlopen(request(parameters(),"https://example.invalid"))
        assert exc.value.code==403
    finally:
        server.shutdown();server.server_close();thread.join(5)


def test_dashboard_evidence_agrees_with_saved_measurements():
    from analyst_console.evidence import load_evidence
    evidence=load_evidence()
    assert sum(evidence["profile"]["band_counts"].values())==evidence["profile"]["rows"]==284807
    assert sum(evidence["profile"]["fraud_by_band"].values())==evidence["profile"]["fraud_count"]==492
    assert len(evidence["tournament"])==120
    assert sum(row["seconds"] is None for row in evidence["tournament"])==15
    assert evidence["capture"]["points"][str(evidence["capture"]["k_half"])]["frauds"]==246
    assert sum(evidence["recommendations"]["wins"].values())==evidence["recommendations"]["comparison_cells"]==28
    assert len(evidence["live"])==6
