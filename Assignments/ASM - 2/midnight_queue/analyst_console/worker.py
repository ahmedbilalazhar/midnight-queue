"""One measured console/demo run, separate from the HTTP server."""
import json
from pathlib import Path
import pickle
import sys
import time

from midnight_queue.deadline import algorithm_deadline
from midnight_queue.records import Counters,TriageOrder,triage_key
from midnight_queue.sorting import SORT_ALGORITHMS
from midnight_queue.topk import TOPK_ALGORITHMS
from midnight_queue.livefeed import build_expected_queues,run_live_feed


def measure(records,algorithm,k,timeout=300,mode="queue",width=3600):
    counters=Counters()
    order=TriageOrder(counters=counters)
    work=list(records)
    publications=None
    if mode=="live":
        expected=build_expected_queues(records,width,k)
        feed=run_live_feed(work,width,k,algorithm,expected=expected,timeout_seconds=timeout)
        output=feed.queues[max(feed.queues)] if feed.queues else []
        elapsed=feed.total_seconds
        counters=feed.counters
        publications=feed.rows
        correct=all(r["correct"] for r in feed.rows)
    else:
        with algorithm_deadline(timeout):
            start=time.perf_counter()
            if algorithm in SORT_ALGORITHMS:
                ordered=SORT_ALGORITHMS[algorithm](work,order,counters)
                if mode=="batch":
                    output=ordered
                else:
                    output=ordered[:k]
                    counters.moves+=len(output)
            else:
                output=TOPK_ALGORITHMS[algorithm](work,k,order,counters)
            elapsed=time.perf_counter()-start
        correct=output==sorted(records,key=triage_key)[:k]
    result=dict(elapsed_s=elapsed,comparisons=counters.comparisons,moves=counters.moves,
                correct=correct,queue_size=len(output),
                queue=[dict(txn_id=t.txn_id,band=t.band,amount=t.amount,time=t.time,risk=t.risk) for t in output])
    if publications is not None: result["publications"]=publications
    return result


if __name__=="__main__":
    with Path(sys.argv[1]).open("rb") as f: job=pickle.load(f)
    json.dump(measure(**job),sys.stdout,allow_nan=False)
