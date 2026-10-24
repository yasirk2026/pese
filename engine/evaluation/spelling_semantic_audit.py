"""Inspectable spelling controls and semantic phrase probes; no private writes."""
import json
from pathlib import Path
import numpy as np
from engine.indexing.document import Document
from engine.indexing.inverted_index import InvertedIndex
from engine.passages.extractor import PassageExtractor
from engine.query_analysis.spelling import CorpusSpellingCorrector
from engine.semantic.provider import FastembedProvider


def run():
    root=Path(__file__).resolve().parents[2]
    raw=json.loads((root/"engine/data/firestore_documents.json").read_text(encoding="utf-8"))
    index=InvertedIndex()
    for item in raw.values():
        if item.get("status")=="published":
            doc=Document(**item);index.index_document(doc,PassageExtractor().extract_passages(doc))
    corrector=CorpusSpellingCorrector();corrector.build_vocabulary(index.index,raw_terms=index.raw_terms)
    typos={"japna":"japan","bycycle":"bicycle","purhcase":"purchase","firbase":"firebase","hydrtion":"hydration","pyskology":"psychology","bicycel":"bicycle","japn":"japan"}
    controls=["enter","invade","surrender","promulgate","specification","firebase","next.js","bm25f","torch","uvicorn","pydantic","numpy","onnx","sqlite","grpc","cuda"]
    records=[]
    for word,expected in list(typos.items())+[(word,word) for word in controls]:
        correction=corrector.correct_token(word)
        actual=correction.corrected_token if correction else word
        records.append(dict(input=word,expected=expected,actual=actual,is_typo=word in typos,changed=actual!=word,correct=actual==expected))
    correct_changes=sum(r["is_typo"] and r["correct"] for r in records)
    changes=sum(r["changed"] for r in records)
    metrics=dict(typo_cases=len(typos),controls=len(controls),correction_precision=correct_changes/changes if changes else None,correction_recall=correct_changes/len(typos),false_correction_rate=sum(not r["is_typo"] and r["changed"] for r in records)/len(controls))
    # Instalment is also a valid English spelling, so record its normalization
    # without mislabeling preservation as a typo-recovery failure.
    variant=corrector.correct_token("instalment")
    phrases=["bike","cycle","bicycle","japan","japanese","japna","payment","installment","split fee","flexible payments","Yasir joined an organization in November 2024"]
    provider=FastembedProvider();vectors=provider.embed_texts(phrases)
    report=dict(spelling=dict(metrics=metrics,records=records,orthographic_variant=dict(input="instalment",output=variant.corrected_token if variant else "instalment")),semantic=dict(provider=provider.get_metadata(),phrases=phrases,cosine_similarity=np.round(vectors@vectors.T,4).tolist()),limitations="Small exposed controls, not a dictionary-wide precision estimate. Cosine similarity probes topic affinity, not answer entailment.")
    (root/"docs/audit/spelling-semantic.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(metrics,indent=2))


if __name__=="__main__":run()
