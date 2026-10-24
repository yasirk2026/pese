"""Exposed RC1 replay, deliberately separate from the sealed holdout runner."""
import json
import argparse
import tempfile
import time
from pathlib import Path
from collections import Counter
from .phase2f_support import build_engine
from ..indexing.document import Document
from .release_manifest import source_manifest
from ..nlp.tokenizer import QueryRepresentation


def run(output, semantic=True):
    base=Path('docs/audit')
    bundle=json.loads((base/'phase2f-holdout-input.json').read_text(encoding='utf-8'))
    labels=json.loads((base/'phase2f-holdout-labels.json').read_text(encoding='utf-8'))['labels']
    previous={r['id']:r for r in json.loads((base/'phase2f-holdout-regression-score.json').read_text(encoding='utf-8'))['records']}
    old_outputs={r['id']:r for r in json.loads((base/'phase2f-holdout-regression-outputs.json').read_text(encoding='utf-8'))['records']}
    records=[]
    with tempfile.TemporaryDirectory(prefix='pese-rc2-exposed-') as temp:
        engine=build_engine([Document.from_dict(d) for d in bundle['documents']],temp,semantic=semantic)
        for label in labels:
            t=time.perf_counter(); results=engine.search(label['query'],skip_qa=True)
            answer=results[0].featured_answer if results else None
            audit=results[0].answer_audit if results else {}
            text=(answer or '').casefold()
            facts=all(any(f.casefold() in text for f in group) for group in label['required_facts'])
            correct=bool(answer and label['answerable'] and results[0].slug in label['expected_source_slugs'] and facts and not any(f.casefold() in text for f in label.get('forbidden_answer_claims',[])))
            slugs=[r.slug for r in results[:3]]
            analysis=results.query_analysis
            qrep=QueryRepresentation(analysis.effective_query,content_terms=analysis.effective_content_terms)
            _,predicates,properties=engine.answer_extractor.relevance_gate._extract_query_semantic_components(analysis)
            qrep.relation_terms=predicates+properties
            captured=[]
            for result in results[:3]:
                captured.extend(dict(slug=p.slug,id=p.passage_id,text=p.text) for p,_,_ in engine.passage_scorer.score_passages_for_doc(result.slug,qrep)[:3])
            unchanged=captured==[{k:p[k] for k in ('slug','id','text')} for p in old_outputs[label['id']]['passages']]
            records.append(dict(id=label['id'],query=label['query'],category=label['category'],answerable=label['answerable'],expected_source=label['expected_source_slugs'],required_facts=label['required_facts'],answer=answer,correct=correct,wrong_promotion=bool(answer and not correct),slugs=slugs,retrieved_passages_unchanged=unchanged,doc_at_1=bool(slugs and slugs[0] in label['expected_source_slugs']),doc_at_3=any(s in label['expected_source_slugs'] for s in slugs),audit=audit,timing=results.timing,elapsed_ms=round((time.perf_counter()-t)*1000,2),rc1_correct=previous[label['id']]['adjudicated_flags']['answer_or_abstention_correct']))
    answerable=[r for r in records if r['answerable']]; promoted=[r for r in records if r['answer']]; negatives=[r for r in records if not r['answerable']]
    summary=dict(cases=len(records),answerable=len(answerable),correct=sum(r['correct'] for r in answerable),promoted=len(promoted),wrong=sum(r['wrong_promotion'] for r in records),negative_abstentions=sum(not r['answer'] for r in negatives),negatives=len(negatives),doc_at_1=sum(r['doc_at_1'] for r in answerable),doc_at_3=sum(r['doc_at_3'] for r in answerable),categories=dict(Counter(r['category'] for r in answerable if r['correct'])))
    report=dict(protocol='EXPOSED DEVELOPMENT REGRESSION, not blind. Original labels unchanged. Grounded sentences accepted; manual relation adjudication still required.',source_sha256=source_manifest()['sha256'],semantic=semantic,summary=summary,records=records)
    summary['retrieved_passages_unchanged']=sum(r['retrieved_passages_unchanged'] for r in records)
    Path(output).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--lexical',action='store_true');a=p.parse_args();run(a.output,not a.lexical)
