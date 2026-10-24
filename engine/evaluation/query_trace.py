"""Trace code-derived live-corpus retrieval stages without changing user content.

Private full traces go under .tmp, never the public audit report.
"""
import collections
import json
import shutil
import sys
import tempfile
from pathlib import Path
from engine.indexing.store import DocumentStore
from engine.indexing.inverted_index import InvertedIndex
from engine.passages.extractor import PassageExtractor
from engine.passages.answer_extractor import FeaturedAnswerExtractor,TEMPORAL_PATTERNS
from engine.link_graph.graph import LinkGraph
from engine.link_graph.authority import LinkAuthorityCalculator
from engine.semantic.index import VectorIndex
from engine.ranking.scorer import RankingEngine
from engine.nlp.tokenizer import QueryRepresentation


def run():
    import torch
    torch.set_num_threads(2)
    root=Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="query-trace-",dir=root/".tmp") as directory:
        temp=Path(directory)
        shutil.copyfile(root/"engine/data/firestore_documents.json",temp/"docs.json")
        store=DocumentStore(temp/"docs.json")
        docs=store.list_documents(status="published");index=InvertedIndex();passages={}
        for doc in docs:
            passages[doc.id]=PassageExtractor().extract_passages(doc);index.index_document(doc,passages[doc.id])
        (temp/"vectors").mkdir();shutil.copyfile(root/"engine/data/semantic_index/cache_store.npz",temp/"vectors/cache_store.npz")
        vectors=VectorIndex(index_dir=temp/"vectors");vectors.build_index(docs,passages)
        graph=LinkGraph();graph.build_from_documents(docs);auth=LinkAuthorityCalculator(graph);auth.compute_scores()
        engine=RankingEngine(index,auth,vector_index=vectors,doc_store=store)
        output=[]
        for query in ["does healing lounge offer flexible payments","when did japan enter ww2"]:
            calls=collections.Counter();order=[];keys={}
            def profile(frame,event,arg):
                if event=="call" and str(root/"engine") in frame.f_code.co_filename and ".venv" not in frame.f_code.co_filename:
                    key=keys.get(frame.f_code)
                    if key is None:
                        key=f"{Path(frame.f_code.co_filename).relative_to(root)}:{frame.f_code.co_name}"
                        keys[frame.f_code]=key
                    if key not in calls:order.append(key)
                    calls[key]+=1
            sys.setprofile(profile)
            try:results=engine.search(query)
            finally:sys.setprofile(None)
            analysis=results.query_analysis
            representation=QueryRepresentation(analysis.effective_query,content_terms=analysis.effective_content_terms)
            gate=FeaturedAnswerExtractor().relevance_gate
            entities,predicates,properties=gate._extract_query_semantic_components(analysis)
            representation.relation_terms=predicates+properties
            lexical=engine.retriever.retrieve_candidates(representation)
            semantic=engine.semantic_retriever.retrieve_candidates(analysis.effective_query,analysis.effective_content_terms)
            fused=engine.candidate_fuser.fuse(lexical,semantic)
            psgs=[]
            dates=[]
            for result in results[:3]:
                for passage,score,breakdown in engine.passage_scorer.score_passages_for_doc(result.slug,representation):
                    psgs.append(dict(slug=result.slug,id=passage.passage_id,text=passage.text,score=score,breakdown=breakdown))
                    if result.slug=="japan":
                        seen=set()
                        for pattern,_ in TEMPORAL_PATTERNS:
                            for match in pattern.finditer(passage.text):
                                candidate=match.group().strip()
                                if candidate in seen:continue
                                seen.add(candidate)
                                dates.append(gate.evaluate(query,candidate,passage.text,analysis).model_dump())
            output.append(dict(query=query,analysis=analysis.model_dump(),entities=entities,predicates=predicates,properties=properties,
                lexical_candidates=lexical,semantic_candidates=[s.model_dump() for s in semantic],fusion=[f.model_dump() for f in fused],
                results=[r.model_dump() for r in results],passages=psgs,temporal_verdicts=dates,qa_trace=results.qa_trace,
                first_function_call_order=order,function_call_counts=dict(calls)))
        (root/".tmp/phase2e-query-traces.json").write_text(json.dumps(output,indent=2),encoding="utf-8")
        print(json.dumps([dict(query=x["query"],analysis=x["analysis"]["effective_query"],entities=x["entities"],predicates=x["predicates"],properties=x["properties"],top=x["results"][0]["slug"],answer=x["results"][0]["featured_answer"]) for x in output],indent=2))


if __name__=="__main__":run()
