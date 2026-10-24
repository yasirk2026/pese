from engine.neural.data.grouped_split import grouped_split, manifest, context_hash
from engine.neural.data.contracts import QAExample


def test_grouping_precedes_windows_and_excludes_benchmark():
    examples=[QAExample(id=str(i),question="What?",context="Context "+str(i//2),source_doc_id="source"+str(i//2)) for i in range(24)]
    split=grouped_split(examples,forbidden_contexts=["Context 0"])
    record=manifest(split)
    owners={}
    for part,rows in split.items():
        for ex in rows:
            assert ex.source_doc_id not in owners or owners[ex.source_doc_id]==part
            owners[ex.source_doc_id]=part
            assert context_hash(ex.context)!=context_hash("Context 0")
    assert record and len(owners)==11
    assert all(split.values())
