"""Package original manuscripts, append locally, and audit through PESE's real indexers.

Run with the repository's Python environment from any directory. No ranking or model
configuration is changed. --install affects only the local JSON document store;
--dense rebuilds the existing derived vector cache using the real embedding model.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "engine/data/knowledge_corpus"
STORE = ROOT / "engine/data/firestore_documents.json"
STAMP = "2026-10-22T00:00:00+05:00"
WORDS = re.compile(r"\b\w+(?:[-']\w+)*\b", re.UNICODE)
MAINS = ["history.md", "conflicts.md", "countries.md", "people.md", "consoles.md", "games.md", "science.md", "comparisons.md"]
DETAILS = ["longform.md", "history_details.md", "country_details.md", "game_details.md", "comparison_notes.md"]
RELATED = {
    "roman-republic": ["roman-empire", "julius-caesar", "augustus"],
    "roman-empire": ["roman-republic", "byzantine-empire", "roman-byzantine-comparison"],
    "mongol-empire": ["genghis-khan", "kublai-khan", "mongol-mughal-comparison"],
    "mughal-empire": ["mongol-mughal-comparison", "british-raj"],
    "british-empire": ["british-raj", "british-africa", "decline-british-empire"],
    "world-war-one": ["ww1-causes", "western-front", "treaty-versailles"],
    "world-war-two": ["ww2-causes", "invasion-poland", "end-world-war-two"],
    "playstation-4": ["playstation-4-pro", "ps4-versus-ps5"],
    "playstation-5": ["playstation-history", "ps4-versus-ps5"],
    "xbox-one": ["xbox-history", "xbox-one-versus-series"],
    "xbox-series-x": ["xbox-series-s", "xbox-one-versus-series"],
    "internet": ["world-wide-web", "internet-web-comparison"],
    "artificial-intelligence": ["machine-learning", "neural-networks"],
    "solar-system": ["sun", "earth", "jupiter"],
    "pakistan": ["muhammad-ali-jinnah", "liaquat-ali-khan", "indian-independence"],
    "red-dead-redemption-two": ["red-dead-redemption", "release-story-dates"],
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def word_count(text):
    return len(WORDS.findall(text))


def sections(path):
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^@@(\+?) ([^\n]+)\n", text, re.M))
    if not matches:
        raise ValueError(f"No articles in {path.name}")
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        yield bool(match[1]), match[2].strip(), text[match.end():end].strip()


def assemble():
    from engine.indexing.document import Document
    sources = read_json(DATA / "sources.json")
    articles = {}
    for filename in MAINS:
        for is_detail, header, body in sections(DATA / filename):
            assert not is_detail, filename
            fields = [x.strip() for x in header.split("|")]
            assert len(fields) == 6, header
            slug, title, category, sub_category, aliases, structures = fields
            assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug), slug
            assert slug not in articles, f"Duplicate slug: {slug}"
            articles[slug] = dict(title=title, category=category, sub_category=sub_category,
                                  aliases=[x.strip() for x in aliases.split(",")],
                                  structures=structures.split(","), body=body, manuscript=filename)
    for filename in DETAILS:
        for is_detail, slug, body in sections(DATA / filename):
            assert is_detail and slug in articles, (filename, slug)
            articles[slug]["body"] += "\n\n" + body
    documents, manifest = [], []
    for slug, article in articles.items():
        content = f"# {article['title']}\n\n{article['body']}\n"
        first_paragraph = article["body"].split("\n\n")[0]
        description = first_paragraph if len(first_paragraph) <= 250 else first_paragraph[:247].rsplit(" ", 1)[0] + "..."
        doc = Document(id="kc-" + slug, slug="kc-" + slug, title=article["title"],
                       content=content, meta_description=description, keywords=article["aliases"],
                       internal_links=["kc-" + s for s in RELATED.get(slug, [])],
                       source_type="authored", status="published", created_at=STAMP, updated_at=STAMP)
        doc.headings = doc.extract_headings_from_content()
        documents.append(doc.to_dict())
        checks = [s for s in sources if slug in s["documents"]]
        count = word_count(content)
        metadata = dict(id=doc.id, slug=doc.slug, title=doc.title, category=article["category"],
                        sub_category=article["sub_category"], aliases=article["aliases"],
                        entities=article["aliases"], topics=[article["category"], article["sub_category"]],
                        source_type="authored", authored_on="2026-10-22", manuscript=article["manuscript"],
                        structures=sorted(set(article["structures"]) - {"long"}), word_count=count,
                        length_band="long" if count >= 700 else "medium" if count >= 300 else "short" if count >= 150 else "focused",
                        last_verified="2026-10-22" if checks else None,
                        verification_scope=[{"source_id": s["id"], "claims": s["claims"]} for s in checks],
                        review_status="Selected claims checked" if checks else "Original synthesis; not exhaustively source-audited",
                        content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest())
        manifest.append(metadata)
    return documents, manifest


def duplicate_audit(records):
    def normalized(text):
        return " ".join(x.casefold() for x in WORDS.findall(text))
    names = Counter(x["title"].strip().casefold() for x in records)
    exact = {}
    shingles = []
    for doc in records:
        norm = normalized(doc["content"])
        exact.setdefault(hashlib.sha256(norm.encode()).hexdigest(), []).append(doc["id"])
        tokens = norm.split()
        shingles.append(set(tuple(tokens[i:i+5]) for i in range(max(0, len(tokens)-4))))
    near, closest = [], []
    for i, left in enumerate(shingles):
        for j in range(i):
            right = shingles[j]
            if not left or not right:
                continue
            overlap = len(left & right)
            jaccard = overlap / len(left | right)
            containment = overlap / min(len(left), len(right))
            pair = dict(documents=[records[j]["id"], records[i]["id"]],
                        jaccard=round(jaccard, 4), containment=round(containment, 4))
            if jaccard >= .35 or containment >= .65:
                near.append(pair)
            closest.append(pair)
    return dict(duplicate_titles=[name for name, count in names.items() if count > 1],
                exact_duplicates=[ids for ids in exact.values() if len(ids) > 1],
                near_duplicate_candidates=near,
                nearest_pairs=sorted(closest, key=lambda x: x["jaccard"], reverse=True)[:10],
                method="Casefolded word sequences; exact SHA256; 5-word shingle Jaccard >= .35 OR containment >= .65. Related topics are allowed; candidates require review.")


def validate_and_index(combined, metadata, dense=False):
    from engine.indexing.document import Document
    from engine.indexing.inverted_index import InvertedIndex
    from engine.passages.extractor import PassageExtractor
    from engine.link_graph.graph import LinkGraph
    from engine.link_graph.authority import LinkAuthorityCalculator
    docs = [Document.from_dict(d) for d in combined.values()]
    assert len({d.id for d in docs}) == len(docs)
    assert len({d.slug for d in docs}) == len(docs)
    index, extractor = InvertedIndex(), PassageExtractor()
    passage_map = {}
    for doc in docs:
        assert doc.id and doc.slug and doc.title.strip() and doc.content.strip(), doc.id
        passages = extractor.extract_passages(doc)
        assert passages, f"No passages: {doc.id}"
        assert all(p.doc_id == doc.id and p.text.strip() for p in passages), doc.id
        passage_map[doc.id] = passages
        index.index_document(doc, passages)
    assert index.total_docs == len(docs)
    assert set(index.documents) == set(combined)
    assert len(index.passages) == sum(len(p) for p in passage_map.values())
    graph = LinkGraph()
    graph.build_from_documents(docs)
    auth = LinkAuthorityCalculator(graph)
    auth.compute_scores()
    for meta in metadata:
        native = combined[meta["id"]]
        assert native["status"] == "published"
        assert "\ufffd" not in native["content"], meta["id"]
        assert meta["word_count"] >= 100, meta["id"]
        assert all(target in {d.slug for d in docs} for target in native["internal_links"]), meta["id"]
    result = dict(loadable_documents=len(docs), lexical_documents=index.total_docs,
                  passages=len(index.passages), lexical_terms=len(index.index), graph_nodes=len(graph.nodes))
    if dense:
        from engine.semantic.index import VectorIndex
        import numpy as np
        vector = VectorIndex()
        vector.build_index(docs, passage_map)
        assert {m.doc_id for m in vector.doc_meta} == set(combined)
        assert len(vector.passage_meta) == len(index.passages)
        assert np.isfinite(vector.doc_vectors).all() and np.isfinite(vector.passage_vectors).all()
        assert np.allclose(np.linalg.norm(vector.doc_vectors, axis=1), 1, atol=1e-4)
        reloaded = VectorIndex()
        assert reloaded.load_from_disk()
        assert len(reloaded.doc_meta) == len(docs)
        assert np.array_equal(reloaded.doc_vectors, vector.doc_vectors)
        result["dense"] = dict(provider=vector.provider.get_metadata(), documents=len(vector.doc_meta),
                               passages=len(vector.passage_meta), reload_verified=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--dense", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    baseline = read_json(DATA / "baseline.json")
    originals = read_json(DATA / "existing_documents.snapshot.json")
    assert hashlib.sha256((DATA / "existing_documents.snapshot.json").read_bytes()).hexdigest() == baseline["store_sha256"]
    changed = [name for name, digest in baseline["protected_files"].items()
               if not (ROOT / name).is_file() or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    # Other chats may be editing this shared workspace. Record their changes;
    # never reset them or claim that the entire workspace stayed unchanged.
    if changed:
        print("Pre-existing files changed outside this corpus builder:", json.dumps(changed), flush=True)
    own_scripts = {"scripts/build_knowledge_corpus.py", "scripts/build_knowledge_queries.py", "scripts/evaluate_knowledge_corpus.py"}
    added_elsewhere = []
    for directory in ("engine", "web/src", "scripts"):
        for parent, dirs, files in os.walk(ROOT / directory):
            dirs[:] = [d for d in dirs if d not in (".venv", "__pycache__")]
            for filename in files:
                path = Path(parent) / filename
                relative = path.relative_to(ROOT).as_posix()
                if path.suffix in (".py", ".ts", ".tsx", ".ps1", ".bat", ".pt", ".pth", ".onnx") and relative not in baseline["protected_files"] and relative not in own_scripts:
                    added_elsewhere.append(relative)
    records, manifest = assemble()
    assert len(records) >= 120
    current = read_json(STORE)
    assert all(current.get(key) == value for key, value in originals.items()), "An original record was altered"
    previous_package = {d["id"]: d for d in read_json(DATA / "documents.json")} if (DATA / "documents.json").exists() else {}
    for d in records:
        if d["id"] in current:
            assert current[d["id"]] == d or current[d["id"]] == previous_package.get(d["id"]), f"Edited or colliding ID: {d['id']}"
    combined = dict(current)
    combined.update({d["id"]: d for d in records})
    audit = duplicate_audit(list(combined.values()))
    assert not audit["duplicate_titles"], audit["duplicate_titles"]
    assert not audit["exact_duplicates"], audit["exact_duplicates"]
    checks = validate_and_index(combined, manifest, dense=args.dense)
    write_json(DATA / "documents.json", records)
    write_json(DATA / "manifest.json", dict(schema_version=1, documents=manifest,
               metadata_policy="Companion metadata is not added to PESE's model or used as ranking hints. Verification dates apply only to the listed claims, not exhaustive fact checking."))
    if args.install:
        assert not any(os.getenv(name) for name in ("FIRESTORE_EMULATOR_HOST", "GOOGLE_APPLICATION_CREDENTIALS")), "Local-only installer refuses configured remote/emulator environments"
        assert read_json(STORE) == current, "Store changed during validation; retry to preserve concurrent edits"
        write_json(STORE, combined)
        from engine.indexing.store import DocumentStore
        store = DocumentStore(storage_path=STORE)
        assert not store.use_firestore
        loaded = store.list_documents(status="published")
        assert {d.id for d in loaded} == set(combined)
        assert all(read_json(STORE)[key] == value for key, value in originals.items())
    words = sum(m["word_count"] for m in manifest)
    report = dict(authored_on="2026-10-22", documents_before=len(originals), documents_added=len(records),
                  documents_after=len(combined), installed=args.install, new_word_count=words,
                  combined_word_count=sum(word_count(d["content"]) for d in combined.values()),
                  category_distribution=dict(Counter(m["category"] for m in manifest)),
                  length_distribution=dict(Counter(m["length_band"] for m in manifest)),
                  structure_counts={name: sum(name in m["structures"] for m in manifest) for name in ("faq", "list", "comparison", "semantic", "narrative", "direct")},
                  long_form_prose=sum(m["word_count"] >= 700 for m in manifest),
                  min_words=min(m["word_count"] for m in manifest), max_words=max(m["word_count"] for m in manifest),
                  native_package_bytes=(DATA / "documents.json").stat().st_size,
                  prospective_store_bytes=len((json.dumps(combined, ensure_ascii=False, indent=2) + "\n").encode("utf-8")),
                  installed_store_bytes=STORE.stat().st_size if args.install else None,
                  checks=checks, duplicate_audit=audit, originals_preserved=True,
                  protected_source_and_model_files_unchanged=len(baseline["protected_files"])-len(changed),
                  preexisting_files_changed_outside_corpus_builder=changed,
                  source_files_added_by_concurrent_work=sorted(added_elsewhere),
                  neural_model_files_unchanged=not any(name.startswith("engine/neural/") for name in changed),
                  existing_evidence_gate_file_unchanged="engine/ranking/evidence_gate.py" not in changed,
                  elapsed_seconds=round(time.perf_counter()-started, 2),
                  limitations=["Length mix is 20 long articles plus medium and short entries; it does not mechanically reproduce the suggested percentages.",
                               "Historical and general-knowledge summaries are original synthesis with selected source checks, not an exhaustive claim-by-claim audit.",
                               "A running API may cache the old store; restart it after file-based installation.",
                               "No Git repository was present in the supplied workspace; no commit was created."])
    write_json(DATA / "validation_report.json", report)
    print(json.dumps({k: v for k, v in report.items() if k not in ("duplicate_audit", "limitations")}, indent=2))
    if audit["near_duplicate_candidates"]:
        print("Near-duplicate candidates require review:", json.dumps(audit["near_duplicate_candidates"]))


if __name__ == "__main__":
    main()
