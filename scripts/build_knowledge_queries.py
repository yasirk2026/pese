"""Build held-out query data with exact evidence offsets; never import it into PESE."""
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "engine/data/knowledge_corpus"


def build():
    documents = json.loads((ROOT / "engine/data/firestore_documents.json").read_text(encoding="utf-8"))
    corpus = json.loads((DATA / "documents.json").read_text(encoding="utf-8"))
    assert all(documents[d["id"]] == d for d in corpus), "Install/index corpus before building ground truth"
    cases, errors = [], []
    for line_number, line in enumerate((DATA / "query_cases.txt").read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        fields = [s.strip() for s in line.split("|")]
        if len(fields) != 5:
            errors.append(f"Line {line_number}: expected five fields")
            continue
        kind, query, keys, answer, notes = fields
        ids = ["kc-" + key for key in keys.split(",")] if keys != "-" else []
        if kind != "buried_answer" and "kc-japan-geography" in ids:
            ids += [key for key, doc in documents.items() if doc["title"] == "Japan"]
        assert all(key in documents for key in ids), (line_number, ids)
        spans = []
        if answer != "-":
            for key in ids:
                text = documents[key]["content"]
                match = re.search(re.escape(answer), text, re.IGNORECASE)
                if match:
                    block_start = text.rfind("\n\n", 0, match.start()) + 2
                    block_end = text.find("\n\n", match.end())
                    if block_end < 0:
                        block_end = len(text)
                    spans.append(dict(document_id=key, start_char=match.start(), end_char=match.end(),
                                      quote=text[match.start():match.end()],
                                      context=text[block_start:block_end].strip(),
                                      context_word_offset=len(re.findall(r"\b\w+\b", text[:match.start()]))))
            if not spans:
                errors.append(f"Line {line_number}: no evidence for {answer!r} in {ids}")
        expected_behavior = "abstain" if kind == "abstention" else "clarify_or_qualified_overview" if kind == "ambiguity" else "answer"
        labels = [kind]
        if kind == "exact_factual":
            labels.append("lexical")
        if kind in ("semantic", "natural_language", "long_question", "buried_answer", "comparison"):
            labels.append("semantic") if "semantic" not in labels else None
        qa = kind not in ("ambiguity",)
        if qa:
            labels.append("qa")
        cases.append(dict(id=f"kcq-{len(cases)+1:03}", query=query, query_type=kind, labels=labels,
                          expected_document=ids[0] if ids else None, acceptable_documents=ids,
                          expected_answer=None if answer == "-" else answer,
                          answer_present=kind != "abstention" and bool(spans),
                          expected_behavior=expected_behavior, is_qa=qa,
                          evidence_spans=spans, as_of="2026-10-22", notes=notes,
                          scoring_note="Expected answer is a reference span/key phrase; explanations and multi-part comparisons require human semantic review. Substring scores are diagnostics only."))
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    assert len(cases) >= 100
    assert sum(c["expected_behavior"] == "abstain" for c in cases) >= 15
    assert len({c["query"].casefold() for c in cases}) == len(cases)
    assert all(c["expected_answer"] is None and not c["evidence_spans"] for c in cases if c["expected_behavior"] == "abstain")
    summary = dict(total_queries=len(cases), primary_types=dict(Counter(c["query_type"] for c in cases)),
                   label_counts=dict(Counter(label for c in cases for label in c["labels"])),
                   qa_queries=sum(c["is_qa"] for c in cases),
                   abstention_queries=sum(c["expected_behavior"] == "abstain" for c in cases),
                   ambiguity_queries=sum(c["query_type"] == "ambiguity" for c in cases),
                   unique_positive_primary_documents=len({c["expected_document"] for c in cases if c["expected_behavior"] == "answer"}),
                   evidence_offsets_verified=True,
                   intended_use="Held-out retrieval and QA inspection only. Do not import, train on, or feed labels to the engine.")
    value = dict(schema_version=1, created_on="2026-10-22", summary=summary, queries=cases,
                 abstention_review="Manually scoped to facts absent from all 212 installed records, including missing attributes of known entities. These are questions, never indexed documents.")
    (DATA / "queries.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    build()
