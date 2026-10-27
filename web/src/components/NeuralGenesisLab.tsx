"use client";
import { useCallback, useEffect, useState } from "react";
import { betaRequest, saveIntelligenceSettings, type BetaStatus, type BetaExample } from "@/lib/api";
import { BetaDisclosure } from "./BetaDisclosure";
type ScopePreview={snapshot_hash:string;current_document_count:number;document_ids:string[];excluded_current_count:number};

export function NeuralGenesisLab() {
  const [status,setStatus]=useState<BetaStatus|null>(null);
  const [examples,setExamples]=useState<BetaExample[]>([]);
  const [busy,setBusy]=useState(false); const [notice,setNotice]=useState("");
  const [agreed,setAgreed]=useState(false); const [clearReview,setClearReview]=useState(false);
  const [feedbackScope,setFeedbackScope]=useState("");const [journalScope,setJournalScope]=useState("");
  const [retention,setRetention]=useState(7);const [selected,setSelected]=useState<BetaExample|null>(null);
  const [allCurrent,setAllCurrent]=useState(false);
  const [scopePreview,setScopePreview]=useState<ScopePreview|null>(null);
  const [grade,setGrade]=useState(2);const [role,setRole]=useState("train");const [rationale,setRationale]=useState("");
  const [answerReviewed,setAnswerReviewed]=useState(false);const [expectedAnswer,setExpectedAnswer]=useState("");
  const ids=(text:string)=>text.split(",").map(s=>s.trim()).filter(Boolean);
  const refresh=useCallback(async()=>{const data=await betaRequest<BetaStatus>("status");setStatus(data);return data;},[]);
  useEffect(()=>{let active=true;betaRequest<BetaStatus>("status").then(data=>{if(active){setStatus(data);setFeedbackScope(data.participation.feedback_scope?.join(", ")||"");setJournalScope(data.participation.journal_scope?.join(", ")||"");setRetention(data.participation.retention_days||7);}}).catch(error=>{if(active)setNotice(error.message);});return()=>{active=false;};},[]);
  useEffect(()=>{if(!status?.training_running)return;const timer=setInterval(()=>{refresh().catch(error=>setNotice(error.message));},1500);return()=>clearInterval(timer);},[status?.training_running,refresh]);
  async function action(path:string,body?:unknown,method="POST") {
    setBusy(true);setNotice("");
    try {const data=await betaRequest<Record<string,unknown>>(path,method,body);await refresh();setNotice(typeof data.status==="string" ? data.status.replaceAll("_"," ") : "Local operation completed.");
      if(path==="exit"||path==="clear"||(path==="agreement"&&(body as {accepted?:boolean})?.accepted===false)){
        const host=window as unknown as {__PESE_CONFIG__?:{trainingUpdate?:boolean};chrome?:{webview?:{postMessage:(s:string)=>void}}};
        if(host.__PESE_CONFIG__?.trainingUpdate)host.chrome?.webview?.postMessage("beta_exit");
      }
      return data;}
    catch(error){setNotice((error as Error).message);return null;}
    finally{setBusy(false);}
  }
  async function inspect(){setBusy(true);try{const data=await betaRequest<{examples:BetaExample[]}>("examples");setExamples(data.examples);}catch(error){setNotice((error as Error).message);}finally{setBusy(false);}}
  const button="px-3 py-2 rounded-lg border border-surface-border text-xs font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:bg-neutral-100 dark:hover:bg-neutral-800";
  const panel="rounded-2xl border border-surface-border bg-surface p-5 space-y-4";
  const field="block w-full p-2 rounded-lg border border-surface-border bg-transparent text-sm";
  if(!status)return <p role="status">{notice||"Loading measured intelligence state…"}</p>;
  return <div className="max-w-5xl mx-auto space-y-6 pb-10" data-testid="neural-genesis-lab">
    <header className="space-y-2"><p className="text-xs uppercase tracking-widest text-orange-600">Closed experimental channel</p><h1 className="text-3xl font-semibold">Neural Genesis Lab</h1>
      <p className="text-sm text-neutral-500">Experience → evidence selection → candidate training → evaluation → promotion. A vote does not immediately change neural parameters. Neural ranking can be active while no training job is running.</p></header>
    <BetaDisclosure agreement={status.agreement}/>
    {status.supported&&<section className={panel} aria-label="Current Brain scope">
      <h2 className="font-semibold">Approve this Brain&apos;s current document collection</h2>
      <p className="text-sm">This applies only to this Brain and Windows account. There is no two-article restriction. Normal retrieval still sends at most six eligible candidates to the neural model. New document IDs are never added to learning scope automatically.</p>
      <button className={button} disabled={busy} onClick={async()=>{setBusy(true);try{setScopePreview(await betaRequest<ScopePreview>("scope"));}catch(error){setNotice((error as Error).message);}finally{setBusy(false);}}}>Review current Brain scope</button>
      {scopePreview&&<><p className="text-sm">{scopePreview.current_document_count} current documents; {scopePreview.document_ids.length} eligible after {scopePreview.excluded_current_count} exclusions.</p>
        <label className="flex gap-2 text-sm"><input type="checkbox" checked={allCurrent} onChange={e=>setAllCurrent(e.target.checked)}/>I explicitly approve all these current non-sensitive documents. Future documents require another approval.</label>
        {status.participation.accepted&&<button className={button} disabled={!allCurrent||busy} onClick={()=>action("agreement",{accepted:true,agreement_hash:status.agreement_hash,approve_all_current:true,scope_snapshot_hash:scopePreview.snapshot_hash,retention_days:retention})}>Approve current collection</button>}</>}
    </section>}
    {!status.supported && <div className={panel}><h2 className="font-semibold">This installation uses the stable intelligence policy</h2><p className="text-sm">Closed-BETA collection and activation are unavailable in this build. Ordinary search remains available. Official model signing is unchanged.</p></div>}
    {status.supported&&!status.participation.accepted&&<section className={panel} aria-label="Aggressive BETA agreement">
      <h2 className="font-semibold text-orange-600">{status.agreement.title}</h2>
      <ul className="space-y-2 text-sm list-disc pl-5">{status.agreement.statements.map(statement=><li key={statement}>{statement}</li>)}</ul>
      <label className="block text-sm">Or choose specific document IDs for a smaller pilot (empty means no collection)<input data-testid="beta-feedback-scope" className={field} value={feedbackScope} onChange={e=>setFeedbackScope(e.target.value)} placeholder="Comma-separated document IDs"/></label>
      <label className="block text-sm">Journal/notes document IDs (also require journal permission)<input className={field} value={journalScope} onChange={e=>setJournalScope(e.target.value)}/></label>
      <label className="flex items-start gap-3 text-sm"><input type="checkbox" checked={agreed} onChange={e=>setAgreed(e.target.checked)} className="mt-1"/>I affirmatively accept the defined local experimental behavior, confirm my approved scope excludes prohibited sensitive material, and understand that ranking quality may be worse. This does not authorize cloud sharing.</label>
      <div className="flex gap-3"><button className={button} disabled={!agreed||busy||(allCurrent&&!scopePreview)} onClick={()=>action("agreement",{accepted:true,agreement_hash:status.agreement_hash,feedback_scope:ids(feedbackScope),journal_scope:ids(journalScope),retention_days:retention,approve_all_current:allCurrent,scope_snapshot_hash:allCurrent?scopePreview?.snapshot_hash:undefined})}>Accept closed BETA</button><button className={button} disabled={busy} onClick={()=>action("agreement",{accepted:false,agreement_hash:status.agreement_hash})}>Decline</button></div>
    </section>}
    <section className={panel} aria-label="Active intelligence"><h2 className="font-semibold">Active intelligence</h2>
      <dl className="grid sm:grid-cols-2 gap-4 text-sm"><div><dt className="text-neutral-500">Ranking mode</dt><dd>{status.ranking_mode.replaceAll("_"," ")}</dd></div><div><dt className="text-neutral-500">Active model</dt><dd>{status.model?.version||status.model?.status||"Deterministic MAAE"}</dd></div>
        <div className="sm:col-span-2"><dt className="text-neutral-500">Checkpoint SHA-256</dt><dd className="font-mono text-xs break-all">{status.model?.checkpoint||"No active experimental checkpoint"}</dd></div>
        <div><dt className="text-neutral-500">Inference</dt><dd>{status.inference.status}{status.inference.latency_ms!==undefined?` · ${status.inference.latency_ms.toFixed(2)} ms`:""}</dd></div>
        <div><dt className="text-neutral-500">Fallback events since engine startup</dt><dd>{status.fallback_events}</dd></div></dl>
      <p className="text-xs text-neutral-500">The base model was trained on original synthetic English specifications. Public independent human acceptance has not been achieved. MAAE evidence admission and answer grounding remain authoritative.</p>
      {status.participation.accepted&&<div className="flex flex-wrap gap-2"><button className={button} disabled={busy} onClick={()=>action("settings",{neural:false},"PUT")}>Switch to deterministic MAAE</button><button className={button} disabled={busy} onClick={()=>action("settings",{neural:true},"PUT")}>Enable bounded BETA ranking</button><button className={button} disabled={!status.rollback_available||busy} onClick={()=>action("rollback")}>Revert checkpoint</button></div>}
    </section>
    <section className={panel} aria-label="Learning evidence"><h2 className="font-semibold">Learning evidence</h2><p className="text-sm">Local collection is {status.learning_active?"active":"paused or unavailable"}. Missing clarification stays uncertain. The learned feedback-meaning classifier is advisory; hard provenance and explicit review control training admission.</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">{["total","verified_training_evidence","high_quality_review_candidate","preference_only","ambiguous","contradictory"].map(key=><div key={key} className="rounded-xl bg-neutral-100 dark:bg-neutral-900 p-3"><p className="text-2xl tabular-nums">{status.evidence[key]||0}</p><p className="text-xs text-neutral-500">{key.replaceAll("_"," ")}</p></div>)}</div>
      <p className="text-xs text-neutral-500">Rejected events since startup: {status.rejected_events}. Generated journal examples remain pending review, not verified labels.</p>
      <div className="flex flex-wrap gap-2"><button className={button} disabled={!status.participation.accepted||busy} onClick={()=>action("settings",{paused:true},"PUT")}>Pause learning</button><button className={button} disabled={!status.participation.accepted||busy} onClick={()=>action("settings",{paused:false},"PUT")}>Resume learning</button><button className={button} disabled={!status.supported||busy} onClick={inspect}>Inspect eligible examples</button></div>
    </section>
    <section className={panel} aria-label="Model evolution"><h2 className="font-semibold">Model evolution</h2>
      <p className="font-medium text-sm">Training job: {status.training_running?"running":"not running"}</p>
      <p className="text-sm">{status.last_job?`Last job: ${status.last_job.status.replaceAll("_"," ")}`:"No local candidate training session has run."}</p>
      <p className="text-xs text-neutral-500">Training requires reviewed positive/negative examples in disjoint document groups. Automatic local promotion additionally requires twelve complete protected heldout query pools, independent of training, plus answer references and regression/resource checks. Insufficient evidence produces a visible refusal.</p>
      {status.last_job&&<pre className="max-h-72 overflow-auto rounded-lg bg-neutral-100 dark:bg-neutral-900 p-3 text-xs">{JSON.stringify(status.last_job,null,2)}</pre>}
      <div className="flex flex-wrap gap-2"><button className={button} disabled={!status.learning_active||status.training_running||busy} onClick={()=>action("train")}>Train candidate now</button><button className={button} disabled={!status.last_job||status.training_running||busy||!status.learning_active} onClick={()=>action("evaluate")}>Evaluate candidate</button><button className={button} disabled={!status.training_running||busy} onClick={()=>action("cancel")}>Cancel training</button></div>
    </section>
    {status.participation.accepted&&<section className={panel} aria-label="Learning privacy"><h2 className="font-semibold">Privacy, journal scope &amp; retention</h2>
      <label className="block text-sm">Feedback-learning document IDs<input className={field} value={feedbackScope} onChange={e=>setFeedbackScope(e.target.value)}/></label>
      <label className="block text-sm">Journal/notes document IDs<input className={field} value={journalScope} onChange={e=>setJournalScope(e.target.value)}/></label>
      <label className="flex items-center gap-3 text-sm"><input type="checkbox" checked={status.privacy.allow_journal_learning||false} disabled={busy} onChange={async e=>{setBusy(true);try{await saveIntelligenceSettings({allow_journal_learning:e.target.checked});await refresh();}catch(error){setNotice((error as Error).message);}finally{setBusy(false);}}}/>Allow these explicitly scoped notes to generate local review candidates</label>
      <label className="block text-sm">Retention in days<input type="number" min={1} max={90} className={field} value={retention} onChange={e=>setRetention(Number(e.target.value))}/></label>
      <p className="text-xs text-neutral-500">Raw events, queued examples and reviewed labels expire from capture time. Derived job datasets and private checkpoint files use the configured file-age window; cleanup runs during app maintenance. Newer weights may retain older patterns. The packaged base, documents, ordinary feedback, history, backups and copies elsewhere are not covered. Expiry is not proof of unlearning.</p>
      <p className="text-xs text-neutral-500">Excluded IDs: {status.privacy.excluded_document_ids?.join(", ")||"none"}. Removing a source from scope drops private adaptations and returns to the public base; selective unlearning is not claimed. External contribution permission: {status.privacy.community_contributions?"enabled separately for reviewed aggregate export":"off"}. No private uploader exists.</p>
      <div className="flex flex-wrap gap-2"><button className={button} disabled={busy} onClick={()=>action("settings",{feedback_scope:ids(feedbackScope),journal_scope:ids(journalScope),retention_days:retention},"PUT")}>Save learning scope</button><button className={button} disabled={!status.privacy.allow_journal_learning||busy} onClick={()=>action("journal",ids(journalScope))}>Generate journal review candidates</button><button className={button} disabled={busy} onClick={()=>action("exit")}>Exit experimental channel</button></div>
    </section>}
    {examples.length>0&&<section className={panel} aria-label="Evidence review"><h2 className="font-semibold">Local evidence review</h2><p className="text-xs text-neutral-500">All text below stays local. A relevance grade does not certify an answer. Evaluation roles are protected from later reassignment to training.</p>
      <div className="max-h-72 overflow-auto space-y-2">{examples.map(example=><button className="block w-full text-left p-3 border border-surface-border rounded-xl text-sm" key={example.id} onClick={()=>{setSelected(example);setRationale("");setAnswerReviewed(false);setExpectedAnswer("");}}><span className="block">{example.payload.receipt.effective_query}</span><span className="text-xs text-neutral-500">{example.quality.replaceAll("_"," ")} · {example.payload.receipt.target_id} · {example.payload.source_kind}</span></button>)}</div>
      {selected&&<div className="space-y-3"><p className="text-sm whitespace-pre-wrap">{selected.payload.evidence_text||"Passage text was not collected for this scope."}</p><p className="text-xs">Reaction: {selected.payload.feedback||"search presentation only"} · Reason: {selected.payload.reason||"not supplied"}</p>
        <select aria-label="Reviewed relevance grade" value={grade} onChange={e=>setGrade(Number(e.target.value))} className={field}><option value={2}>2 · Specifically useful evidence</option><option value={1}>1 · Topical, limited utility</option><option value={0}>0 · Not relevant</option></select>
        <select aria-label="Protected dataset role" value={role} onChange={e=>setRole(e.target.value)} className={field}><option value="train">Candidate training</option><option value="evaluation">Protected heldout evaluation</option></select>
        <textarea aria-label="Review rationale" className={field} value={rationale} onChange={e=>setRationale(e.target.value)} placeholder="Explain your relevance judgment"/>
        {role==="evaluation"&&<><label className="flex gap-2 text-sm"><input type="checkbox" checked={answerReviewed} onChange={e=>setAnswerReviewed(e.target.checked)}/>I also reviewed the expected grounded answer for this query.</label><input aria-label="Expected grounded answer" className={field} value={expectedAnswer} onChange={e=>setExpectedAnswer(e.target.value)} placeholder="Expected answer; leave empty only for expected abstention"/></>}
        <button className={button} disabled={busy||rationale.trim().length<3||!selected.payload.evidence_text||!status.learning_active} onClick={async()=>{const result=await action("review",{event_id:selected.id,receipt_hash:selected.receipt_hash,grade,rationale,role,answer_reviewed:answerReviewed,expected_answer:expectedAnswer||null});if(result){setSelected(null);await inspect();}}}>Confirm this exact local evidence review</button></div>}
    </section>}
    {status.supported&&<section className={panel}><h2 className="font-semibold text-red-600">Delete this account&apos;s experimental learning data</h2><p className="text-sm">This stops the BETA and deletes this account&apos;s queue, reviewed labels, job datasets and private checkpoints. Documents, canonical feedback, history, backups, other accounts and legacy copies remain. Exiting retains prior data until deletion/expiry. In the training update, decline or exit closes PESE.</p><label className="flex gap-2 text-sm"><input type="checkbox" checked={clearReview} onChange={e=>setClearReview(e.target.checked)}/>I confirm deletion of local experimental learning data.</label><button className={button} disabled={!clearReview||busy} onClick={()=>action("clear",{confirmed:true})}>Clear experimental learning data</button></section>}
    {notice&&<p role="status" className="text-sm border border-surface-border p-4 rounded-xl">{notice}</p>}
  </div>;
}
