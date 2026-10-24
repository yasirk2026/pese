"""Release studies over exposed public development data, never the holdout."""
import argparse
import gc
import hashlib
import json
import statistics
import tempfile
import time
from pathlib import Path
from engine.evaluation.phase2f_support import build_engine, closure_documents
from engine.evaluation.independent_dataset import documents, CASES
from engine.evaluation.runtime_audit import rss_mb


ROOT = Path(__file__).resolve().parents[2]


def save(name, payload):
    path = ROOT / "docs" / "audit" / ("phase2f-"+name+".json")
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload.get("summary", payload), indent=2), flush=True)


def ranking():
    with tempfile.TemporaryDirectory() as temp:
        eng = build_engine(documents()+closure_documents(), temp)
        cases = [(q,slug,category) for q,slug,_,category,_ in CASES]
        cases.extend([("what are my camera specifications", "owned", "attribute"),
                      ("what is my camera weight", "owned", "attribute"),
                      ("when did Mira envision NOVA", "coref", "coreference")])
        def assess():
            eng._search_cache.clear()
            records = []
            for query, slug, category in cases:
                res = eng.search(query, skip_qa=True)
                records.append(dict(query=query, category=category, expected=slug,
                    doc1=bool(res and res[0].slug==slug), doc3=any(r.slug==slug for r in res[:3]),
                    spam_win=bool(res and eng._spam[res[0].doc_id]["spam_penalty"]>=0.3),
                    rescued=bool(res and res[0].is_semantic_rescue)))
            return dict(doc_at_1=statistics.mean(r["doc1"] for r in records), doc_at_3=statistics.mean(r["doc3"] for r in records),
                        spam_wins=sum(r["spam_win"] for r in records), attribute_failures=sum(not r["doc1"] for r in records if "attribute" in r["category"]),
                        semantic_rescues=sum(r["rescued"] for r in records), winners=[r["expected"] if r["doc1"] else None for r in records])
        baseline = dict(eng.weights)
        runs = [{"component":"baseline", "factor":1, **assess()}]
        for name in ("title", "heading", "passage", "dense", "rrf", "coverage"):
            for factor in (.8, 1.2):
                eng.weights = dict(baseline)
                eng.weights[name] *= factor
                runs.append(dict(component=name, factor=factor, value=eng.weights[name], **assess()))
        eng.weights = baseline
        for name in ("rescue_threshold", "semantic_weight", "drift_threshold", "relation_threshold"):
            owner = eng.candidate_fuser if name in {"rescue_threshold", "semantic_weight"} else eng.semantic_retriever.drift_detector if name=="drift_threshold" else eng.relation_matcher
            attr = "weak_similarity_threshold" if name=="drift_threshold" else "threshold" if name=="relation_threshold" else name
            initial = getattr(owner, attr)
            for factor in (.8, 1.2):
                setattr(owner, attr, initial*factor)
                runs.append(dict(component=name, factor=factor, value=initial*factor, **assess()))
            setattr(owner, attr, initial)
        save("sensitivity", dict(dataset="exposed diversified development corpus; no tuning on holdout", cases=len(cases), runs=runs,
             summary={"runs":len(runs), "doc1_min":min(r["doc_at_1"] for r in runs), "doc1_max":max(r["doc_at_1"] for r in runs), "max_spam_wins":max(r["spam_wins"] for r in runs)}))


def soak(count):
    with tempfile.TemporaryDirectory() as temp:
        eng = build_engine(documents()+closure_documents(), temp)
        eng.search("when did Orion enter the war", skip_qa=True)
        checkpoints = []
        durations = []
        start = time.perf_counter()
        gc.collect()
        before = rss_mb()
        bases = ["Atlas weight", "Orion history", "Cobalt fee", "camera specifications", "Linden railway"]
        for i in range(1,count+1):
            query = bases[i % len(bases)] + " " + str(100000+i)
            t=time.perf_counter()
            eng.search(query, skip_qa=True, force_raw=True)
            durations.append((time.perf_counter()-t)*1000)
            if i in {100, 1000, 5000, 10000, count}:
                before_gc=rss_mb(); gc.collect()
                search_bytes = sum(len(json.dumps([r.model_dump() for r in rows])) for rows in eng._search_cache.values())
                row=dict(searches=i, rss_before_gc_mb=before_gc, rss_after_gc_mb=rss_mb(),
                    result_cache_entries=len(eng._search_cache), estimated_result_json_bytes=search_bytes,
                    embedding_cache=eng.vector_index.provider._cached_query.cache_info()._asdict(),
                    relation_cache=eng.relation_matcher._embedding.cache_info()._asdict(),
                    elapsed_seconds=round(time.perf_counter()-start,2))
                checkpoints.append(row)
                print(json.dumps(row), flush=True)
        save("soak", dict(summary=dict(distinct_queries=count, rss_before_mb=before, rss_after_mb=rss_mb(),
             duration_seconds=round(time.perf_counter()-start,2), p50_ms=statistics.median(durations), p95_ms=sorted(durations)[int(.95*(len(durations)-1))]),
             checkpoints=checkpoints, conditions="Real BGE, synthetic 39-document corpus; single process, sequential cold query keys, QA disabled. Unique numeric suffixes force cache misses; this is not diverse natural-language accuracy evaluation. JSON byte estimate excludes Python object overhead and traces on list metadata."))


def spelling():
    from engine.query_analysis.spelling import CorpusSpellingCorrector
    from engine.indexing.inverted_index import InvertedIndex
    from engine.passages.extractor import PassageExtractor
    from engine.data.demo_corpus import demo_documents
    index=InvertedIndex()
    for doc in documents()+closure_documents()+demo_documents():
        index.index_document(doc,PassageExtractor().extract_passages(doc))
    corrector=CorpusSpellingCorrector();corrector.build_vocabulary(index.index,raw_terms=index.raw_terms)
    originals=["japan","bicycle","camera","mercury","clinic","payment","installments","railway","observatory","constitution","instructions","telescope","mechanical","specifications","geography","linden","cobalt","citrine","aurora","kestrel"]
    rows=[]
    for word in originals:
        center=len(word)//2
        variants={"transposition":word[:center]+word[center+1]+word[center]+word[center+2:],
            "missing_letter":word[:center]+word[center+1:], "extra_letter":word[:center]+word[center]+word[center:],
            "wrong_vowel":word[:center]+("a" if word[center]!="a" else "e")+word[center+1:],
            "two_edits":word[1:center]+word[center+1:]+word[0]}
        for kind,typo in variants.items():
            result=corrector.correct_token(typo);actual=result.corrected_token if result else typo
            rows.append(dict(input=typo,expected=word,actual=actual,category=kind,changed=actual!=typo,correct=actual==word))
    controls=["cpu","gpu","bge","onnx","grpc","cuda","numpy","pydantic","uvicorn","torch","bm25f","rrf","sqlite","oauth","json","http","https","next.js","typescript","tokenizers","fastembed","protobuf","aperture","shutter","mercury","cobalt","go","rust","c","r","ai","ml","ir","qa","os","api","sql","tcp","udp","ram"]
    control_rows=[]
    for word in controls:
        result=corrector.correct_token(word);actual=result.corrected_token if result else word
        control_rows.append(dict(input=word,actual=actual,changed=actual!=word))
    changed=sum(r["changed"] for r in rows)+sum(r["changed"] for r in control_rows)
    true=sum(r["changed"] and r["correct"] for r in rows)
    save("spelling", dict(summary=dict(typos=len(rows), controls=len(controls), precision=true/changed if changed else None,
        recall=sum(r["correct"] for r in rows)/len(rows),false_correction_rate=sum(r["changed"] for r in control_rows)/len(controls)),
        categories={kind:dict(total=sum(r["category"]==kind for r in rows),correct=sum(r["category"]==kind and r["correct"] for r in rows)) for kind in {r["category"] for r in rows}},
        records=rows,controls=control_rows,limitations="Generated development mutations. Precision includes corrections to a wrong corpus word; conservative misses remain visible. Technical controls may be out of corpus."))


def relations():
    from engine.semantic.provider import FastembedProvider
    from engine.semantic.relations import RelationMatcher
    matcher=RelationMatcher(FastembedProvider())
    pairs=[("Can I split the fee?","Clients may pay in two equal installments.",[]),
       ("When did Arlen dream ASTRA?","Arlen envisioned ASTRA in 2023.",["arlen","astra"]),
       ("What was Helix built with?","Helix was developed using Python.",["helix"]),
       ("When did Toria enter the war?","Toria joined the conflict in 1942.",["toria"]),
       ("Where does Remy live?","Remy resides in Lisbon.",["remy"]),
       ("Can I split the fee?","Clients may book two appointment slots.",[]),
       ("When did Arlen dream ASTRA?","Arlen joined ASTRA in 2024.",["arlen","astra"]),
       ("What was Helix built with?","Helix offers a development newsletter.",["helix"])]
    rows=[dict(query=q,evidence=s,cosine=matcher.similarity(q,s,e),threshold=matcher.threshold) for q,s,e in pairs]
    save("relations",dict(rows=rows,summary={"passing_similarity":sum(r["cosine"]>=matcher.threshold for r in rows),"pairs":len(rows)},
         limitation="Similarity alone is never sufficient for promotion; mandatory entity/property/negation/type/span gates still apply."))


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("mode",choices=["ranking","soak","spelling","relations"]);parser.add_argument("--count",type=int,default=10000)
    args=parser.parse_args()
    {"ranking":ranking,"soak":lambda:soak(args.count),"spelling":spelling,"relations":relations}[args.mode]()
