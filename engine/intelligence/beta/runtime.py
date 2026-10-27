"""Consent-gated, per-Brain closed-BETA lifecycle. Stable remains deterministic."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from threading import Event,RLock,Thread
import time
from uuid import uuid4
from ..evidence import digest
from ..reranking import NeuralReranker
from ..settings import SettingsStore
from ...brain.atomic import atomic_write_json
from .artifacts import LocalModels,write_manifest
from .base_lock import BASE_FILES
from .consent import AGREEMENT,AGREEMENT_HASH
from .judge import advisory,Quality
from .processes import ResidentInference,run_training
from .queue import LearningQueue

_LOCK=RLock();_RUNTIMES={}


def beta_channel():return os.getenv("PESE_INTELLIGENCE_CHANNEL","stable")=="aggressive_learning_beta"


def document_revision(doc):
    data=doc.model_dump();data.pop("indexed_at",None);return digest(data)


class BetaReranker(NeuralReranker):
    def __init__(self,owner):
        self.owner=owner;self.worker=ResidentInference()
        super().__init__(predictor=self.worker)

    @property
    def available(self):return self.owner.enabled()

    @property
    def cache_identity(self):
        self.owner.expire()
        pointer=self.owner.root/"active.json"
        return digest((self.owner.state(),self.owner.settings.read().neural_search,
                       hashlib.sha256(pointer.read_bytes()).hexdigest() if pointer.exists() else "base"))

    def adjust(self,candidates,query,*,enabled=False):
        if not self.owner.enabled():return {"status":"DISABLED","authority":"NONE","channel":"aggressive_learning_beta"}
        self.owner.expire()
        try:self.approved=self.owner.models.current()
        except Exception:
            self.owner.last_inference={"status":"ARTIFACT_FAILURE_FALLBACK","authority":"NONE"};return self.owner.last_inference
        result=super().adjust(candidates,query,enabled=enabled)
        self.owner.last_inference=result
        if result["authority"]=="NONE" and result["status"]!="DISABLED":self.owner.fallbacks+=1
        return result


class BetaRuntime:
    def __init__(self,brain_root,*,channel=None,base_path=None,base_pin=None,document_reader=None):
        self.brain=Path(brain_root);self.root=self.brain/".pese-intelligence-v1/beta"
        self.channel=beta_channel() if channel is None else channel
        self.settings=SettingsStore(self.brain);self.lock=RLock();self.cancel=Event();self.thread=None
        self.document_reader=document_reader
        self.base_path=Path(base_path) if base_path else Path(__file__).resolve().parents[2]/"neural/assets/basic_english_beta_v1"
        self.models=LocalModels(self.root,digest(str(self.brain.resolve())),self.base_path,BASE_FILES if base_pin is None else base_pin)
        self.ranker=BetaReranker(self);self.last_inference={"status":"NOT_RUN","authority":"NONE"};self.fallbacks=0;self.rejections=0
        self._last_expire=0.0

    def state(self):
        try:return json.loads((self.root/"participation.json").read_text(encoding="utf-8"))
        except (OSError,ValueError):return {"version":1,"accepted":False,"paused":True,"neural":False,"feedback_scope":[],"journal_scope":[],"retention_days":30}

    def accepted(self):
        state=self.state()
        return self.channel and state.get("accepted") is True and state.get("agreement_hash")==AGREEMENT_HASH

    def enabled(self):return self.accepted() and self.state().get("neural") is True and self.settings.read().neural_search

    def collecting(self):
        settings=self.settings.read()
        return self.accepted() and not self.state().get("paused",True) and settings.collect_research_feedback and settings.learn_from_feedback

    def owned_root(self):
        if not self.root.resolve().is_relative_to(self.brain.resolve()) or self.root.is_symlink():raise ValueError("Experimental storage must remain inside this Brain sidecar")
        return self.root.resolve()

    def queue(self):
        self.owned_root()
        return LearningQueue(self.root/"learning.db",retention_days=self.state().get("retention_days",30))

    def accept(self,agreement_hash,*,affirmative,feedback_scope=(),journal_scope=()):
        if not self.channel:raise ValueError("This application is not the closed BETA channel")
        if affirmative is not True or agreement_hash!=AGREEMENT_HASH:raise ValueError("Affirmative acceptance of the current disclosure is required")
        self.models.base()  # integrity/known objective contract before activation
        self.owned_root()
        self.root.mkdir(parents=True,exist_ok=True)
        with self.lock:
            state={"version":1,"accepted":True,"agreement_hash":AGREEMENT_HASH,"accepted_at":datetime.now(timezone.utc).isoformat(),
                   "paused":False,"neural":True,"feedback_scope":sorted(set(feedback_scope)),"journal_scope":sorted(set(journal_scope)),"retention_days":30}
            atomic_write_json(self.root/"participation.json",state)
            self.settings.update({"neural_search":True,"collect_research_feedback":True},neural_available=True)
            self.queue()
        return self.status()

    def configure(self,changes):
        if not self.accepted():raise ValueError("BETA participation is not active")
        if set(changes)-{"paused","neural","feedback_scope","journal_scope","retention_days"}:raise ValueError("Unsupported BETA setting")
        if "retention_days" in changes and (type(changes["retention_days"]) is not int or not 1<=changes["retention_days"]<=90):raise ValueError("Retention must be 1..90 days")
        if any(k in changes and type(changes[k]) is not bool for k in ("paused","neural")):raise ValueError("Boolean required")
        for field in ("feedback_scope","journal_scope"):
            if field in changes and (not isinstance(changes[field],list) or len(changes[field])>1000 or any(not isinstance(v,str) or len(v)>200 for v in changes[field])):raise ValueError("Explicit document IDs required")
        with self.lock:
            old=self.state();new={**old,**changes}
            removed=(set(old.get("feedback_scope",[]))|set(old.get("journal_scope",[])))-(set(new.get("feedback_scope",[]))|set(new.get("journal_scope",[])))
            atomic_write_json(self.root/"participation.json",new)
            if "neural" in changes:self.settings.update({"neural_search":new["neural"]},neural_available=True)
            if changes.get("paused") is False:self.settings.update({"collect_research_feedback":True},neural_available=True)
            if new["paused"]:self.cancel.set()
            if not new["neural"]:self.ranker.worker.close()
            if removed:self.forget(removed)
        return self.status()

    def exit(self):
        self.cancel.set();self.ranker.worker.close()
        if self.root.exists():
            with self.lock:
                state=self.state();state.update(accepted=False,paused=True,neural=False)
                atomic_write_json(self.root/"participation.json",state)
        return self.status()

    def allowed(self,document_id,*,journal=False):
        state=self.state();permissions=self.settings.read()
        if not self.collecting() or document_id in permissions.excluded_document_ids:return False
        # Every passage is opt-in by ID; unknown document collections are never
        # guessed to be safe. Journal scope has its own explicit permission.
        if document_id in state.get("journal_scope",[]):
            return permissions.allow_journal_learning
        return not journal and document_id in state.get("feedback_scope",[])

    def record(self,presentation,*,feedback=None,reason=None,source="feedback"):
        if not self.collecting() or not presentation:return {"status":"not_collected"}
        event=deepcopy(presentation);receipt=event.get("receipt",{});identity=receipt.get("target_id")
        if identity in self.settings.read().excluded_document_ids:return {"status":"excluded"}
        if not self.allowed(identity):event["evidence_text"]=None
        if event.get("evidence_text") and digest(event["evidence_text"])!=receipt.get("evidence_hash"):
            self.rejections+=1;return {"status":"rejected_evidence_hash"}
        event.update(feedback=feedback,reason=reason,source_kind=source,timestamp=datetime.now(timezone.utc).isoformat())
        current=self.document_reader(identity) if self.document_reader else None
        if current is None:
            self.rejections+=1;return {"status":"rejected_missing_document"}
        result=self.queue().append(event,verified=True,current_revision=document_revision(current),source=source)
        if result.get("stored") is False:self.rejections+=1
        result["advisory"]=advisory(event)
        return result

    def review(self,event_id,receipt_hash,grade,rationale,role,expected_answer=None,answer_reviewed=False):
        if not self.collecting():raise ValueError("Learning is paused or BETA is inactive")
        row=next((r for r in self.queue().list(2000) if r["id"]==event_id),None)
        if not row:raise ValueError("Event not found")
        doc_id=row["document_id"]
        if not self.allowed(doc_id):raise ValueError("Document is outside current learning scope")
        doc=self.document_reader(doc_id) if self.document_reader else None
        if doc is None:raise ValueError("Document removed")
        result=self.queue().review(event_id,receipt_hash=receipt_hash,grade=grade,rationale=rationale,role=role,current_revision=document_revision(doc))
        if answer_reviewed:
            self.queue().set_answer_review(event_id,expected_answer)
        return result

    def journal(self,document_ids):
        if not self.collecting():raise ValueError("Learning is paused or not accepted")
        output=[]
        for identity in document_ids:
            if not self.allowed(identity,journal=True):continue
            doc=self.document_reader(identity) if self.document_reader else None
            if doc is None:continue
            text=doc.content.split("\n\n")[0][:4000]
            question="find my note about "+doc.title[:150]
            receipt={"version":1,"context_id":"journal-synthetic-"+uuid4().hex,"effective_query":question,
                "target_type":"SERP_RESULT","target_id":doc.id,"document_revision":document_revision(doc),
                "evidence_id":doc.slug+"#journal-generated","evidence_hash":digest(text),"generation":"journal_generated_not_a_search",
                "ranking_version":"journal-suggestion-v1","model_versions":{"generator":"deterministic_title_question_v1"}}
            event={"receipt":receipt,"evidence_text":text,"source_kind":"journal_synthetic","feedback":None,"reason":None,
                   "synthetic_provenance":"title question; not an independently verified relevance label"}
            output.append(self.queue().append(event,verified=True,current_revision=document_revision(doc),source="journal_synthetic"))
        return {"generated":len(output),"events":output,"labels_created":0}

    def forget(self,document_ids):
        self.cancel.set();self.ranker.worker.close()
        self.owned_root()
        (self.root/"active.json").unlink(missing_ok=True)
        if self.thread and self.thread.is_alive():self.thread.join(timeout=3)
        if self.thread and self.thread.is_alive():raise ValueError("Training still stopping; adaptations disabled, retry cleanup")
        if (self.root/"learning.db").exists():self.queue().forget(document_ids)
        # Selective unlearning is not asserted. Drop every private adaptation
        # when a source is excluded/deleted, and return to the public base.
        for name in ("models","jobs"):
            path=self.root/name
            if path.exists() and path.resolve().is_relative_to(self.root.resolve()):shutil.rmtree(path)

    def clear(self,confirmed=False):
        if confirmed is not True:raise ValueError("Explicit deletion confirmation required")
        self.exit()
        if self.thread and self.thread.is_alive():self.thread.join(timeout=3)
        if self.thread and self.thread.is_alive():raise ValueError("Training is still stopping; retry deletion")
        self.owned_root()
        if self.root.exists():shutil.rmtree(self.root)
        return {"status":"experimental_data_deleted","documents_changed":False}

    def status(self):
        supported=self.channel
        if supported:self.expire()
        state=self.state() if supported else {"accepted":False}
        model=None
        if self.accepted():
            try:
                current=self.models.current();model={"version":current.identity,"checkpoint":current.checkpoint_hash,"trust":"owner_local_experimental_not_production_signed"}
            except Exception:model={"status":"invalid_artifact_fallback"}
        counts=self.queue().counts() if supported and (self.root/"learning.db").exists() else {"total":0}
        job=None
        if supported and (self.root/"last-job.json").exists():
            try:job=json.loads((self.root/"last-job.json").read_text())
            except ValueError:job={"status":"corrupt_job_receipt"}
        return {"version":1,"channel":"aggressive_learning_beta" if supported else "stable","supported":supported,
                "participation":state,"agreement":AGREEMENT,"agreement_hash":AGREEMENT_HASH,
                "learning_active":self.collecting(),
                "model":model,"ranking_mode":"experimental_bounded_neural" if self.enabled() else "deterministic_maae",
                "inference":self.last_inference,"fallback_events":self.fallbacks,"rejected_events":self.rejections,
                "evidence":counts,"last_job":job,"training_running":bool(self.thread and self.thread.is_alive()),
                "external_uploads":False,"independent_public_acceptance":False,
                "privacy":self.settings.read().model_dump() if supported else {},
                "rollback_available":(self.root/"active.json").exists() if supported else False}

    def close(self):
        self.cancel.set();self.ranker.worker.close()
        if self.thread and self.thread.is_alive():self.thread.join(timeout=6)

    def expire(self):
        if time.monotonic()-self._last_expire<60:return
        self._last_expire=time.monotonic()
        if not self.root.exists():return
        self.owned_root()
        cutoff=time.time()-self.state().get("retention_days",30)*86400
        pointer=self.root/"active.json"
        try:pointers=json.loads(pointer.read_text()) if pointer.exists() else {}
        except ValueError:pointers={}
        active=self.root/"models"/pointers.get("current","base")
        if active.exists() and active.stat().st_mtime<cutoff:
            self.ranker.worker.close();pointer.unlink(missing_ok=True);pointers={}
        # Preserve current/previous until expiry; bound other retained artifacts.
        keep={name for name in (pointers.get("current"),pointers.get("previous")) if name and name!="base" and
              (self.root/"models"/name).exists() and (self.root/"models"/name).stat().st_mtime>=cutoff}
        for folder,maximum in (("jobs",16),("models",8)):
            parent=self.root/folder
            if not parent.exists():continue
            paths=sorted((p for p in parent.iterdir() if p.is_dir() and p.resolve().is_relative_to(self.root.resolve())),key=lambda p:p.stat().st_mtime,reverse=True)
            used=0
            for index,path in enumerate(paths):
                size=sum(f.stat().st_size for f in path.rglob("*") if f.is_file() and not f.is_symlink())
                used+=size
                if (path.stat().st_mtime<cutoff or index>=maximum or used>128*1024*1024) and path.name not in keep:
                    if self.thread and self.thread.is_alive() and folder=="jobs":continue
                    shutil.rmtree(path)

    def train_now(self):
        if not self.collecting():raise ValueError("Accept and resume local BETA learning first")
        if self.document_reader is None:raise ValueError("Document revision resolver unavailable")
        from .lifecycle import snapshot
        data=snapshot(self.queue(),self.document_reader,self.allowed)
        with self.lock:
            if self.thread and self.thread.is_alive():raise ValueError("A training job is already running")
            job_id=uuid4().hex;job=self.root/"jobs"/job_id;job.mkdir(parents=True,exist_ok=False)
            atomic_write_json(job/"dataset.json",data)
            current=self.models.current()
            self.cancel=Event();self._job_status(job_id,"queued",{"snapshot_hash":data["snapshot_hash"],"training_examples":len(data["train"]),"evaluation_examples":len(data["evaluation"])})
            self.thread=Thread(target=self._train_job,args=(job_id,job,data,current),daemon=True);self.thread.start()
        return {"job_id":job_id,"status":"queued"}

    def _job_status(self,job_id,status,extra=None):
        receipt={"version":1,"job_id":job_id,"status":status,"updated":time.time(),**(extra or {})}
        atomic_write_json(self.root/"last-job.json",receipt)
        return receipt

    def _train_job(self,job_id,job,data,current):
        try:
            self._job_status(job_id,"training",{"training_examples":len(data["train"]),"snapshot_hash":data["snapshot_hash"]})
            result=run_training({"dataset":str(job/"dataset.json"),"output":str(job/"candidate"),"base":str(current.directory),"steps":100},self.cancel)
            if self.cancel.is_set() or not self.collecting():raise InterruptedError()
            self._job_status(job_id,"evaluating",result)
            decision=self._evaluate_job(job_id,job,data,current)
            self._job_status(job_id,"promoted" if decision["decision"]=="promote" else "rejected_or_review_required",{"evaluation":decision,**result})
        except InterruptedError:self._job_status(job_id,"cancelled",{"active_checkpoint_preserved":True})
        except Exception as exc:self._job_status(job_id,"failed",{"error_code":type(exc).__name__,"active_checkpoint_preserved":True})

    def _evaluate_job(self,job_id,job,data,current):
        from .lifecycle import evaluate_local,decide
        from .neural import predict,load_model
        self._snapshot_current(data)
        decision=run_training({"operation":"evaluation","dataset":str(job/"dataset.json"),"candidate":str(job/"candidate"),
                              "current":str(current.directory),"base":str(self.base_path)},self.cancel,timeout=60)
        # Real isolated health checks are independent of training loss.
        probe=ResidentInference()
        try:
            manifest=json.loads((job/"candidate/training.json").read_text())
            payload={"directory":str(job/"candidate"),"checkpoint_hash":manifest["checkpoint_sha256"],
                "tokenizer_hash":manifest["tokenizer_sha256"],"query":"find a note","evidence":["a short synthetic note"]}
            probe([],payload);_,health=probe([],payload)
            decision["metrics"]["inference_health"]=health["latency_ms"]<=150 and health["peak_bytes"]<=384*1024*1024
            decision={**decision,**decide(decision["metrics"]),"health":health}
        except Exception:decision={**decision,**decide({**decision["metrics"],"inference_health":False})}
        finally:probe.close()
        atomic_write_json(job/"evaluation.json",decision)
        training=json.loads((job/"candidate/training.json").read_text())
        decision.update(candidate_checkpoint=training["checkpoint_sha256"],dataset_snapshot=data["snapshot_hash"],
                        current_checkpoint=current.checkpoint_hash)
        atomic_write_json(job/"evaluation.json",decision)
        from .lifecycle import lineage
        inherited=set(json.loads((current.directory/"beta-model.json").read_text()).get("training_lineage",[]))
        provenance=inherited|lineage(data["train"]+data["validation"])
        if len(provenance)>10000:raise ValueError("Adaptation lineage budget exceeded; restart from the public base")
        write_manifest(job/"candidate",identity="PESE-local:"+job_id,origin="local_adaptation",brain_binding=self.models.binding,evaluation=decision,training=training,lineage=provenance)
        with self.lock:
            if self.cancel.is_set() or not self.collecting():raise InterruptedError()
            self._snapshot_current(data)
            if decision["decision"]=="promote":
                self.ranker.worker.close();self.models.promote(job/"candidate",decision,lambda _:True)
        return decision

    def _snapshot_current(self,data):
        for row in data["train"]+data["validation"]+data["evaluation"]:
            doc=self.document_reader(row["document_id"]) if self.document_reader else None
            if doc is None or not self.allowed(row["document_id"]) or document_revision(doc)!=row.get("document_revision"):
                raise ValueError("A training/evaluation source revision or permission changed; candidate cannot be promoted")

    def evaluate_latest(self):
        if not self.collecting():raise ValueError("BETA learning is paused or inactive")
        if self.thread and self.thread.is_alive():raise ValueError("Training/evaluation already in progress")
        path=self.root/"last-job.json"
        if not path.exists():raise ValueError("No candidate job exists")
        job_id=json.loads(path.read_text())["job_id"]
        if len(job_id)!=32 or any(c not in "0123456789abcdef" for c in job_id):raise ValueError("Invalid job receipt")
        job=self.root/"jobs"/job_id
        data=json.loads((job/"dataset.json").read_text())
        return self._evaluate_job(job_id,job,data,self.models.current())

    def rollback(self):
        if not self.accepted():raise ValueError("BETA participation is not active")
        self.cancel.set();self.ranker.worker.close();model=self.models.rollback()
        return {"status":"rolled_back","model":model.identity}


def runtime():
    from ...config import RUNTIME_ROOT
    key=(str(RUNTIME_ROOT.resolve()),beta_channel())
    with _LOCK:
        if key not in _RUNTIMES:_RUNTIMES[key]=BetaRuntime(RUNTIME_ROOT)
        return _RUNTIMES[key]
