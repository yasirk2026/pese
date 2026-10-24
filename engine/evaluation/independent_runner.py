"""Stage-separated Phase 2E evaluation; isolated synthetic corpus, no user writes.

Run: python -m engine.evaluation.independent_runner --output docs/audit/after.json
--neural records shadow calibration; --semantic uses real local embeddings.
This suite is development/regression data, not a holdout.
"""
import argparse
import hashlib
import json
import statistics
import tempfile
import time
from pathlib import Path

from engine.evaluation.independent_dataset import CASES, documents
from engine.indexing.inverted_index import InvertedIndex
from engine.indexing.store import DocumentStore
from engine.link_graph.graph import LinkGraph
from engine.link_graph.authority import LinkAuthorityCalculator
from engine.nlp.tokenizer import QueryRepresentation
from engine.passages.extractor import PassageExtractor
from engine.ranking.scorer import RankingEngine


def run(output, neural=False, semantic=False):
    import torch
    torch.set_num_threads(2)
    with tempfile.TemporaryDirectory(prefix="pese-audit-") as temp:
        docs = documents()
        index = InvertedIndex()
        passages = {}
        for doc in docs:
            passages[doc.id] = PassageExtractor().extract_passages(doc)
            index.index_document(doc, passages[doc.id])
        graph = LinkGraph()
        graph.build_from_documents(docs)
        auth = LinkAuthorityCalculator(graph)
        auth.compute_scores()
        vectors = None
        if semantic:
            from engine.semantic.index import VectorIndex
            vectors = VectorIndex(index_dir=Path(temp)/"vectors")
            vectors.build_index(docs, passages)
        engine = RankingEngine(index, auth, vector_index=vectors)
        records = []
        for query, slug, expected, category, evidence in CASES:
            start = time.perf_counter()
            results = engine.search(query, skip_qa=not neural)
            elapsed = (time.perf_counter()-start)*1000
            answer = results[0].featured_answer if results else None
            # Date answers must be exact; sentence answers must contain the expected
            # relation/value and remain extracted from their source document.
            answer_assessed = "keyword" not in category
            valid = bool(answer and expected and expected.casefold() in answer.casefold())
            if expected and expected.isdigit() and len(expected) == 4:
                valid = answer == expected
            source = next(d for d in docs if d.slug == results[0].slug) if results else None
            source_text = (source.content + " " + " ".join(f["answer"] for f in source.faqs)) if source else ""
            grounded = bool(answer and answer.casefold() in source_text.casefold())
            valid = valid and grounded
            ranked_passages = []
            for result in results[:3]:
                representation = QueryRepresentation(results.query_analysis.effective_query, content_terms=results.query_analysis.effective_content_terms)
                _, predicates, properties = engine.answer_extractor.relevance_gate._extract_query_semantic_components(results.query_analysis)
                representation.relation_terms = predicates + properties
                ranked_passages.extend(engine.passage_scorer.score_passages_for_doc(result.slug, representation)[:3])
            correct_passage = lambda p: p.slug == slug and evidence and evidence.casefold() in p.text.casefold()
            doc1 = bool(results and results[0].slug == slug)
            doc3 = any(r.slug == slug for r in results[:3])
            p1 = bool(ranked_passages and correct_passage(ranked_passages[0][0])) if evidence else None
            p3 = any(correct_passage(p) for p,_,_ in ranked_passages[:3]) if evidence else None
            abstention = answer is None if expected is None and answer_assessed else None
            failure = None
            if answer_assessed and answer and not valid:
                failure = "ANSWER_RELEVANCE_FAILURE"
            elif not doc1:
                failure = "DOCUMENT_RETRIEVAL_FAILURE"
            elif evidence and not p1:
                failure = "PASSAGE_RETRIEVAL_FAILURE"
            elif expected and not valid:
                failure = "QA_FAILURE"
            shadow = results.qa_trace or {}
            records.append(dict(query=query, category=category, expected_source=slug, expected_answer=expected,
                doc_at_1=doc1, doc_at_3=doc3, passage_at_1=p1, passage_at_3=p3, answer=answer,
                valid_direct_answer=valid if expected and answer_assessed else None, correct_abstention=abstention,
                answer_assessed=answer_assessed,
                grounded=grounded if answer else None, latency_ms=round(elapsed,2), failure_class=failure,
                effective_query=results.query_analysis.effective_query,
                top_slugs=[r.slug for r in results[:3]], timing=results.timing,
                shadow_answer=shadow.get("shadow_answer"), shadow_confidence=shadow.get("confidence")))
        mean = lambda k: round(statistics.mean(r[k] for r in records if r[k] is not None),4)
        promoted = [r for r in records if r["answer"]]
        summary = {k:mean(k) for k in ["doc_at_1","doc_at_3","passage_at_1","passage_at_3","valid_direct_answer","correct_abstention"]}
        summary.update(cases=len(records), promoted=len(promoted), wrong_promotions=sum(r["failure_class"]=="ANSWER_RELEVANCE_FAILURE" for r in records),
            p50_ms=round(statistics.median(r["latency_ms"] for r in records),2), p95_ms=round(sorted(r["latency_ms"] for r in records)[int(.95*(len(records)-1))],2))
        calibration = []
        for low in [.5,.6,.7,.8,.9]:
            bucket = [r for r in records if r["shadow_confidence"] is not None and low <= r["shadow_confidence"] <= (1.0 if low==.9 else low+.099999)]
            correct = [bool(r["shadow_answer"] and r["expected_answer"] and r["expected_answer"].lower() in r["shadow_answer"].lower()) or (not r["shadow_answer"] and r["expected_answer"] is None) for r in bucket]
            calibration.append(dict(low=low, count=len(bucket), accuracy=round(statistics.mean(correct),4) if correct else None))
        report = dict(dataset_status="development_regression_not_blind", semantic=semantic, neural_shadow=neural,
            corpus_sha256=hashlib.sha256(json.dumps([d.model_dump() for d in docs],sort_keys=True).encode()).hexdigest(),
            summary=summary, calibration=calibration, records=records)
        Path(output).parent.mkdir(parents=True,exist_ok=True)
        Path(output).write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(summary,indent=2))
        return report


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    parser.add_argument("--neural",action="store_true")
    parser.add_argument("--semantic",action="store_true")
    args=parser.parse_args()
    run(args.output,args.neural,args.semantic)
