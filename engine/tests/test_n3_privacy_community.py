from copy import deepcopy
import json
import pytest
from fastapi.testclient import TestClient
from engine.intelligence.settings import SettingsStore
from engine.intelligence.contributions import ExportReview, ContributionEndpoint, parse_package, MAX_BYTES
from engine.search_sync.feedback_store import SearchSyncFeedbackStore
from engine.search_sync.preference_signal import SearchSyncPreferenceSignal
from engine.tests.test_n3_evidence import vote
from research.mock_intake import create_mock_app, expire_quarantine


def test_local_permissions_persistence_disable_reset_and_exclusions(tmp_path):
    settings = SettingsStore(tmp_path)
    original = settings.read()
    assert original.learn_from_feedback  # preserve equivalent N3-A behavior
    assert not original.allow_journal_learning and not original.community_contributions
    assert not original.collect_research_feedback and not original.neural_search
    store = SearchSyncFeedbackStore(tmp_path/"feedback.db")
    store.record_feedback(vote(feedback="LIKE"))
    signal = SearchSyncPreferenceSignal(store)
    assert signal.get_preference_adjustment("clock","d").adjustment == 2
    settings.update({"learn_from_feedback":False})
    assert signal.get_preference_adjustment("clock","d").adjustment == 0
    assert len(store.get_active_preferences_for_query("clock")) == 1
    # Restart permission read does not re-enable personalization.
    assert not SettingsStore(tmp_path).read().learn_from_feedback
    settings.update({"learn_from_feedback":True,"collect_research_feedback":True})
    assert not settings.read().community_contributions
    assert not settings.read().permits_document("journal",journal=True)
    settings.update({"allow_journal_learning":True,"excluded_document_ids":["secret"]})
    assert settings.read().permits_document("journal",journal=True)
    assert not settings.read().permits_document("secret",journal=True)
    store.clear_all()
    assert signal.get_preference_adjustment("clock","d").adjustment == 0
    assert settings.read().allow_journal_learning
    with pytest.raises(ValueError):
        settings.update({"neural_search":True})
    settings.path.write_text("corrupt")
    assert not settings.read().learn_from_feedback and not settings.read().community_contributions


def test_export_preview_review_cancel_revocation_and_no_private_text(tmp_path):
    settings = SettingsStore(tmp_path)
    store = SearchSyncFeedbackStore(tmp_path/"feedback.db")
    review = ExportReview(settings,store)
    with pytest.raises(ValueError): review.preview()
    settings.update({"community_contributions":True})
    for i in range(8):
        event = vote(); event.target_id=f"d{i}"; event.query="PRIVATE JOURNAL QUERY"
        store.record_feedback(event)
    preview = review.preview()
    assert "PRIVATE" not in json.dumps(preview) and "d0" not in json.dumps(preview)
    assert preview["package"]["diagnostics"][0]["count_bucket"] == "5-9"
    with pytest.raises(ValueError): review.export(preview["preview_id"],preview["sha256"],False)
    with pytest.raises(ValueError): review.export(preview["preview_id"],"0"*64,True)
    review.cancel(preview["preview_id"])
    with pytest.raises(ValueError): review.export(preview["preview_id"],preview["sha256"],True)
    preview=review.preview()
    settings.update({"community_contributions":False})
    with pytest.raises(ValueError): review.export(preview["preview_id"],preview["sha256"],True)
    settings.update({"community_contributions":True})
    stale=review.preview()
    settings.update({"community_contributions":False})
    settings.update({"community_contributions":True})
    with pytest.raises(ValueError): review.export(stale["preview_id"],stale["sha256"],True)
    preview=review.preview()
    body=review.export(preview["preview_id"],preview["sha256"],True)
    assert parse_package(json.dumps(body).encode()).consent.reviewed
    with pytest.raises(RuntimeError): ContributionEndpoint().submit(body)


def test_permissions_and_research_never_enter_drive_payload(tmp_path):
    import zipfile
    from engine.brain import initialize_brain
    from engine.sync.snapshot import create_snapshot,canonical_state_digest
    from engine.sync.restore import restore_snapshot
    root=tmp_path/"source"
    initialize_brain(root)
    before=canonical_state_digest(root)
    settings=SettingsStore(root)
    settings.update({"allow_journal_learning":True,"community_contributions":True})
    (settings.root/"research-fixture.json").write_text('{"private":"synthetic research marker"}')
    assert canonical_state_digest(root)==before
    bundle=create_snapshot(root,tmp_path/"backups")
    with zipfile.ZipFile(bundle.zip_path) as archive:
        assert not any("intelligence" in name or "research" in name for name in archive.namelist())
    recovered=tmp_path/"inactive"
    restore_snapshot(bundle.zip_path,recovered,expected_brain_id=bundle.brain_id,
        expected_snapshot_id=bundle.snapshot_id,expected_zip_sha256=bundle.zip_sha256)
    assert not SettingsStore(recovered).read().allow_journal_learning
    assert not SettingsStore(recovered).read().community_contributions
    assert canonical_state_digest(root)==before


def package():
    return {"format":"pese-contribution","version":1,"app_version":"0.1.0-alpha.6",
        "model_version":"PESE-Rel-0:frozen:shadow","diagnostics":[{"category":"incomplete_provenance","count_bucket":"5-9"}],
        "consent":{"version":1,"reviewed":True,"purpose":"reviewable_local_export_for_future_model_improvement",
                   "includes_text":False,"upload_authorized":False}}


@pytest.mark.parametrize("field",["query","journal","evidence","embeddings","model_deltas","device_id","labels","provenance"])
def test_private_text_and_untrusted_labels_not_in_contract(field):
    body=package(); body[field]="private"
    with pytest.raises(ValueError): parse_package(json.dumps(body).encode())


def test_mock_intake_quarantine_limits_versions_consent_and_duplicates(tmp_path):
    app=create_mock_app(tmp_path,token="test-only",max_per_minute=100)
    client=TestClient(app)
    headers={"Authorization":"Bearer test-only","X-PESE-Test-Review":"reviewed-loopback-only-v1"}
    assert client.post("/v1/contributions",json=package()).status_code == 401
    assert client.post("/v1/contributions",json=package(),headers={"Authorization":"Bearer test-only"}).status_code == 403
    response=client.post("/v1/contributions",json=package(),headers=headers)
    assert response.json()=={"status":"quarantined","training_eligible":False}
    assert client.post("/v1/contributions",json=package(),headers=headers).json()["status"]=="duplicate"
    for change in ({"version":99},{"consent":{}},{"query":"private"},{"model_version":"untrusted"}):
        body={**package(),**change}
        assert client.post("/v1/contributions",json=body,headers=headers).status_code==400
    assert client.post("/v1/contributions",content=b"x"*(MAX_BYTES+1),headers={**headers,"Content-Type":"application/json"}).status_code==413
    assert expire_quarantine(tmp_path,now=10**12)==1
    limited=TestClient(create_mock_app(tmp_path/"limited",token="test-only",max_per_minute=1))
    assert limited.post("/v1/contributions",json=package(),headers=headers).status_code==200
    assert limited.post("/v1/contributions",json=package(),headers=headers).status_code==429


def test_api_enforces_preview_review_and_permission_boundaries(tmp_path,monkeypatch):
    from engine.api import main
    from engine.intelligence import settings as module
    local=SettingsStore(tmp_path)
    store=SearchSyncFeedbackStore(tmp_path/"feedback.db")
    monkeypatch.setattr(module,"intelligence_settings",local)
    monkeypatch.setattr(main,"contribution_reviews",ExportReview(local,store))
    monkeypatch.setattr(main,"feedback_store",store)
    client=TestClient(main.app)
    assert client.get("/api/intelligence/settings").json()["neural_available"] is False
    assert client.put("/api/intelligence/settings",json={"neural_search":True}).status_code==400
    assert client.post("/api/intelligence/contributions/preview").status_code==409
    assert client.put("/api/intelligence/settings",json={"community_contributions":True}).status_code==200
    p=client.post("/api/intelligence/contributions/preview").json()
    assert client.post("/api/intelligence/contributions/export",json={"preview_id":p["preview_id"],"sha256":p["sha256"],"reviewed":False}).status_code==409
    assert client.put("/api/intelligence/settings",json={"community_contributions":False,"learn_from_feedback":False}).status_code==200
    assert client.post("/api/intelligence/contributions/export",json={"preview_id":p["preview_id"],"sha256":p["sha256"],"reviewed":True}).status_code==409
    assert client.post("/api/search/feedback",json={"query":"clock","target_type":"SERP_RESULT","target_id":"d","feedback":"LIKE"}).status_code==409
