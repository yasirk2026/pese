"""Fresh-process engine cold/warm/memory profile; isolated derived indexes."""
import ctypes
import json
import shutil
import statistics
import tempfile
import time
from pathlib import Path


def rss_mb():
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[("cb",wintypes.DWORD),("PageFaultCount",wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in ["PeakWorkingSetSize","WorkingSetSize","QuotaPeakPagedPoolUsage","QuotaPagedPoolUsage","QuotaPeakNonPagedPoolUsage","QuotaNonPagedPoolUsage","PagefileUsage","PeakPagefileUsage"]]
    counters=Counters();counters.cb=ctypes.sizeof(counters)
    ctypes.windll.psapi.GetProcessMemoryInfo(wintypes.HANDLE(-1),ctypes.byref(counters),counters.cb)
    return round(counters.WorkingSetSize/1024**2,2)


def run():
    started=time.perf_counter();memory={"interpreter":rss_mb()}
    from engine.indexing.document import Document
    from engine.indexing.inverted_index import InvertedIndex
    from engine.passages.extractor import PassageExtractor
    from engine.link_graph.graph import LinkGraph
    from engine.link_graph.authority import LinkAuthorityCalculator
    root=Path(__file__).resolve().parents[2]
    raw=json.loads((root/"engine/data/firestore_documents.json").read_text(encoding="utf-8"))
    docs=[Document(**d) for d in raw.values() if d.get("status")=="published"]
    index=InvertedIndex();passages={}
    for doc in docs:
        passages[doc.id]=PassageExtractor().extract_passages(doc)
        index.index_document(doc,passages[doc.id])
    memory["lexical_passages"]=rss_mb();lexical_ready_ms=(time.perf_counter()-started)*1000
    graph=LinkGraph();graph.build_from_documents(docs);auth=LinkAuthorityCalculator(graph);auth.compute_scores()
    from engine.semantic.index import VectorIndex
    from engine.ranking.scorer import RankingEngine
    with tempfile.TemporaryDirectory(prefix="runtime-audit-",dir=root/".tmp") as temp:
        cache=root/"engine/data/semantic_index/cache_store.npz"
        if cache.exists():shutil.copyfile(cache,Path(temp)/"cache_store.npz")
        vector=VectorIndex(index_dir=Path(temp));vector.build_index(docs,passages)
        memory["vector_arrays_before_model"]=rss_mb()
        vector.provider.embed_query("startup prewarm")
        memory["embedding_model"]=rss_mb()
        engine=RankingEngine(index,auth,vector_index=vector)
        import torch
        torch.set_num_threads(2)
        reader=engine._get_qa_reader()
        memory["qa_model"]=rss_mb()
        startup_ms=(time.perf_counter()-started)*1000
        rows=[]
        for label,q in [("first","when did japan enter ww2"),("second_repeat","when did japan enter ww2"),("third_different","does healing lounge offer flexible payments"),("fourth_repeat","does healing lounge offer flexible payments")]:
            t=time.perf_counter();res=engine.search(q,skip_qa=True)
            rows.append(dict(label=label,ms=round((time.perf_counter()-t)*1000,2),cache_hit=res.timing.get("cache_hit")))
        memory["before_100"]=rss_mb()
        durations=[]
        for n in range(100):
            t=time.perf_counter();engine.search(f"Japan history auditcase{n}",skip_qa=True);durations.append((time.perf_counter()-t)*1000)
        memory["after_100_unique"]=rss_mb()
        report=dict(memory_mb=memory,lexical_ready_ms=round(lexical_ready_ms,2),startup_ms=round(startup_ms,2),first_queries=rows,
            stress=dict(cases=100,p50_ms=round(statistics.median(durations),2),p95_ms=round(sorted(durations)[94],2)),
            cache_entries=len(engine._search_cache),torch_threads=torch.get_num_threads(),torch_interop_threads=torch.get_num_interop_threads(),
            model_parameters=sum(p.numel() for p in reader.model.parameters()) if reader else None,
            limitations="Fresh Python process with existing corpus vector cache; NOT a model-download cold start or HTTP/browser startup. RSS includes native allocator retention; 100 queries cannot prove absence of leaks.")
        (root/"docs/audit/runtime.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report,indent=2))


if __name__=="__main__":run()
