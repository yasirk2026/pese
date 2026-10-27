"""Bounded, versioned research sidecar. Never part of a Brain/Drive snapshot."""
from contextlib import closing
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
from threading import RLock
import time
from uuid import uuid4
from ..evidence import digest
from .judge import assess,Quality


class LearningQueue:
    def __init__(self,path,*,max_events=2000,max_bytes=16*1024*1024,retention_days=30):
        self.path=Path(path);self.max_events=max_events;self.max_bytes=max_bytes;self.retention_days=retention_days
        if self.path.is_symlink():raise ValueError("Learning queue must be a regular local file")
        self.lock=RLock()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(self.connect()) as db:
            version=db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0,1):raise ValueError("Unsupported learning queue schema")
            db.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY,dedupe TEXT UNIQUE NOT NULL,identity TEXT NOT NULL,document_id TEXT NOT NULL,revision TEXT NOT NULL,payload TEXT NOT NULL,quality TEXT NOT NULL,action TEXT NOT NULL,created REAL NOT NULL,review TEXT,role TEXT)")
            db.execute("PRAGMA user_version=1");db.commit()

    def connect(self):
        db=sqlite3.connect(self.path,timeout=5);db.row_factory=sqlite3.Row
        return db

    def prune(self,db):
        db.execute("DELETE FROM events WHERE created < ?",(time.time()-self.retention_days*86400,))
        while True:
            count,size=db.execute("SELECT COUNT(*),COALESCE(SUM(length(CAST(payload AS BLOB))),0) FROM events").fetchone()
            if count<self.max_events and size<self.max_bytes:break
            db.execute("DELETE FROM events WHERE id=(SELECT id FROM events ORDER BY created,id LIMIT 1)")

    def append(self,event,*,verified,current_revision=None,source="feedback"):
        raw=json.dumps(event,ensure_ascii=False,allow_nan=False,sort_keys=True)
        if len(raw.encode())>16000:raise ValueError("Learning event too large")
        if len(raw.encode())>self.max_bytes:raise ValueError("Event exceeds queue storage budget")
        receipt=event.get("receipt",{})
        identity=digest({k:receipt.get(k) for k in ("effective_query","target_type","target_id","document_revision","evidence_id","evidence_hash")})
        dedupe=digest((identity,event.get("feedback"),event.get("reason"),source))
        with self.lock,closing(self.connect()) as db:
            old=db.execute("SELECT * FROM events WHERE dedupe=?",(dedupe,)).fetchone()
            if old:return {"id":old["id"],"quality":old["quality"],"deduplicated":True}
            previous=db.execute("SELECT payload FROM events WHERE identity=?",(identity,)).fetchall()
            contradictory=event.get("feedback") in ("LIKE","DISLIKE") and any(json.loads(row[0]).get("feedback") in ("LIKE","DISLIKE") and json.loads(row[0]).get("feedback")!=event.get("feedback") for row in previous)
            judgment=assess(event,verified=verified,current_revision=current_revision,contradictory=contradictory)
            if source=="journal_synthetic" and judgment["quality"]!=Quality.INVALID.value:
                judgment={"quality":Quality.CANDIDATE.value,"action":"review_generated_example","reason":"Synthetic question is not a label"}
            if judgment["quality"]==Quality.INVALID.value:return {**judgment,"stored":False}
            if contradictory:
                db.execute("UPDATE events SET quality=?,action='quarantine',review=NULL WHERE identity=?",(Quality.CONTRADICTORY.value,identity))
            self.prune(db)
            # Make space for this record without exceeding the payload budget.
            while db.execute("SELECT COALESCE(SUM(length(CAST(payload AS BLOB))),0) FROM events").fetchone()[0]+len(raw.encode())>self.max_bytes:
                db.execute("DELETE FROM events WHERE id=(SELECT id FROM events ORDER BY created,id LIMIT 1)")
            event_id=uuid4().hex
            db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?)",(event_id,dedupe,identity,receipt.get("target_id",""),
                receipt.get("document_revision",""),raw,judgment["quality"],judgment["action"],time.time(),None,None))
            db.commit()
            return {"id":event_id,"quality":judgment["quality"],"action":judgment["action"],"stored":True}

    def list(self,limit=100):
        with self.lock,closing(self.connect()) as db:
            db.execute("DELETE FROM events WHERE created < ?",(time.time()-self.retention_days*86400,));db.commit()
            return [self.decode(r) for r in db.execute("SELECT * FROM events ORDER BY created DESC LIMIT ?",(min(2000,max(1,limit)),))]

    @staticmethod
    def decode(row):
        result=dict(row);result["payload"]=json.loads(result["payload"])
        result["review"]=json.loads(result["review"]) if result["review"] else None
        return result

    def counts(self):
        with self.lock,closing(self.connect()) as db:
            db.execute("DELETE FROM events WHERE created < ?",(time.time()-self.retention_days*86400,));db.commit()
            counts={r[0]:r[1] for r in db.execute("SELECT quality,COUNT(*) FROM events GROUP BY quality")}
            counts["total"]=sum(counts.values());return counts

    def review(self,event_id,*,receipt_hash,grade,rationale,role,current_revision):
        if role not in ("train","evaluation"):raise ValueError("Choose training or protected evaluation role")
        with self.lock,closing(self.connect()) as db:
            row=db.execute("SELECT * FROM events WHERE id=?",(event_id,)).fetchone()
            if row is None:raise ValueError("Evidence event missing or expired")
            if row["role"] and row["role"]!=role:raise ValueError("Protected split roles cannot be reassigned")
            event=json.loads(row["payload"])
            if row["quality"]==Quality.CONTRADICTORY.value:raise ValueError("Resolve contradictory actions before review")
            if not event.get("evidence_text"):raise ValueError("Text was not eligible for collection")
            review={"receipt_hash":receipt_hash,"grade":grade,"rationale":rationale,"objective":"retrieval_relevance",
                    "reviewer":"local_owner","reviewed_at":datetime.now(timezone.utc).isoformat()}
            result=assess(event,verified=True,current_revision=current_revision,review=review)
            if result["quality"]!=Quality.VERIFIED.value:raise ValueError(result["reason"])
            # A query/document family cannot be put into both train and holdout.
            related=db.execute("SELECT role,payload FROM events WHERE role IS NOT NULL").fetchall()
            for old in related:
                old_event=json.loads(old["payload"])
                if old[0]!=role and (old_event["receipt"]["effective_query"]==event["receipt"]["effective_query"] or
                                    old_event["receipt"]["target_id"]==event["receipt"]["target_id"]):
                    raise ValueError("Query/document family crosses training and evaluation")
            db.execute("UPDATE events SET quality=?,action=?,review=?,role=? WHERE id=?",(result["quality"],result["action"],json.dumps(review),role,event_id));db.commit()
            return result

    def set_answer_review(self,event_id,expected_answer):
        if expected_answer is not None and (not isinstance(expected_answer,str) or len(expected_answer)>1000):raise ValueError("Expected answer must be bounded text or explicit abstention")
        with self.lock,closing(self.connect()) as db:
            row=db.execute("SELECT review FROM events WHERE id=?",(event_id,)).fetchone()
            if not row or not row[0]:raise ValueError("Relevance review required first")
            review=json.loads(row[0]);review.update(answer_reviewed=True,expected_answer=expected_answer)
            db.execute("UPDATE events SET review=? WHERE id=?",(json.dumps(review),event_id));db.commit()

    def forget(self,document_ids):
        with self.lock,closing(self.connect()) as db:
            for identity in document_ids:db.execute("DELETE FROM events WHERE document_id=?",(identity,))
            db.commit()
