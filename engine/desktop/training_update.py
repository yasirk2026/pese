"""Native first-start agreement. No serving/indexing or pointer changes here."""
import json
from pathlib import Path
from ..intelligence.beta.runtime import BetaRuntime
from ..intelligence.beta.consent import AGREEMENT,AGREEMENT_HASH
from ..intelligence.beta.processes import ResidentInference
from ..intelligence.evidence import digest


def onboarding(command, info):
    if command.get("intelligenceChannel")!="aggressive_learning_beta":
        raise ValueError("This build does not provide the training update")
    brain=Path(info.path)
    owner=BetaRuntime(brain,channel=True)
    owner.expire()
    action=command["action"]
    # This is the normal native consent view's metadata enumeration, never an
    # evaluation/training reader. Only IDs, titles and status reach the UI.
    rows=json.loads((brain/"firestore_documents.json").read_text(encoding="utf-8"))
    documents=[{"id":d["id"],"title":d.get("title",""),"status":d.get("status","published")} for d in rows.values()]
    ids=[d["id"] for d in documents]
    snapshot=owner.scope_snapshot(ids)
    if action=="beta_prepare":
        return {"ok":True,"brain":info.model_dump(mode="json"),"accepted":owner.accepted(),
                "agreement":AGREEMENT,"agreement_hash":AGREEMENT_HASH,"scope":snapshot,"documents":documents,
                "excluded_document_ids":owner.settings.read().excluded_document_ids}
    if action=="beta_decline":
        owner.exit()
        return {"ok":True,"accepted":False,"shutdown_required":True}
    if action!="beta_accept" or command.get("accepted") is not True or command.get("agreement_hash")!=AGREEMENT_HASH:
        raise ValueError("Affirmative acceptance of the current training disclosure is required")
    if command.get("scope_snapshot_hash")!=snapshot["snapshot_hash"]:
        raise ValueError("The current document collection changed; review the agreement again")
    excluded=command.get("excluded_document_ids",[])
    if not isinstance(excluded,list) or len(excluded)>10000 or any(not isinstance(v,str) or len(v)>200 for v in excluded):
        raise ValueError("Explicit document exclusions required")
    # Always preserve existing exclusions; the separate Privacy control can
    # explicitly remove them later. All-current acceptance cannot erase them.
    excluded=sorted(set(excluded)|set(owner.settings.read().excluded_document_ids))
    approved=sorted(set(ids)-set(excluded))
    from ..sync.snapshot import create_snapshot
    from ..brain.resolver import get_desktop_settings_path
    profile=Path(command.get("settingsPath") or get_desktop_settings_path()).parent
    bundle=create_snapshot(brain, profile/"BETA Safety Backups"/info.brain_id)
    # Verify recovery into a separate inactive directory before experimental use.
    from ..sync.restore import restore_snapshot
    restored=profile/"BETA Safety Backups"/info.brain_id/("inactive-"+bundle.snapshot_id)
    restore_snapshot(bundle.zip_path,restored,expected_brain_id=info.brain_id,
                     expected_snapshot_id=bundle.snapshot_id,expected_zip_sha256=bundle.zip_sha256)
    import hashlib
    if hashlib.sha256((brain/"firestore_documents.json").read_bytes()).digest()!=hashlib.sha256((restored/"firestore_documents.json").read_bytes()).digest():
        raise ValueError("Backup document verification failed; BETA remains inactive")
    owner.settings.update({"neural_search":False,"collect_research_feedback":False,"excluded_document_ids":excluded,
                           "allow_journal_learning":False,"community_contributions":False},neural_available=False)
    owner.accept(AGREEMENT_HASH,affirmative=True,feedback_scope=approved,retention_days=7,scope_mode="all_current_snapshot")
    health={"verified":False,"status":"MAAE_FALLBACK"}
    if owner.enabled():
        probe=ResidentInference()
        try:
            model=owner.models.current()
            _,timing=probe([],{"directory":str(model.directory),"checkpoint_hash":model.checkpoint_hash,
                              "tokenizer_hash":model.tokenizer_hash,"query":"find study notes",
                              "evidence":["These public synthetic study notes describe a library."]})
            health={"verified":True,**timing}
        except Exception as failure:
            health["failure_type"]=type(failure).__name__
            owner.configure({"neural":False})
        finally:probe.close()
    from ..brain.atomic import atomic_write_json
    receipt={"version":1,"agreement_hash":AGREEMENT_HASH,"brain_id":info.brain_id,
             "account_binding":owner.account,"scope_count":len(approved),"scope_ids_hash":digest(approved),
             "future_documents_authorized":False,"journal_training":False,"retention_days":7,
             "backup_sha256":bundle.zip_sha256,"backup_snapshot":bundle.snapshot_id,"inactive_restore_verified":True,
             "runtime_health":health,"external_sharing":False,"training_started":False}
    atomic_write_json(owner.root/"onboarding-receipt.json",receipt)
    return {"ok":True,"accepted":True,"receipt":receipt}
