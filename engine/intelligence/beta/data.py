"""Basic English DATA-BETA-1. Original synthetic specifications, CC0-1.0.

Labels describe retrieval utility (0 unrelated, 1 topical, 2 specific utility),
not factual truth/answer certification. They are specification-derived, not
independently human-adjudicated. No private queries or documents are accessed.
"""
import hashlib
import json
from pathlib import Path
from ..evidence import digest

TOPICS = [
    ("neural search", "learned ranking", "find useful passages", "keyword matches were misleading"),
    ("drive backup", "cloud copies", "recover saved documents", "the old disk could fail"),
    ("journal notes", "daily writing", "remember past decisions", "important details were forgotten"),
    ("website ideas", "page designs", "plan a small site", "the earlier layout was confusing"),
    ("brain storage", "knowledge folders", "keep documents portable", "application updates replace program files"),
    ("failed experiments", "unsuccessful trials", "record what went wrong", "the test results were unreliable"),
    ("search feedback", "result ratings", "remember explicit preferences", "some useful pages were ranked too low"),
    ("document indexing", "searchable records", "find recently edited notes", "the previous index was stale"),
]
NAMES = {"train":["alder","beacon","cedar","dawn","elm","falcon","grove","harbor"],
         "validation":["iris","juniper","kestrel","linden"],
         "calibration":["maple","nectar","olive"],
         "acceptance":["pearl","quartz","raven","spruce"]}
QUERY = {
 "train":["why did {name} change {topic}?", "find {name}'s notes about {topic}"],
 "validation":["what made {name} revise {topic}?", "show the writing on {topic} by {name}"],
 "calibration":["{name} changed {topic} for what reason?", "where are {name}'s records on {topic}?"],
 "acceptance":["what prompted {name}'s decision on {topic}?", "locate the document discussing {topic} for {name}"]}


def build_splits():
    splits = {}
    for split,names in NAMES.items():
        cases=[]
        for n,name in enumerate(names):
            for t,(topic,alias,purpose,cause) in enumerate(TOPICS):
                family=f"{split}:{name}:{t}"
                other=names[(n+1)%len(names)]
                if split=="train":
                    specific=f"{name} changed {topic} because {cause}. the aim was to {purpose}."
                    paraphrase=f"{name} revised {alias}. {cause}, so the new approach would {purpose}."
                elif split=="validation":
                    specific=f"a decision by {name}: update {topic}. the reason was that {cause}."
                    paraphrase=f"to {purpose}, {name} chose a different approach to {alias}; {cause}."
                elif split=="calibration":
                    specific=f"the record explains {name}'s revision of {topic}: {cause}."
                    paraphrase=f"{cause}. this led {name} to change {alias} and {purpose}."
                else:
                    specific=f"in {name}'s project diary, {topic} was reconsidered after finding that {cause}."
                    paraphrase=f"a note from {name} links the {alias} decision to one problem. {cause}."
                for style,template in enumerate(QUERY[split]):
                    question=template.format(name=name,topic=topic)
                    categories=["causal_cross_sentence","natural_document_search"]
                    # Deliberate spelling/partial-query variants stay in their
                    # source family, never creating a new independent group.
                    if style==1 and (n+t)%5==0:
                        question=question.replace("notes","ntoes").replace("writing","writng").replace("document","documnt")
                    rows=[
                      ("specific",specific,2), ("paraphrase",paraphrase,2),
                      ("wrong_relation",f"{name} read about {topic}. the meeting was held on monday, but no reason for a change was recorded.",1 if style==0 else 2),
                      ("wrong_entity",f"{other} changed {topic} because {cause}. this entry is only about {other}.",0),
                      ("unrelated",f"{name} watered the garden and repaired a bicycle. these records contain no project discussion.",0),
                      ("missing",f"{name}'s {topic} record is incomplete. the cause of the decision is unknown.",1 if style==0 else 2),
                    ]
                    # Contradictions/temporal conflicts are topical evidence,
                    # not automatic negatives or permission to answer.
                    if (n+t)%4==0:
                        rows[-1]=("temporal_conflict",f"{name}'s {topic} notes list both 2023 and 2024 for the change. the dates conflict and no reason is given.",1 if style==0 else 2)
                    cases.append({"id":family+f":q{style}","group":family,"document_family":family,
                       "template_family":f"{split}:prose:{style}","category":categories[style],"question":question,
                       "source_kind":"synthetic_specification","label_trust":"rule_checked_not_independent_human_review",
                       "candidates":[{"id":family+":"+kind,"text":text,"grade":grade,"category":kind} for kind,text,grade in rows]})
        splits[split]=cases
    return splits


def freeze(directory):
    target=Path(directory)
    target.mkdir(parents=True,exist_ok=False)
    splits=build_splits()
    seen={}
    for split,cases in splits.items():
        for case in cases:
            for field in ("group","document_family","template_family"):
                key=(field,case[field])
                if key in seen and seen[key]!=split:
                    raise ValueError("Cross-split family contamination")
                seen[key]=split
    files={}
    for split,cases in splits.items():
        raw=json.dumps(cases,sort_keys=True,ensure_ascii=False,indent=2).encode()
        (target/f"{split}.json").write_bytes(raw)
        files[f"{split}.json"]={"sha256":hashlib.sha256(raw).hexdigest(),"queries":len(cases),
                              "pairs":sum(len(c["candidates"]) for c in cases)}
    manifest={"version":1,"dataset":"PESE-BASIC-ENGLISH-BETA-1","license":"CC0-1.0",
       "objective":"retrieval_relevance","provenance":"Original synthetic specification; no scraped or private material",
       "label_trust":"specification_derived_not_independent_human_acceptance","files":files,
       "generator_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"independent_acceptance":False}
    (target/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest


def load(directory,split):
    root=Path(directory)
    manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    raw=(root/f"{split}.json").read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest["files"][f"{split}.json"]["sha256"]:
        raise ValueError("Dataset integrity failure")
    return json.loads(raw)
