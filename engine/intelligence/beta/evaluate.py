"""Actual learned scores, graded synthetic metrics and exact MAAE integration.

No model prediction supplies a label. The independent-human status stays false
for this generated dataset even when its acceptance partition is untouched.
"""
import hashlib
import json
import statistics
import time
from pathlib import Path
from .neural import load_model,predict
from ..evaluation import ranking_metrics,paired_report,calibration


def evaluate_pairs(directory,cases,temperature=1.0):
    model,tokenizer=load_model(directory)
    pairs=[(c["question"],p["text"]) for c in cases for p in c["candidates"]]
    grades=[p["grade"] for c in cases for p in c["candidates"]]
    start=time.perf_counter()
    probabilities=predict(model,tokenizer,pairs,temperature=temperature)
    elapsed=(time.perf_counter()-start)*1000
    decisive=[(p,int(g==2)) for p,g in zip(probabilities,grades) if g!=1]
    positives=[int(p>=.5)==bool(y) for p,y in decisive if y]
    negatives=[int(p>=.5)==bool(y) for p,y in decisive if not y]
    scores={}; offset=0; metrics=[];categories={}
    for c in cases:
        n=len(c["candidates"]); values=probabilities[offset:offset+n]; offset+=n
        scores[c["id"]]={p["id"]:s for p,s in zip(c["candidates"],values)}
        order=sorted(scores[c["id"]],key=scores[c["id"]].get,reverse=True)
        metrics.append(ranking_metrics(order,{p["id"]:p["grade"] for p in c["candidates"]}))
        categories.setdefault(c["category"],[]).append(metrics[-1]["ndcg10"])
    return {"version":1,"queries":len(cases),"families":len({c["group"] for c in cases}),
            "balanced_accuracy":(statistics.mean(positives)+statistics.mean(negatives))/2,
            "ndcg10":statistics.mean(m["ndcg10"] for m in metrics),
            "category_ndcg10":{key:statistics.mean(values) for key,values in categories.items()},
            "mrr":statistics.mean(m["mrr"] for m in metrics),
            "pairwise_accuracy":statistics.mean(m["pairwise_accuracy"] for m in metrics),
            "calibration":calibration([p for p,y in decisive],[y for p,y in decisive]),
            "batch_evaluation_ms":elapsed,"scores":scores,"independent_human_review":False}


def integrated(directory,cases):
    from ...indexing.document import Document
    from ...indexing.inverted_index import InvertedIndex
    from ...indexing.snapshot import SnapshotStore
    from ...passages.extractor import PassageExtractor
    from ...link_graph.graph import LinkGraph
    from ...link_graph.authority import LinkAuthorityCalculator
    from ...ranking.scorer import RankingEngine
    from ...search_sync.feedback_store import SearchSyncFeedbackStore
    from ...search_sync.preference_signal import SearchSyncPreferenceSignal
    from ...search_sync.neural_shadow import PESERelationShadowAdapter
    from ..model_release import ApprovedModel
    from ..reranking import NeuralReranker
    import os
    old=os.environ.get("PESE_REL_SHADOW_ENABLED")
    os.environ["PESE_REL_SHADOW_ENABLED"]="false"
    model,tokenizer=load_model(directory)
    raw=Path(directory)
    artifact=ApprovedModel(raw,"PESE-English-Beta-1",hashlib.sha256((raw/"weights.pt").read_bytes()).hexdigest(),
                           hashlib.sha256((raw/"tokenizer.json").read_bytes()).hexdigest(),.03,.75)
    def direct_research_prediction(command,payload):
        start=time.perf_counter()
        values=predict(model,tokenizer,[(payload["query"],p) for p in payload["evidence"]])
        return values,{"latency_ms":(time.perf_counter()-start)*1000,"transport":"direct_offline_research"}
    records=[]
    try:
        for case in cases:
            docs=[Document(id=p["id"],slug=f"fixture-{i}",title=p["text"].split('.')[0],content=p["text"],
                           created_at="2020-01-01T00:00:00Z",updated_at="2020-01-01T00:00:00Z") for i,p in enumerate(case["candidates"])]
            index=InvertedIndex()
            for d in docs: index.index_document(d,PassageExtractor().extract_passages(d))
            graph=LinkGraph(); graph.build_from_documents(docs)
            auth=LinkAuthorityCalculator(graph); auth.compute_scores()
            engine=RankingEngine(index,auth,doc_store=SnapshotStore(docs),search_sync=SearchSyncPreferenceSignal(SearchSyncFeedbackStore(":memory:")))
            baseline=engine.search(case["question"],skip_qa=True)
            engine.neural_ranker=NeuralReranker(artifact,predictor=direct_research_prediction)
            engine._neural_search_enabled=lambda:True
            engine.invalidate_query_cache()
            candidate=engine.search(case["question"],skip_qa=True)
            judgments={p["id"]:p["grade"] for p in case["candidates"]}
            b=[r.doc_id for r in baseline]; n=[r.doc_id for r in candidate]
            # Visible proxy only: literal grounding and synthetic source utility.
            def wrong(rows):
                if not rows or not rows[0].featured_answer:return False
                source=next(d for d in docs if d.id==rows[0].doc_id)
                return rows[0].featured_answer.casefold() not in source.content.casefold() or judgments[rows[0].doc_id]==0
            records.append({"id":case["id"],"category":case["category"],"group":case["group"],
                "baseline":b,"candidate":n,"judgments":judgments,
                "changed":b!=n,"new_wrong_promotion_proxy":wrong(candidate) and not wrong(baseline),
                "featured_answer":candidate[0].featured_answer if candidate else None,
                "gate_violations":len(set(n)-set(b)),"neural":candidate.hybrid_trace.get("neural_ranking"),
                "adjustments":[{"id":r.doc_id,"delta":r.neural_adjustment,"admitted":r.trace.evidence_gate_passed} for r in candidate]})
    finally:
        if old is None:os.environ.pop("PESE_REL_SHADOW_ENABLED",None)
        else:os.environ["PESE_REL_SHADOW_ENABLED"]=old
    paired=paired_report(records,samples=500)
    paired.pop("rows")
    return {"paired":paired,"changed_queries":sum(r["changed"] for r in records),
            "new_wrong_promotions_proxy":sum(r["new_wrong_promotion_proxy"] for r in records),
            "gate_violations":sum(r["gate_violations"] for r in records),"records":records,
            "answer_assessment":"synthetic_source_and_literal_grounding_proxy_not_human_answer_review"}
