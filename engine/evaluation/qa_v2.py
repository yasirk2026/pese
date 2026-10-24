"""Fresh public source-grouped QA evaluation; does not train or promote a model."""
import hashlib
import json
import re
import statistics
import tempfile
from collections import Counter
from pathlib import Path
from engine.evaluation.phase2f_support import build_engine, document
from engine.neural.data.contracts import QAExample
from engine.neural.data.grouped_split import context_hash, manifest
from engine.neural.tokenization.bpe_tokenizer import BPETokenizer

ROOT=Path(__file__).resolve().parents[2]
ROWS = {
 "train":[
   ("quasar", "Quasar notes", "A quasar is a luminous galactic nucleus.", "What is a quasar?", "a luminous galactic nucleus", "What is its catalog number?"),
   ("resistor", "Resistor notes", "A resistor limits electric current.", "What does a resistor limit?", "electric current", "Who manufactured this resistor?"),
   ("enzyme", "Enzyme notes", "An enzyme accelerates a chemical reaction.", "What does an enzyme accelerate?", "a chemical reaction", "What is the enzyme's mass?"),
   ("cache", "Cache notes", "A cache stores frequently accessed data.", "What does a cache store?", "frequently accessed data", "What is this cache's capacity?")],
 "validation":[
   ("fjord", "Fjord notes", "A fjord is a narrow inlet with steep cliffs.", "What is a fjord?", "a narrow inlet with steep cliffs", "How deep is this fjord?"),
   ("lichen", "Lichen notes", "Lichen combines a fungus and a photosynthetic partner.", "What does lichen combine?", "a fungus and a photosynthetic partner", "Who named this lichen?")],
 "test":[
   ("velora", "Velora lantern", "The Velora lantern launched in 2016. The Velora lantern was discontinued in 2021.", "When did the Velora lantern launch?", "2016", "What color is the Velora lantern?"),
   ("thistle", "Thistle Archive", "Thistle Archive opened in 1987. Thistle Archive reopened in 2009.", "When did Thistle Archive reopen?", "2009", "Who designed Thistle Archive?"),
   ("bracken", "Bracken tablet", "The Bracken tablet weighs 620 grams and has a ceramic frame.", "How much does the Bracken tablet weigh?", "620 grams", "What is the Bracken tablet battery capacity?"),
   ("mistral", "Mistral library", "Mistral library is located in Cedar Bay.", "Where is Mistral library located?", "Cedar Bay", "When did Mistral library open?"),
   ("silverfin", "Silverfin workshop", "Silverfin workshop accepts installment payments. Silverfin workshop does not accept cryptocurrency.", "Does Silverfin workshop accept cryptocurrency?", "Silverfin workshop does not accept cryptocurrency.", "Who founded Silverfin workshop?"),
   ("tavin", "Tavin expedition", "Tavin launched an expedition in 1998. He ended the expedition in 2003.", "When did Tavin end the expedition?", "2003", "How much did Tavin's expedition cost?"),
   ("dovetail", "Dovetail service", "Dovetail service uses a message queue to coordinate tasks.", "What does Dovetail service use to coordinate tasks?", "a message queue", "What programming language is Dovetail service written in?"),
   ("sorrel", "Sorrel instrument", "Sorrel was created by Elian Shore.", "Who created Sorrel?", "Elian Shore", "How much does Sorrel cost?")]
}


def dataset():
    split={}
    for part, rows in ROWS.items():
        examples=[]
        for source,title,context,question,answer,negative in rows:
            for suffix,q,a in (("positive",question,answer),("negative",negative,None)):
                start=context.find(a) if a else None
                examples.append(QAExample(id=source+":"+suffix,source_doc_id=source,question=q,context=context,
                    answer_text=a,answer_start_char=start,answer_end_char=start+len(a) if a else None,is_answerable=bool(a),
                    metadata={"entity":source,"paraphrase_family":source,"split":part}))
        split[part]=examples
    return split


def norm(text):
    text=re.sub(r"[^\w\s]"," ",(text or "").lower())
    return " ".join(t for t in text.split() if t not in {"a","an","the"})


def f1(actual, expected):
    a,b=Counter(norm(actual).split()),Counter(norm(expected).split())
    if not a or not b:return float(a==b)
    common=sum((a&b).values())
    return 2*common/(sum(a.values())+sum(b.values()))


def run():
    import torch
    torch.set_num_threads(2)
    split=dataset(); m=manifest(split)
    from engine.neural.data.qa_dataset import STAGE_A_SANITY_EXAMPLES,STAGE_B_MICRO_OVERFIT_EXAMPLES,STAGE_C_PUBLIC_QA_CORPUS
    legacy={context_hash(e.context) for e in STAGE_A_SANITY_EXAMPLES+STAGE_B_MICRO_OVERFIT_EXAMPLES+STAGE_C_PUBLIC_QA_CORPUS}
    assert not {context_hash(e.context) for e in split["test"]}.intersection(legacy)
    tokenizer=BPETokenizer();tokenizer.train([e.question+" "+e.context for e in split["train"]],target_vocab_size=450,min_frequency=1)
    toksha=hashlib.sha256(json.dumps({"vocab":tokenizer.vocab,"merges":tokenizer.merges},sort_keys=True).encode()).hexdigest()
    rows=[]
    with tempfile.TemporaryDirectory() as temp:
        docs=[document(source,title,context) for source,title,context,*_ in ROWS["test"]]
        eng=build_engine(docs,temp)
        reader=eng._get_qa_reader()
        for example in split["test"]:
            base=eng.search(example.question,skip_qa=True)
            shadow=eng.search(example.question,skip_qa=False)
            actual=base[0].featured_answer if base else None
            augmented=shadow[0].featured_answer if shadow else None
            assert actual==augmented
            result=reader.read_passage(example.question,example.context) if reader else None
            predicted=result.answer if result and result.answerable else None
            trace=shadow.qa_trace or {}
            search_shadow=trace.get("shadow_answer")
            valid_main=bool(actual and example.answer_text and norm(example.answer_text) in norm(actual) and
                            base[0].slug==example.source_doc_id) if example.is_answerable else not actual
            valid_model=norm(predicted)==norm(example.answer_text)
            rows.append(dict(id=example.id,question=example.question,expected=example.answer_text,answerable=example.is_answerable,
                deterministic=actual,plus_shadow=augmented,complete_search_correct=valid_main,
                qa_passage_answer=predicted,qa_exact_match=valid_model,qa_token_f1=f1(predicted,example.answer_text),
                qa_answerability_correct=bool(predicted)==example.is_answerable,
                qa_span_grounded=bool(predicted and predicted in example.context) if predicted else None,
                qa_confidence=result.answer_confidence if result else None,
                complete_search_shadow=search_shadow,shadow_promoted=False))
    positives=[r for r in rows if r["answerable"]]; negatives=[r for r in rows if not r["answerable"]]
    predicted_no=[r for r in rows if not r["qa_passage_answer"]]
    true_no=sum(not r["answerable"] for r in predicted_no)
    calibration=[]
    for low,high in ((0,.5),(.5,.7),(.7,.9),(.9,1.00001)):
        bucket=[r for r in rows if r["qa_confidence"] is not None and low<=r["qa_confidence"]<high]
        calibration.append(dict(low=low,high=min(high,1),count=len(bucket),exact_match=statistics.mean(r["qa_exact_match"] for r in bucket) if bucket else None))
    report=dict(dataset_status="exposed source-grouped public evaluation, not independent holdout",manifest=m,
        tokenizer=dict(policy="V2 training examples only; not used to alter legacy checkpoint",sha256=toksha,vocab_size=tokenizer.vocab_size),
        legacy_checkpoint=dict(status="EXPERIMENT",original_leakage="5 identical train/validation contexts; 9/15 old benchmark items shared training contexts; original tokenizer saw validation. These cannot be retroactively repaired.",
          test_identical_context_overlap=0,trained_v2=False),
        summary=dict(test_examples=len(rows),answerable=len(positives),unanswerable=len(negatives),checkpoint_available=reader is not None,
          complete_search_accuracy=statistics.mean(r["complete_search_correct"] for r in rows),incremental_complete_search_gain=0,
          qa_exact_match=statistics.mean(r["qa_exact_match"] for r in rows),qa_token_f1=statistics.mean(r["qa_token_f1"] for r in rows),
          qa_answerability_accuracy=statistics.mean(r["qa_answerability_correct"] for r in rows),
          no_answer_precision=true_no/len(predicted_no) if predicted_no else None,no_answer_recall=true_no/len(negatives),
          grounded_span_rate=statistics.mean(r["qa_span_grounded"] for r in rows if r["qa_span_grounded"] is not None) if any(r["qa_span_grounded"] is not None for r in rows) else None),
        calibration=calibration,records=rows,decision="EXPERIMENT: no promotion; shadow has zero authoritative answer impact by design")
    target=ROOT/"docs/audit/phase2f-qa-v2.json";target.write_text(json.dumps(report,indent=2),encoding="utf-8")
    (ROOT/"docs/audit/phase2f-qa-v2-dataset.json").write_text(json.dumps({part:[e.model_dump() for e in examples] for part,examples in split.items()},indent=2),encoding="utf-8")
    print(json.dumps(report["summary"],indent=2))


if __name__=="__main__":run()
