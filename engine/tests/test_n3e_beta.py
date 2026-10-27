from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time
from threading import Event
import pytest
from fastapi.testclient import TestClient
from engine.brain import initialize_brain
from engine.indexing.document import Document
from engine.intelligence.evidence import digest
from engine.intelligence.beta.consent import AGREEMENT_HASH
from engine.intelligence.beta.runtime import BetaRuntime,document_revision
from engine.intelligence.beta.judge import assess,advisory,Quality
from engine.intelligence.beta.queue import LearningQueue
from engine.intelligence.beta.lifecycle import decide
from engine.intelligence.beta.processes import ResidentInference,run_training
from engine.intelligence.beta.base_lock import BASE_FILES


@pytest.fixture
def owner(tmp_path):
    brain=tmp_path/"disposable";initialize_brain(brain)
    docs={f"d{i}":Document(id=f"d{i}",slug=f"doc-{i}",title=f"Clock notes {i}",
          content=f"mira changed clock project {i} because the old design failed.") for i in range(8)}
    beta=BetaRuntime(brain,channel=True,document_reader=docs.get)
    yield beta,docs
    beta.close()
    if beta.thread:beta.thread.join(timeout=5)


def presentation(doc,query="why did mira change the clock?",text=None):
    text=doc.content if text is None else text
    return {"receipt":{"version":1,"context_id":"c-"+doc.id,"effective_query":query,"target_type":"SERP_RESULT",
          "target_id":doc.id,"document_revision":document_revision(doc),"evidence_id":doc.slug+"#p0",
          "evidence_hash":digest(text),"model_versions":{"ranking":"synthetic-test"},"ranking_version":"maae","generation":"test"},
          "original_query":query,"evidence_text":text,"rank":1,"maae_score":10,"neural_adjustment":0,"preference_adjustment":0}


def test_agreement_scope_pause_exit_and_delete(owner):
    beta,docs=owner
    assert not beta.root.exists()
    assert beta.record(presentation(docs["d0"]))["status"]=="not_collected"
    with pytest.raises(ValueError):beta.accept(AGREEMENT_HASH,affirmative=False)
    beta.accept(AGREEMENT_HASH,affirmative=True,feedback_scope=["d0"],journal_scope=["d1"])
    assert beta.enabled() and beta.collecting()
    beta.record(presentation(docs["d0"]),feedback="LIKE")
    beta.record(presentation(docs["d2"]),feedback="DISLIKE",reason="not relevant")
    rows=beta.queue().list();assert len(rows)==2
    assert next(r for r in rows if r["document_id"]=="d2")["payload"]["evidence_text"] is None
    beta.configure({"paused":True});count=beta.queue().counts()["total"]
    beta.record(presentation(docs["d0"]),feedback="DISLIKE")
    assert beta.queue().counts()["total"]==count
    beta.configure({"paused":False});beta.exit()
    assert not beta.enabled() and not beta.collecting()
    assert beta.queue().counts()["total"]==count
    with pytest.raises(ValueError):beta.clear()
    beta.clear(True);assert not beta.root.exists()
    assert (beta.brain/"firestore_documents.json").exists()


def test_selective_judge_never_promotes_votes_or_own_confidence(owner):
    beta,docs=owner;event=presentation(docs["d0"])
    event.update(feedback="LIKE",reason=None,model_confidence=1.0)
    assert assess(event,verified=True)["quality"]==Quality.AMBIGUOUS.value
    assert assess(event,verified=False)["quality"]==Quality.INVALID.value
    assert assess(event,verified=True,current_revision="stale")["quality"]==Quality.INVALID.value
    assert assess(event,verified=True,repeated=True)["action"]=="deduplicate"
    assert assess(event,verified=True,contradictory=True)["quality"]==Quality.CONTRADICTORY.value
    event["reason"]="presentation";assert assess(event,verified=True)["quality"]==Quality.PREFERENCE.value
    event["reason"]="not relevant";assert assess(event,verified=True)["quality"]==Quality.CANDIDATE.value
    assert advisory(event)["admission_authority"]=="NONE"
    fake={"receipt_hash":digest(event),"grade":0,"objective":"retrieval_relevance","reviewer":"model","rationale":"high confidence"}
    assert assess(event,verified=True,review=fake)["quality"]==Quality.INVALID.value


def test_dedup_contradiction_stale_revision_and_review_roles(owner):
    beta,docs=owner;beta.accept(AGREEMENT_HASH,affirmative=True,feedback_scope=list(docs))
    event=presentation(docs["d0"])
    first=beta.record(event,feedback="DISLIKE",reason="not relevant")
    again=beta.record(event,feedback="DISLIKE",reason="not relevant")
    assert again["deduplicated"] and beta.queue().counts()["total"]==1
    row=beta.queue().list()[0]
    beta.review(row["id"],digest(row["payload"]),0,"wrong target", "evaluation",None,True)
    with pytest.raises(ValueError):beta.review(row["id"],digest(row["payload"]),0,"wrong target","train")
    beta.record(event,feedback="LIKE",reason="interesting")
    assert all(r["quality"]==Quality.CONTRADICTORY.value and r["review"] is None for r in beta.queue().list())
    docs["d1"].content="new revision"
    stale=presentation(docs["d1"]);stale["receipt"]["document_revision"]="old"
    assert beta.record(stale,feedback="DISLIKE").get("stored") is False


def test_journal_generation_is_unlabelled_and_requires_separate_scope(owner):
    beta,docs=owner;beta.accept(AGREEMENT_HASH,affirmative=True,journal_scope=["d1"])
    assert beta.journal(["d1","d2"])["generated"]==0
    beta.settings.update({"allow_journal_learning":True},neural_available=True)
    result=beta.journal(["d1","d2"])
    assert result["generated"]==1 and result["labels_created"]==0
    row=beta.queue().list()[0];assert row["review"] is None and row["payload"]["source_kind"]=="journal_synthetic"
    beta.settings.update({"excluded_document_ids":["d1"]},neural_available=True)
    assert beta.journal(["d1"])["generated"]==0


def test_actual_resident_inference_integrity_and_disabled_mode(owner):
    beta,docs=owner;beta.accept(AGREEMENT_HASH,affirmative=True,feedback_scope=["d0"])
    model=beta.models.current();worker=ResidentInference()
    payload={"directory":str(model.directory),"checkpoint_hash":model.checkpoint_hash,"tokenizer_hash":model.tokenizer_hash,
             "query":"why did iris revise neural search?","evidence":["iris changed neural search because keyword matches were misleading.","iris watered the garden."]}
    try:
        scores,cold=worker([],payload);again,warm=worker([],payload)
        assert len(scores)==2 and scores==pytest.approx(again)
        assert cold["cold"] and not warm["cold"] and warm["latency_ms"]<150
        assert warm["peak_bytes"]<=384*1024*1024
        with pytest.raises(Exception):worker([],{**payload,"checkpoint_hash":"0"*64})
    finally:worker.close()
    beta.configure({"neural":False})
    assert beta.ranker.adjust([],"q",enabled=True)["status"]=="DISABLED"


def test_closed_beta_cannot_change_production_trust(owner):
    beta,_=owner
    from engine.intelligence.model_release import verify_bundle,TRUSTED_RELEASE_KEYS
    assert not TRUSTED_RELEASE_KEYS
    with pytest.raises(ValueError):verify_bundle(beta.base_path)
    stable=BetaRuntime(beta.brain,channel=False)
    with pytest.raises(ValueError):stable.accept(AGREEMENT_HASH,affirmative=True)
    assert not stable.enabled()


def test_local_promotion_policy_preserves_all_gates():
    passing={"reviewed_queries":12,"heldout_document_families":3,"independent_of_training":True,
       "delta_current":.02,"delta_maae":0,"delta_base":0,"category_regression":0,
       "new_wrong_answers":0,"gate_violations":0,"inference_health":True}
    assert decide(passing)["decision"]=="promote"
    for bad in ({"reviewed_queries":0},{"independent_of_training":False},{"delta_current":0},
                {"new_wrong_answers":1},{"gate_violations":1},{"inference_health":False}):
        assert decide({**passing,**bad})["decision"]!="promote"


def test_queue_limits_and_legacy_schema_rejection(owner,tmp_path):
    beta,docs=owner;queue=LearningQueue(tmp_path/"bounded.db",max_events=3)
    for i in range(8):
        event=presentation(docs[f"d{i}"]);event.update(feedback="LIKE")
        queue.append(event,verified=True)
    assert queue.counts()["total"]==3
    import sqlite3
    with sqlite3.connect(tmp_path/"wrong.db") as db:db.execute("PRAGMA user_version=99")
    with pytest.raises(ValueError):LearningQueue(tmp_path/"wrong.db")


def test_beta_api_agreement_and_control_boundary(owner,monkeypatch):
    beta,docs=owner
    from engine.api import main
    from engine.intelligence.beta import api
    monkeypatch.setattr(api,"get_runtime",lambda:beta)
    monkeypatch.setattr(main.store,"get_document",docs.get)
    client=TestClient(main.app)
    status=client.get("/api/intelligence/beta/status").json();assert not status["participation"]["accepted"]
    assert client.post("/api/intelligence/beta/train").status_code==409
    result=client.post("/api/intelligence/beta/agreement",json={"accepted":True,"agreement_hash":AGREEMENT_HASH,"feedback_scope":["d0"]})
    assert result.status_code==200
    assert client.put("/api/intelligence/beta/settings",json={"neural":False}).status_code==200
    assert client.post("/api/intelligence/beta/train").status_code==409
    assert client.post("/api/intelligence/beta/clear",json={"confirmed":False}).status_code==409


def test_actual_private_candidate_training_journal_review_and_gated_rollback(owner):
    beta,docs=owner
    beta.accept(AGREEMENT_HASH,affirmative=True,journal_scope=list(docs))
    beta.settings.update({"allow_journal_learning":True},neural_available=True)
    # Original synthetic notes only. Generated pairs are reviewed explicitly in
    # this fixture; generation alone never creates a label.
    beta.journal(list(docs)[:6])
    for row in beta.queue().list():
        beta.review(row["id"],digest(row["payload"]),2,"Synthetic note title matches the passage","train")
    for i in range(6):
        for number in range(3):
            positive=number==0
            query=("why did mira change clock " if positive else "find bicycle repair ")+f"{i} variant {number}"
            beta.record(presentation(docs[f"d{i}"],query),feedback="LIKE" if positive else "DISLIKE",reason="not relevant" if not positive else None)
            row=next(r for r in beta.queue().list() if r["payload"]["receipt"]["effective_query"]==query)
            beta.review(row["id"],digest(row["payload"]),2 if positive else 0,"Synthetic subject relevance confirmed","train")
    before=hashlib.sha256((beta.brain/"firestore_documents.json").read_bytes()).hexdigest()
    base=beta.models.current()
    job=beta.train_now();deadline=time.monotonic()+60
    while beta.thread.is_alive() and time.monotonic()<deadline:time.sleep(.05)
    assert not beta.thread.is_alive()
    receipt=json.loads((beta.root/"last-job.json").read_text())
    assert receipt["status"]=="rejected_or_review_required",receipt
    candidate=beta.root/"jobs"/job["job_id"]/"candidate"
    learned=json.loads((candidate/"training.json").read_text())
    assert learned["checkpoint_sha256"]!=base.checkpoint_hash
    assert receipt["evaluation"]["decision"]!="promote"  # no complete heldout pools
    assert beta.models.current().checkpoint_hash==base.checkpoint_hash
    # Exercise actual checkpoint replacement/rollback with a clearly labelled
    # policy fixture. This is not evidence that the candidate's quality passed.
    from engine.intelligence.beta.neural import load_model,predict
    def health(model):
        network,tokenizer=load_model(model.directory)
        return len(predict(network,tokenizer,[("find clock notes","mira changed the clock")]))==1
    with pytest.raises(ValueError):beta.models.promote(candidate,{"decision":"reject"},health)
    fixture_decision={"decision":"promote","evidence":"synthetic_gate_unit_fixture_only","candidate_checkpoint":learned["checkpoint_sha256"]}
    from engine.intelligence.beta.artifacts import write_manifest
    write_manifest(candidate,identity="test-local-candidate",origin="local_adaptation",brain_binding=beta.models.binding,
                   evaluation=fixture_decision,training=learned)
    promoted=beta.models.promote(candidate,fixture_decision,health)
    assert promoted.checkpoint_hash==learned["checkpoint_sha256"]
    assert beta.models.rollback().checkpoint_hash==base.checkpoint_hash
    assert hashlib.sha256((beta.brain/"firestore_documents.json").read_bytes()).hexdigest()==before
