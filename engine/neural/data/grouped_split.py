"""Source/entity/family grouping before tokenization. No window-level split."""
import hashlib
import re


def normalized(text):
    return " ".join(re.findall(r"\w+", text.lower()))


def context_hash(text):
    return hashlib.sha256(normalized(text).encode()).hexdigest()


def grouped_split(examples, forbidden_contexts=()):
    forbidden = {context_hash(c) for c in forbidden_contexts}
    rows = [ex for ex in examples if context_hash(ex.context) not in forbidden]
    parent = list(range(len(rows)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    seen = {}
    for i, ex in enumerate(rows):
        keys = ["context:"+context_hash(ex.context)]
        if ex.source_doc_id: keys.append("source:"+ex.source_doc_id)
        for field in ("entity", "paraphrase_family"):
            if ex.metadata.get(field): keys.append(field+":"+str(ex.metadata[field]).lower())
        # Legacy examples lack source ids: group shared named entities too.
        names = re.findall(r"\b[A-Z][A-Za-z0-9-]*(?:\s+[A-Z][A-Za-z0-9-]*)*\b", ex.context)
        if not ex.source_doc_id:
            keys.extend("name:"+n.lower() for n in names if n not in {"The", "A", "An", "This", "It", "In", "Real", "Personal Evil Search Engine"})
        for key in keys:
            if key in seen: parent[root(i)] = root(seen[key])
            else: seen[key] = i
    groups = {}
    for i, ex in enumerate(rows): groups.setdefault(root(i), []).append(ex)
    ordered = sorted(groups.values(), key=lambda g: hashlib.sha256("|".join(sorted(e.id for e in g)).encode()).hexdigest())
    split = {"train":[], "validation":[], "test":[]}
    for i, group in enumerate(ordered):
        destination = "test" if i % 7 == 0 else "validation" if i % 7 == 1 else "train"
        split[destination].extend(group)
    return split


def manifest(split):
    result = {}
    for name, rows in split.items():
        result[name] = [{"id":e.id, "source":e.source_doc_id, "context_sha256":context_hash(e.context),
                         "example_sha256":hashlib.sha256(e.model_dump_json().encode()).hexdigest()} for e in rows]
    hashes = [{r["context_sha256"] for r in rows} for rows in result.values()]
    assert all(not a.intersection(b) for i,a in enumerate(hashes) for b in hashes[i+1:])
    return result
