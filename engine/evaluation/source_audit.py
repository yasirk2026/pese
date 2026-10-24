"""Reproducible source inventories; never reads credentials or private corpus."""
import ast
import importlib.metadata
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SUBSYSTEMS=["api","ranking","retrieval","passages","semantic","indexing","query_analysis","quality","link_graph","discovery","neural","nlp"]
TERMS=re.compile(r'japan|ww2|world war|yasir|bicycle|bycycle|japna|meiji|golden age|healing lounge|payments|1941|1910|2023|2026',re.I)


def run():
    constants=[]
    occurrences=[]
    for subsystem in SUBSYSTEMS:
        for path in sorted((ROOT/"engine"/subsystem).rglob("*.py")):
            source=path.read_text(encoding="utf-8")
            tree=ast.parse(source)
            parents={child:parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
            for node in ast.walk(tree):
                if isinstance(node,ast.Constant) and isinstance(node.value,(int,float)) and not isinstance(node.value,bool):
                    parent=parents.get(node)
                    while parent is not None and not isinstance(parent,(ast.FunctionDef,ast.ClassDef,ast.Module)):
                        parent=parents.get(parent)
                    constants.append(dict(file=str(path.relative_to(ROOT)),line=node.lineno,value=node.value,
                        owner=getattr(parent,"name","module"),purpose_context=source.splitlines()[node.lineno-1].strip(),
                        origin="source literal; no version history available",benchmark_derived="unknown; cannot infer provenance from value",
                        documented=bool(parent and ast.get_docstring(parent)),sensitivity="review context; thresholds/weights high, loop indices low"))
            for line,text in enumerate(source.splitlines(),1):
                if TERMS.search(text):
                    occurrences.append(dict(file=str(path.relative_to(ROOT)),line=line,source=text.strip()))
    versions={}
    for package in ["torch","fastapi","fastembed","uvicorn","numpy","pydantic","firebase-admin","pytest","httpx","onnxruntime","tokenizers"]:
        try: versions[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError: versions[package]=None
    from engine.neural.data.qa_dataset import STAGE_A_SANITY_EXAMPLES,STAGE_B_MICRO_OVERFIT_EXAMPLES,STAGE_C_PUBLIC_QA_CORPUS,build_qa_features
    from engine.evaluation.qa_reader_dataset import BENCHMARK_QA_ITEMS
    training=STAGE_B_MICRO_OVERFIT_EXAMPLES+STAGE_C_PUBLIC_QA_CORPUS
    import random
    from engine.neural.tokenization.bpe_tokenizer import BPETokenizer
    tokenizer_data=json.loads((ROOT/"engine/neural/checkpoints/qa/peseqa0_tokenizer.json").read_text(encoding="utf-8"))
    tokenizer=BPETokenizer(vocab=tokenizer_data["vocab"],merges=[tuple(m) for m in tokenizer_data["merges"]])
    features=[]
    for example in training:features.extend(build_qa_features(example,tokenizer,max_seq_len=128))
    random.Random(42).shuffle(features)
    split=int(len(features)*.85)
    context={e.id:e.context.strip().lower() for e in training}
    train_contexts={context[f.example_id] for f in features[:split]}
    validation_contexts={context[f.example_id] for f in features[split:]}
    overlap=[]
    for item in BENCHMARK_QA_ITEMS:
        for ex in training:
            if item.context.strip().lower()==ex.context.strip().lower():
                overlap.append(dict(benchmark=item.id,train_example=ex.id,type="identical_context"))
    report=dict(numeric_literals=constants,suspicious_term_occurrences=occurrences,installed_versions=versions,
        training=dict(stage_a=len(STAGE_A_SANITY_EXAMPLES),stage_b=len(STAGE_B_MICRO_OVERFIT_EXAMPLES),stage_c=len(STAGE_C_PUBLIC_QA_CORPUS),benchmark=len(BENCHMARK_QA_ITEMS),identical_context_overlap=overlap,
            reconstructed_train_features=split,reconstructed_validation_features=len(features)-split,
            identical_contexts_across_train_validation=len(train_contexts & validation_contexts)),
        test_files=[str(p.relative_to(ROOT)) for p in sorted((ROOT/"engine/tests").glob("test_*.py"))])
    path=ROOT/"docs/audit/source-inventory.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(dict(numeric_literals=len(constants),term_occurrences=len(occurrences),versions=versions,training=report["training"]),indent=2))


if __name__=="__main__":run()
