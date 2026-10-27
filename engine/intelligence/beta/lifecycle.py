"""Immutable local job snapshots and predefined, conservative promotion gates."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import statistics
from ..evidence import digest
from .judge import Quality


def lineage(rows):
    return {value for r in rows for value in ("document:"+digest(r.get("document_id",r.get("document_family"))),
            "query:"+digest(r["question"].casefold()),"pair:"+digest((r["question"].casefold(),r["text"])))}


def snapshot(queue,document_reader,allowed):
    train=[];evaluation=[]
    for row in queue.list(2000):
        if row["quality"]!=Quality.VERIFIED.value or not row["review"]:continue
        e=row["payload"];p=e["receipt"]
        if not allowed(p["target_id"]):continue
        doc=document_reader(p["target_id"])
        if doc is None:continue
        from .runtime import document_revision
        if document_revision(doc)!=p["document_revision"]:continue
        item={"question":p["effective_query"],"text":e["evidence_text"],"grade":row["review"]["grade"],
              "document_revision":p["document_revision"],
              "group":p["target_id"],"document_family":p["target_id"],"id":row["id"],"document_id":p["target_id"],
              "source_kind":e.get("source_kind"),"receipt_hash":digest(e),"review":row["review"]}
        (evaluation if row["role"]=="evaluation" else train).append(item)
    if len(train)<12 or len({r["group"] for r in train})<3:
        raise ValueError("Need at least 12 reviewed training pairs across three document families")
    if {r["grade"] for r in train}-{1}!={0,2}:raise ValueError("Reviewed relevant and irrelevant examples required")
    groups=sorted({r["group"] for r in train})
    validation_groups=set(groups[-max(1,len(groups)//4):])
    validation=[r for r in train if r["group"] in validation_groups]
    training=[r for r in train if r["group"] not in validation_groups]
    for rows in (training,validation):
        if {r["grade"] for r in rows}-{1}!={0,2}:raise ValueError("Both classes required in disjoint train/validation groups")
    if set(r["document_family"] for r in training+validation)&set(r["document_family"] for r in evaluation):
        raise ValueError("Training/evaluation document families overlap")
    if set(r["question"].casefold() for r in training+validation)&set(r["question"].casefold() for r in evaluation):
        raise ValueError("Training/evaluation queries overlap")
    return {"version":1,"train":training,"validation":validation,"evaluation":evaluation,
            "snapshot_hash":digest([training,validation,evaluation]),"label_trust":"explicit_local_owner_review_not_global_truth"}


def evaluation_cases(rows):
    grouped=defaultdict(list)
    for r in rows:grouped[r["question"]].append(r)
    cases=[]
    for question,group in grouped.items():
        candidates={r["document_id"]:r for r in group}
        if len(candidates)<2 or {r["grade"] for r in candidates.values()}-{1}!={0,2}:continue
        if any(not r["review"].get("answer_reviewed") for r in candidates.values()):continue
        answers={r["review"].get("expected_answer") for r in candidates.values()}
        if len(answers)!=1:raise ValueError("Conflicting heldout expected-answer reviews")
        cases.append({"id":digest(question),"question":question,"group":digest(question),"document_family":digest(sorted(candidates)),
            "category":"local_reviewed","expected_answer":next(iter(answers)),
            "candidates":[{"id":r["document_id"],"text":r["text"],"grade":r["grade"],"category":"reviewed_local"} for r in candidates.values()]})
    return cases


def decide(metrics):
    reasons=[]
    if metrics.get("reviewed_queries",0)<12:reasons.append("Need twelve complete independently reviewed heldout query pools")
    if metrics.get("heldout_document_families",0)<3:reasons.append("Need three disjoint heldout document families")
    if metrics.get("independent_of_training") is not True:reasons.append("Evaluation overlaps training or lacks a protected snapshot")
    for field,minimum in (("delta_current",.01),("delta_maae",-.02),("delta_base",-.02)):
        if metrics.get(field,-1)<minimum:reasons.append(field+" failed")
    if metrics.get("category_regression",1)>.05:reasons.append("Category regression")
    if metrics.get("new_wrong_answers",1) or metrics.get("gate_violations",1):reasons.append("Answer/evidence safety regression")
    if metrics.get("inference_health") is not True:reasons.append("Inference/resource health failed")
    return {"version":1,"decision":"promote" if not reasons else "review_required_or_reject","reasons":reasons,"metrics":metrics,
            "evaluation_status":"protected_local_regression_independent_of_training_not_fresh_public_blind_acceptance"}


def evaluate_local(candidate,current,base,data):
    from .evaluate import integrated,evaluate_pairs
    cases=evaluation_cases(data["evaluation"])
    inherited=set(json.loads((Path(current)/"beta-model.json").read_text()).get("training_lineage",[]))
    if lineage(data["evaluation"]) & inherited:
        return decide({"independent_of_training":False})
    if not cases:
        return decide({"reviewed_queries":0,"heldout_document_families":0,"independent_of_training":True})
    # Exact heldout pool is fully judged. No unobserved result is labelled negative.
    runs={"candidate":integrated(candidate,cases),"current":integrated(current,cases),"base":integrated(base,cases)}
    from ..evaluation import ranking_metrics
    def average(key):
        return statistics.mean(ranking_metrics(r["candidate"],r["judgments"])["ndcg10"] for r in runs[key]["records"])
    maae=statistics.mean(ranking_metrics(r["baseline"],r["judgments"])["ndcg10"] for r in runs["candidate"]["records"])
    protected=json.loads((Path(base)/"regression.json").read_text(encoding="utf-8"))
    training_pairs={(r["question"].casefold(),r["text"]) for r in data["train"]+data["validation"]}
    if any((c["question"].casefold(),p["text"]) in training_pairs for c in protected for p in c["candidates"]):
        return decide({"independent_of_training":False})
    broad_candidate=evaluate_pairs(candidate,protected);broad_current=evaluate_pairs(current,protected)
    # Compare actual deterministic answer outputs with human-supplied expected
    # answers; no relevance-model score can pass this test by itself.
    new_wrong=0
    for c,new,old in zip(cases,runs["candidate"]["records"],runs["current"]["records"]):
        expected=c["expected_answer"]
        def correct(row):
            answer=row.get("featured_answer")
            return answer is None if expected is None else bool(answer and expected.casefold() in answer.casefold())
        if not correct(new) and correct(old):new_wrong+=1
    metrics={"reviewed_queries":len(cases),"heldout_document_families":len({r["document_family"] for r in data["evaluation"]}),
       "independent_of_training":True,"delta_current":average("candidate")-average("current"),
       "delta_maae":average("candidate")-maae,"delta_base":average("candidate")-average("base"),
       "category_regression":max(0,broad_current["ndcg10"]-broad_candidate["ndcg10"]),
       "new_wrong_answers":new_wrong,"gate_violations":runs["candidate"]["gate_violations"],"inference_health":False}
    return {**decide(metrics),"comparisons":{k:{f:v for f,v in run.items() if f!="records"} for k,run in runs.items()},
            "protected_regression":{"candidate_ndcg10":broad_candidate["ndcg10"],"current_ndcg10":broad_current["ndcg10"]}}
