"""Frozen fact/source scoring with explicit format flags and manual review queue.

This module is only run after a sealed production output has been recorded.
It does not revise labels, inputs or outputs. All promotions require review of
their requested relation, polarity and qualifiers in addition to raw matching.
"""
import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from collections import defaultdict


def normalize(value):
    value=unicodedata.normalize('NFKC',value).casefold()
    return re.sub(r'\s+',' ',value.translate(str.maketrans({'’':"'",'‘':"'",'“':'"','”':'"','–':'-','—':'-'}))).strip()


def score(outputs,labels,output):
    captured=json.loads(Path(outputs).read_text(encoding='utf-8'))
    truth=json.loads(Path(labels).read_text(encoding='utf-8'))['labels']
    expected={r['id']:r for r in truth}; records=[]
    assert len(expected)==len(captured['records'])
    for row in captured['records']:
        label=expected[row['id']];answer=row.get('answer');text=normalize(answer or '')
        slugs=row['slugs'];sources=label['expected_source_slugs']
        source_correct=bool(slugs and slugs[0] in sources)
        facts=all(any(normalize(value) in text for value in group) for group in label['required_facts'])
        forbidden=[value for value in label.get('forbidden_answer_claims',[]) if normalize(value) in text]
        correct=bool(answer and label['answerable'] and source_correct and facts and not forbidden)
        supported=lambda p:any(p['slug']==e['source_slug'] and normalize(e['text']) in normalize(p['text']) for e in label['supporting_evidence'])
        passages=row['passages']
        canonical=correct and any(text==normalize(value) for group in label['required_facts'] for value in group)
        records.append(dict(id=row['id'],query=row['query'],category=label['category'],answerable=label['answerable'],expected_source=sources,required_facts=label['required_facts'],supporting_evidence=label['supporting_evidence'],answer=answer,source_correct=source_correct,raw_fact_correct=correct,adjudicated_correct=correct,adjudication='PENDING review of all promotions; raw labels unchanged',format_flag='FACT_CORRECT' if canonical else ('FACT_CORRECT_FORMAT_NONCANONICAL' if correct else None),wrong_promotion=bool(answer and not correct),false_abstention=bool(label['answerable'] and not answer),negative_abstention=bool(not label['answerable'] and not answer),doc_at_1=source_correct,doc_at_3=any(s in sources for s in slugs),passage_at_1=bool(passages and supported(passages[0])),passage_at_3=any(supported(p) for p in passages[:3]),audit=row.get('answer_audit'),timing=row['timing']))
    summary=aggregate(records)
    result=dict(protocol='One frozen production run. Raw labels, source and output immutable. Supported full sentences count as fact-correct; formatting is independent. Review every promotion for relation/type/polarity and record any change without editing raw flags.',outputs_sha256=hashlib.sha256(Path(outputs).read_bytes()).hexdigest(),labels_sha256=hashlib.sha256(Path(labels).read_bytes()).hexdigest(),source_sha256=captured['source_sha256'],summary=summary,records=records)
    with Path(output).open('x',encoding='utf-8') as handle:json.dump(result,handle,indent=2,ensure_ascii=False)
    print(json.dumps(summary))


def aggregate(records):
    positives=[r for r in records if r['answerable']];negatives=[r for r in records if not r['answerable']];promoted=[r for r in records if r['answer']]
    return dict(questions=len(records),answerable=len(positives),negatives=len(negatives),correct=sum(r['adjudicated_correct'] for r in positives),promoted=len(promoted),wrong_promotions=sum(r['wrong_promotion'] for r in records),false_abstentions=sum(r['false_abstention'] for r in positives),negative_abstentions=sum(r['negative_abstention'] for r in negatives),**{key:sum(r[key] for r in positives) for key in ('doc_at_1','doc_at_3','passage_at_1','passage_at_3')})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outputs',required=True);p.add_argument('--labels',required=True);p.add_argument('--output',required=True);a=p.parse_args();score(a.outputs,a.labels,a.output)
