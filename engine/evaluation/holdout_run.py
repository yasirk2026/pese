"""One-run unlabelled holdout capture. Refuses to overwrite recorded outputs."""
import argparse
import hashlib
import json
import tempfile
import time
from pathlib import Path
from engine.evaluation.phase2f_support import build_engine
from engine.evaluation.release_manifest import source_manifest
from engine.indexing.document import Document
from engine.nlp.tokenizer import QueryRepresentation


def run(bundle, output, freeze):
    frozen=json.loads(Path(freeze).read_text(encoding="utf-8"))
    before=source_manifest()
    assert before["sha256"]==frozen["sha256"],"Code does not match freeze"
    raw=Path(bundle).read_bytes();data=json.loads(raw)
    # There is deliberately no expected-label argument or import.
    assert set(data)=={"documents","questions"}
    docs=[Document.from_dict(row) for row in data["documents"]]
    records=[]
    with tempfile.TemporaryDirectory(prefix="pese-holdout-") as temp:
        engine=build_engine(docs,temp)
        for row in data["questions"]:
            start=time.perf_counter();results=engine.search(row["query"],skip_qa=True)
            analysis=results.query_analysis
            qrep=QueryRepresentation(analysis.effective_query,content_terms=analysis.effective_content_terms)
            _,predicates,properties=engine.answer_extractor.relevance_gate._extract_query_semantic_components(analysis)
            qrep.relation_terms=predicates+properties
            passages=[]
            for result in results[:3]:
                for passage,score,breakdown in engine.passage_scorer.score_passages_for_doc(result.slug,qrep)[:3]:
                    passages.append(dict(slug=passage.slug,id=passage.passage_id,text=passage.text,score=score))
            records.append(dict(id=row["id"],query=row["query"],category=row.get("category"),
                effective_query=analysis.effective_query,slugs=[r.slug for r in results[:3]],passages=passages,
                answer=results[0].featured_answer if results else None,
                answer_audit=results[0].answer_audit if results else None,
                timing=results.timing,elapsed_ms=round((time.perf_counter()-start)*1000,2)))
        model=engine.vector_index.provider.get_metadata()
    assert source_manifest()["sha256"]==before["sha256"],"Source changed during holdout"
    report=dict(source_sha256=before["sha256"],bundle_sha256=hashlib.sha256(raw).hexdigest(),provider=model,
                protocol="Independent author labels withheld; one production run; QA disabled; no tuning after reveal",records=records)
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as handle: json.dump(report,handle,indent=2)
    print(json.dumps({"queries":len(records),"outputs_sha256":hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--bundle",required=True);parser.add_argument("--output",required=True);parser.add_argument("--freeze",required=True)
    args=parser.parse_args();run(args.bundle,args.output,args.freeze)
