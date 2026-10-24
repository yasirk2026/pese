"""Local HTTP waterfall, including concurrent discovery contention.

No sessions/events, so this probe does not add behavioral history.
python -m engine.evaluation.http_probe --output .tmp/phase2e-http-after.json
"""
import argparse
import concurrent.futures
import json
import statistics
import time
from pathlib import Path
import httpx

QUERIES=["does healing lounge offer flexible payments","when did japan enter ww2","meiji period","japna","what is my bicycle specification","when did yasir dream pese","when did islamic golden age end","when was bicycle invented",
         "when did Japan surrender","what does a CPU do","how do I clean a bicycle chain","where is Japan located"]


def run(base_url,output,repeats=3):
    records=[]
    with httpx.Client(base_url=base_url,timeout=60,trust_env=False) as client:
        health=client.get("/health").json()
        def fetch(path,q,debug=False):
            start=time.perf_counter()
            response=client.get(path,params=dict(q=q,debug=str(debug).lower()))
            response.raise_for_status()
            elapsed=(time.perf_counter()-start)*1000
            data=response.json()
            return dict(path=path,http_ms=round(elapsed,2),server_ms=data.get("took_ms"),bytes=len(response.content),data=data)
        first=fetch("/api/search",QUERIES[0])
        for repeat in range(repeats):
            for q in QUERIES:
                single=fetch("/api/search",q)
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                    jobs=[pool.submit(fetch,path,q) for path in ["/api/search","/api/questions","/api/related"]]
                    results=[j.result() for j in jobs]
                records.append(dict(query=q,repeat=repeat,isolated=single,concurrent=results))
        # Shadow ablation: same query and corpus, QA only in explicit debug mode.
        debug=[dict(query=q,request=fetch("/api/search",q,True)) for q in QUERIES[:8]]
    def stats(values):
        ordered=sorted(values)
        return dict(n=len(ordered),p50_ms=round(statistics.median(ordered),2),p95_ms=round(ordered[int(.95*(len(ordered)-1))],2),max_ms=round(max(ordered),2))
    summary={"isolated_main":stats([r["isolated"]["http_ms"] for r in records])}
    for path in ["/api/search","/api/questions","/api/related"]:
        summary[path]=stats([x["http_ms"] for r in records for x in r["concurrent"] if x["path"]==path])
    report=dict(health=health,first_probe=first,summary=summary,records=records,debug_shadow=debug,
        limitations="HTTP localhost measurements; browser paint and cold process startup are separate measurements. First probe is NOT a cold-server measurement.")
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--base-url",default="http://127.0.0.1:8000")
    parser.add_argument("--output",required=True)
    parser.add_argument("--repeats",type=int,default=3)
    args=parser.parse_args()
    run(args.base_url,args.output,args.repeats)
