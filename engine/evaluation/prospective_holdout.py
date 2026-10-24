"""One-run prospective holdout after source freeze.

Facts are sampled at execution, not inspected during implementation tuning.
Templates are author-known: this is NOT an independently authored blind test.
After the first run it is regression data. Refuses to overwrite its report.
"""
import hashlib
import json
import secrets
from pathlib import Path
from engine.indexing.document import Document
from engine.indexing.inverted_index import InvertedIndex
from engine.passages.extractor import PassageExtractor
from engine.link_graph.graph import LinkGraph
from engine.link_graph.authority import LinkAuthorityCalculator
from engine.ranking.scorer import RankingEngine


def source_digest():
    root=Path(__file__).resolve().parents[2]
    sources=[p for p in (root/"engine").rglob("*.py") if not any(part in {".venv","tests","evaluation","data"} for part in p.relative_to(root/"engine").parts)]
    return hashlib.sha256(b"".join(str(p.relative_to(root)).encode()+p.read_bytes() for p in sorted(sources))).hexdigest()


def run(output_name="prospective-holdout.json"):
    root=Path(__file__).resolve().parents[2]
    if Path(output_name).name!=output_name:raise ValueError("Output must be an audit report filename")
    output=root/"docs/audit"/output_name
    if output.exists():raise RuntimeError("Holdout already run; it is regression data now. Do not overwrite or retune against it as blind data.")
    frozen=source_digest()
    docs=[];cases=[]
    for n in range(12):
        name="Unit"+secrets.token_hex(3)
        slug=f"holdout-{n}"
        year=str(1970+secrets.randbelow(50));other=str(int(year)+5)
        kind=n%6
        faqs=[]
        if kind==0:
            content=f"{name} opened in {year}. {name} closed in {other}."
            questions=[(f"When did {name} open?",year),(f"When did {name} close?",other)]
        elif kind==1:
            content=f"{name} operates in Valparaiso. {name} hired an accountant in {year}."
            questions=[(f"Where does {name} operate?","Valparaiso"),(f"Does {name} offer credit cards?",None)]
        elif kind==2:
            content=f"Nora founded {name} in {year}. Evan joined {name} in {other}."
            questions=[(f"Who founded {name}?","Nora"),(f"When did Evan join {name}?",other)]
        elif kind==3:
            content=f"{name} accepts bank transfer. {name} does not accept cryptocurrency."
            questions=[(f"Does {name} accept cryptocurrency?","does not accept cryptocurrency"),(f"Does {name} accept bank transfer?","accepts bank transfer")]
        elif kind==4:
            content=f"Clients of {name} may divide the fee into three installments."
            questions=[(f"Can {name} clients split the payment?","three installments"),(f"Does {name} offer free parking?",None)]
        else:
            content=f"{name} is a sensor."
            faq_answer=f"{name} launched in {year}."
            faqs=[dict(id="launch",question=f"When did {name} launch?",answer=faq_answer)]
            questions=[(f"When did {name} launch?",year),(f"Does {name} support wireless charging?",None)]
        docs.append(Document(id=slug,slug=slug,title=name,content=content,faqs=faqs))
        cases.extend((q,slug,expected,kind) for q,expected in questions)
    index=InvertedIndex()
    for doc in docs:index.index_document(doc,PassageExtractor().extract_passages(doc))
    graph=LinkGraph();graph.build_from_documents(docs);auth=LinkAuthorityCalculator(graph);auth.compute_scores()
    engine=RankingEngine(index,auth)
    records=[]
    for query,slug,expected,kind in cases:
        results=engine.search(query,skip_qa=True)
        answer=results[0].featured_answer if results else None
        correct=answer is None if expected is None else bool(answer and expected.lower() in answer.lower() and results[0].slug==slug)
        if expected and expected.isdigit():correct=answer==expected
        records.append(dict(query=query,expected_source=slug,expected_answer=expected,answer=answer,correct=correct,template=kind,doc_at_1=bool(results and results[0].slug==slug)))
    if source_digest()!=frozen:raise RuntimeError("Implementation changed while holdout ran")
    report=dict(status="one_run_prospective_then_regression",independent_author=False,source_sha256=frozen,
        generated_corpus=[d.model_dump() for d in docs],records=records,
        summary=dict(cases=len(records),correct=sum(r["correct"] for r in records),wrong_promotions=sum(bool(r["answer"]) and not r["correct"] for r in records),doc_at_1=sum(r["doc_at_1"] for r in records)/len(records)))
    output.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report["summary"],indent=2))


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--output-name",default="prospective-holdout.json")
    run(parser.parse_args().output_name)
