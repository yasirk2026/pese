"""Synthetic multi-size Brains, account boundaries, retention and native policy."""
from copy import deepcopy
from contextlib import closing
import hashlib
import json
import os
import time
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from engine.brain import initialize_brain
from engine.indexing.document import Document
from engine.intelligence.beta.runtime import BetaRuntime
from engine.intelligence.beta.consent import AGREEMENT_HASH
from engine.intelligence.evidence import digest


@pytest.mark.parametrize("size",[2,200,400])
def test_current_scope_is_snapshot_not_two_document_limit(tmp_path,size):
    brain=tmp_path/"synthetic";initialize_brain(brain)
    docs={f"study-{i}":Document(id=f"study-{i}",slug=f"study-{i}",title=f"Public study note {i}",content="Synthetic technical study material.") for i in range(size)}
    owner=BetaRuntime(brain,channel=True,document_reader=docs.get)
    try:
        preview=owner.scope_snapshot(docs)
        assert preview["current_document_count"]==size and len(preview["document_ids"])==size
        assert not owner.collecting() and not owner.root.exists()
        owner.accept(AGREEMENT_HASH,affirmative=True,feedback_scope=preview["document_ids"],scope_mode="all_current_snapshot")
        assert all(owner.allowed(v) for v in docs)
        assert owner.state()["retention_days"]==7 and not owner.settings.read().allow_journal_learning
        docs["future"]=Document(id="future",slug="future",title="Future note",content="New unapproved study text.")
        assert not owner.allowed("future")
        owner.settings.update({"excluded_document_ids":["study-0"]},neural_available=True)
        owner.forget(["study-0"])
        assert not owner.allowed("study-0")
        owner.settings.update({"excluded_document_ids":[]},neural_available=True)
        assert not owner.allowed("study-0")  # even an ID reused after delete needs fresh approval
        assert len(owner.scope_snapshot(docs)["document_ids"])==size+1
    finally:owner.close()


def test_consent_and_research_storage_do_not_cross_accounts_or_brains(tmp_path):
    brain=tmp_path/"shared-synthetic";initialize_brain(brain)
    a=BetaRuntime(brain,channel=True,account="a"*64)
    b=BetaRuntime(brain,channel=True,account="b"*64)
    other=tmp_path/"other-synthetic";initialize_brain(other)
    c=BetaRuntime(other,channel=True,account="a"*64)
    try:
        a.accept(AGREEMENT_HASH,affirmative=True,feedback_scope=["d"])
        assert a.accepted() and not b.accepted() and not c.accepted()
        assert a.root!=b.root and a.settings.path!=b.settings.path
        assert a.models.binding!=b.models.binding and a.models.binding!=c.models.binding
        assert not b.root.exists() and not b.settings.read().collect_research_feedback
        # Copying a consent record into another account or Brain cannot grant it.
        for target in (b,c):
            target.root.mkdir(parents=True)
            (target.root/"participation.json").write_bytes((a.root/"participation.json").read_bytes())
            assert not target.accepted() and not target.status()["participation"]["accepted"]
    finally:
        for owner in (a,b,c):owner.close()


def test_current_snapshot_api_requires_fresh_explicit_approval(tmp_path,monkeypatch):
    from engine.intelligence.beta import api
    from engine.api import main
    brain=tmp_path/"synthetic";initialize_brain(brain)
    owner=BetaRuntime(brain,channel=True)
    monkeypatch.setattr(api,"get_runtime",lambda:owner)
    ids=[f"study-{i}" for i in range(200)]
    monkeypatch.setattr(api,"current_document_ids",lambda:ids)
    client=TestClient(main.app)
    try:
        preview=client.get("/api/intelligence/beta/scope").json()
        ids.append("future")
        body={"accepted":True,"agreement_hash":AGREEMENT_HASH,"approve_all_current":True,"scope_snapshot_hash":preview["snapshot_hash"]}
        assert client.post("/api/intelligence/beta/agreement",json=body).status_code==409
        assert not owner.accepted()
        ids.pop()
        assert client.post("/api/intelligence/beta/agreement",json=body).status_code==200
        assert len(owner.state()["feedback_scope"])==200
        client.post("/api/intelligence/beta/agreement",json={"accepted":False,"agreement_hash":AGREEMENT_HASH})
        assert not owner.collecting() and not owner.enabled()
    finally:owner.close()


def test_missing_model_accepts_policy_but_uses_maae(tmp_path):
    brain=tmp_path/"synthetic";initialize_brain(brain)
    owner=BetaRuntime(brain,channel=True,base_path=tmp_path/"missing-artifact")
    try:
        result=owner.accept(AGREEMENT_HASH,affirmative=True,feedback_scope=["d"])
        assert owner.accepted() and not owner.enabled()
        assert result["ranking_mode"]=="deterministic_maae"
        with pytest.raises((ValueError,OSError)):owner.configure({"neural":True})
    finally:owner.close()


def test_legacy_permissions_keep_preferences_but_never_transfer_training_consent(tmp_path):
    from engine.intelligence.settings import SettingsStore
    brain=tmp_path/"synthetic";initialize_brain(brain)
    SettingsStore(brain).update({"neural_search":True,"collect_research_feedback":True,"allow_journal_learning":True,
                                 "learn_from_feedback":False,"excluded_document_ids":["excluded"]},neural_available=True)
    owner=BetaRuntime(brain,channel=True)
    try:
        permissions=owner.settings.read()
        assert not permissions.learn_from_feedback and permissions.excluded_document_ids==["excluded"]
        assert not permissions.neural_search and not permissions.collect_research_feedback and not permissions.allow_journal_learning
        assert not owner.accepted()
    finally:owner.close()


def test_presentation_registry_keeps_research_passages_inside_approved_scope():
    from engine.intelligence.contexts import SearchContexts
    contexts=SearchContexts()
    def row(identity,text):
        return SimpleNamespace(doc_id=identity,evidence_provenance={"target_id":identity},rank=1,slug=identity,
            base_score=10,learning_evidence_text=text,neural_adjustment=0,search_sync_adjustment=0,final_score=10,
            trace=SimpleNamespace(neural_model_version=None),is_featured=True,featured_answer=text)
    contexts.remember("c","synthetic question",[row("approved","public synthetic"),row("excluded","EXCLUDED_SENTINEL")],
                      learning=True,learning_allowed=lambda identity:identity=="approved")
    excluded=SimpleNamespace(search_context_id="c",target_type="SERP_RESULT",target_id="excluded")
    assert contexts.learning_target(excluded) is None
    assert set(contexts._learning["c"])=={("SERP_RESULT","approved"),("FEATURED_ANSWER","approved")}


def test_unapproved_or_excluded_passages_never_reach_experimental_model(tmp_path):
    brain=tmp_path/"synthetic";initialize_brain(brain)
    owner=BetaRuntime(brain,channel=True)
    sent=[]
    def prediction(_,payload):
        sent.extend(payload["evidence"])
        return [.5]*len(payload["evidence"]),{"latency_ms":1}
    owner.ranker._predictor=prediction
    owner.accept(AGREEMENT_HASH,affirmative=True,feedback_scope=["approved","excluded"])
    owner.settings.update({"excluded_document_ids":["excluded"]},neural_available=True)
    def row(identity,text):
        return {"doc_id":identity,"passage_text":text,"base_score":10,"final_score":10,"search_sync_adjustment":0,
                "trace":SimpleNamespace(evidence_gate_passed=True)}
    candidates=[row("approved","Synthetic approved public study text"),row("excluded","EXCLUDED_SENTINEL"),row("future","UNAPPROVED_SENTINEL")]
    try:
        result=owner.ranker.adjust(candidates,"find study text",enabled=True)
        assert result["authority"]=="BOUNDED_RANKING_ONLY"
        assert sent==["Synthetic approved public study text"]
        assert candidates[1]["final_score"]==10 and candidates[2]["final_score"]==10
        owner.configure({"paused":True})
        assert not owner.allowed("approved") and owner.in_scope("approved")  # pause collection, keep consented ranking
    finally:owner.close()


def test_retention_removes_raw_review_labels_jobs_and_expired_models(tmp_path):
    from engine.tests.test_n3e_beta import presentation
    brain=tmp_path/"synthetic";initialize_brain(brain)
    doc=Document(id="d",slug="d",title="Public study note",content="mira changed the clock because the design failed.")
    owner=BetaRuntime(brain,channel=True,document_reader=lambda _:doc)
    try:
        owner.accept(AGREEMENT_HASH,affirmative=True,feedback_scope=["d"])
        owner.record(presentation(doc),feedback="DISLIKE",reason="not relevant")
        row=owner.queue().list()[0]
        owner.review(row["id"],digest(row["payload"]),0,"Synthetic unrelated question","train")
        old=time.time()-8*86400
        with closing(owner.queue().connect()) as db:db.execute("UPDATE events SET created=?",(old,));db.commit()
        for name in ("jobs/expired","models/"+"c"*64):
            path=owner.root/name;path.mkdir(parents=True);(path/"synthetic.json").write_text('{}');os.utime(path,(old,old))
        (owner.root/"active.json").write_text(json.dumps({"version":1,"current":"c"*64,"previous":"base"}))
        owner._last_expire=0;owner.expire()
        assert owner.queue().counts()["total"]==0
        assert not (owner.root/"jobs/expired").exists() and not (owner.root/"models"/("c"*64)).exists()
        assert owner.models.current().checkpoint_hash==owner.models.base().checkpoint_hash
        owner.clear(True)
        assert not owner.root.exists() and (brain/"firestore_documents.json").exists()
    finally:owner.close()


def test_native_training_policy_decline_preserves_pointer_and_has_no_enrollment(tmp_path,monkeypatch):
    from engine.desktop.launcher import brain_command
    from engine.indexing.store import DocumentStore
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path/"profile"))
    brain=tmp_path/"synthetic";initialize_brain(brain)
    DocumentStore(brain/"firestore_documents.json").save_document(Document(id="study",slug="study",title="Public study",content="Original synthetic public material."))
    pointer=tmp_path/"profile/ManiacSoftwares/PESE/desktop-settings.json"
    pointer.parent.mkdir(parents=True);pointer.write_text('{"brainPath":"synthetic-sentinel"}')
    before=pointer.read_bytes();content=(brain/"firestore_documents.json").read_bytes()
    command={"action":"beta_prepare","brainPath":str(brain),"settingsPath":str(pointer),"intelligenceChannel":"aggressive_learning_beta"}
    prepared=brain_command(command)
    assert not prepared["accepted"] and prepared["scope"]["current_document_count"]==1
    declined=brain_command({**command,"action":"beta_decline"})
    assert declined["shutdown_required"] and not declined["accepted"]
    assert pointer.read_bytes()==before and (brain/"firestore_documents.json").read_bytes()==content
    assert not (brain/".pese-intelligence-v1").exists()


def test_native_training_policy_backup_and_full_scope_without_training(tmp_path,monkeypatch):
    from engine.desktop.launcher import brain_command
    from engine.indexing.store import DocumentStore
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path/"profile"))
    brain=tmp_path/"synthetic";initialize_brain(brain)
    store=DocumentStore(brain/"firestore_documents.json")
    for i in range(2):store.save_document(Document(id=f"study-{i}",slug=f"study-{i}",title=f"Public note {i}",content="Original synthetic classroom observations."))
    pointer=tmp_path/"profile/ManiacSoftwares/PESE/desktop-settings.json"
    pointer.parent.mkdir(parents=True);pointer.write_text('{"brainPath":"synthetic-sentinel"}')
    before=pointer.read_bytes();content=(brain/"firestore_documents.json").read_bytes()
    command={"action":"beta_prepare","brainPath":str(brain),"settingsPath":str(pointer),"intelligenceChannel":"aggressive_learning_beta"}
    prepared=brain_command(command)
    result=brain_command({**command,"action":"beta_accept","accepted":True,"agreement_hash":prepared["agreement_hash"],
                          "scope_snapshot_hash":prepared["scope"]["snapshot_hash"],"excluded_document_ids":["study-1"]})
    assert result["accepted"] and result["receipt"]["scope_count"]==1
    assert result["receipt"]["inactive_restore_verified"] and not result["receipt"]["training_started"]
    owner=BetaRuntime(brain,channel=True)
    try:
        assert owner.accepted() and owner.allowed("study-0") and not owner.allowed("study-1")
        assert owner.queue().counts()["total"]==0 and not owner.settings.read().allow_journal_learning
        assert pointer.read_bytes()==before and (brain/"firestore_documents.json").read_bytes()==content
    finally:owner.close()
