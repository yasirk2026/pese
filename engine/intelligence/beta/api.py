"""Local, launch-token protected in desktop, closed-BETA control endpoints."""
from fastapi import APIRouter,Body,HTTPException
from pydantic import BaseModel,Field,StrictBool,StrictInt
from ..evidence import digest
from .runtime import runtime as get_runtime


def runtime():
    from ...api.main import store
    owner=get_runtime();owner.document_reader=store.get_document;return owner

router=APIRouter(prefix="/api/intelligence/beta")


def invoke(function):
    try:return function()
    except (ValueError,FileNotFoundError) as exc:
        # Controlled operational messages only; never echo raw evidence/errors.
        raise HTTPException(409,detail=str(exc) if isinstance(exc,ValueError) else "Required local artifact is unavailable") from exc


class AgreementRequest(BaseModel):
    accepted: StrictBool
    agreement_hash: str=Field(min_length=64,max_length=64)
    feedback_scope: list[str]=Field(default_factory=list,max_length=10000)
    journal_scope: list[str]=Field(default_factory=list,max_length=10000)
    approve_all_current:StrictBool=False
    scope_snapshot_hash:str|None=Field(default=None,min_length=64,max_length=64)
    retention_days:StrictInt=Field(default=7,ge=1,le=90)


def current_document_ids():
    from ...api.main import store
    return [doc.id for doc in store.list_documents()]


@router.get("/scope")
def scope():return invoke(lambda:runtime().scope_snapshot(current_document_ids()))


@router.get("/status")
def status():return runtime().status()


@router.post("/agreement")
def agreement(body:AgreementRequest):
    if body.accepted is not True:return runtime().exit()
    def accept():
        owner=runtime();ids=body.feedback_scope
        if body.approve_all_current:
            snapshot=owner.scope_snapshot(current_document_ids())
            if body.scope_snapshot_hash!=snapshot["snapshot_hash"]:
                raise ValueError("Current documents or exclusions changed; review the scope again")
            ids=snapshot["document_ids"]
        return owner.accept(body.agreement_hash,affirmative=body.accepted,feedback_scope=ids,
                            journal_scope=body.journal_scope,retention_days=body.retention_days,
                            scope_mode="all_current_snapshot" if body.approve_all_current else "selected_ids")
    return invoke(accept)


@router.put("/settings")
def settings(changes:dict=Body(...)):return invoke(lambda:runtime().configure(changes))


@router.get("/examples")
def examples():
    owner=runtime()
    if not owner.channel:raise HTTPException(409,"BETA capability required")
    rows=owner.queue().list() if (owner.root/"learning.db").exists() else []
    return {"examples":[{**row,"receipt_hash":digest(row["payload"])} for row in rows]}


class ReviewRequest(BaseModel):
    event_id:str=Field(max_length=64)
    receipt_hash:str=Field(min_length=64,max_length=64)
    grade:StrictInt=Field(ge=0,le=2)
    rationale:str=Field(min_length=3,max_length=500)
    role:str
    expected_answer:str|None=Field(default=None,max_length=1000)
    answer_reviewed:StrictBool=False


@router.post("/review")
def review(body:ReviewRequest):return invoke(lambda:runtime().review(**body.model_dump()))


@router.post("/train")
def train():return invoke(lambda:runtime().train_now())


@router.post("/cancel")
def cancel():
    runtime().cancel.set();return {"status":"cancellation_requested"}


@router.post("/evaluate")
def evaluate():return invoke(lambda:runtime().evaluate_latest())


@router.post("/rollback")
def rollback():return invoke(lambda:runtime().rollback())


@router.post("/journal")
def journal(document_ids:list[str]=Body(...)):return invoke(lambda:runtime().journal(document_ids))


@router.post("/exit")
def exit_beta():return runtime().exit()


class ClearRequest(BaseModel):
    confirmed:StrictBool=False


@router.post("/clear")
def clear(body:ClearRequest):return invoke(lambda:runtime().clear(body.confirmed))
