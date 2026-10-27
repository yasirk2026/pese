"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getIntelligenceSettings, saveIntelligenceSettings, resetIntelligencePersonalization,
  previewIntelligenceContribution, exportIntelligenceContribution, cancelIntelligenceContribution,
  type IntelligenceSettings, type ContributionPreview } from "@/lib/api";

export function PrivacyIntelligence() {
  const [settings, setSettings] = useState<IntelligenceSettings | null>(null);
  const [available, setAvailable] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState<ContributionPreview | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [resetReview, setResetReview] = useState(false);
  const [exclusions, setExclusions] = useState("");
  useEffect(() => {
    let active = true;
    getIntelligenceSettings().then(data => {
      if (active) { setSettings(data.settings); setAvailable(data.neural_available); setExclusions(data.settings.excluded_document_ids.join(", ")); }
    }).catch(() => { if (active) setNotice("Local intelligence settings are unavailable. No new permission has been granted."); });
    return () => { active = false; };
  }, []);
  async function update(changes: Partial<IntelligenceSettings>) {
    setBusy(true); setNotice("");
    try {
      const data = await saveIntelligenceSettings(changes);
      setSettings(data.settings);
      if (changes.community_contributions === false) { setPreview(null); setReviewed(false); }
      setNotice("Saved for this Brain.");
    } catch (error) { setNotice((error as Error).message); }
    finally { setBusy(false); }
  }
  async function prepare() {
    setBusy(true); setNotice("");
    try { setPreview(await previewIntelligenceContribution()); setReviewed(false); }
    catch (error) { setNotice((error as Error).message); }
    finally { setBusy(false); }
  }
  async function download() {
    if (!preview || !reviewed) return;
    setBusy(true);
    try {
      const data = await exportIntelligenceContribution(preview);
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: "application/json"}));
      const link = document.createElement("a"); link.href = url; link.download = "pese-contribution-v1.json"; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setPreview(null); setNotice("Exported locally. Nothing was uploaded.");
    } catch (error) { setNotice((error as Error).message); }
    finally { setBusy(false); }
  }
  async function cancel() {
    if (!preview) return;
    setBusy(true);
    try { await cancelIntelligenceContribution(preview); setPreview(null); setReviewed(false); }
    catch (error) { setNotice((error as Error).message); }
    finally { setBusy(false); }
  }
  const controls: {key: "neural_search" | "learn_from_feedback" | "allow_journal_learning" | "community_contributions"; label: string; detail: string; disabled?: boolean}[] = [
    {key: "neural_search", label: "Enable neural search", disabled: !available,
      detail: available ? "A local model may adjust eligible result order. In the closed BETA this remains experimental; it is not public validation." : "Unavailable: no accepted model is active in this channel. Deterministic search remains active."},
    {key: "learn_from_feedback", label: "Learn from my search feedback",
      detail: "Existing Search Sync uses explicit likes and dislikes as bounded, exact-query preferences. It does not update neural parameters. Turning this off pauses new feedback and ignores saved preferences; saved records remain until reset."},
    {key: "allow_journal_learning", label: "Allow journal content for local learning",
      detail: "Off by default. Closed BETA also requires explicit document scope in Neural Genesis Lab. Generated question/passage pairs require review before private candidate training. Stable releases do not train journals. Indexing is independent."},
    {key: "community_contributions", label: "Help improve PESE for everyone",
      detail: "Off by default. Enables a preview and local export of coarse diagnostic categories. No upload service is configured. Every export needs a separate review; no queries, journal text, passages, embeddings or model deltas are included."},
  ];
  return <section className="p-6 rounded-2xl bg-surface border border-surface-border space-y-5" aria-label="Privacy and Intelligence">
    <div><h3 className="text-base font-semibold">Privacy &amp; Intelligence</h3>
      <Link href="/neural-genesis/" className="text-xs text-blue-600">Open Neural Genesis Lab</Link>
      <p className="text-xs text-neutral-500 mt-1">Permissions apply to this Brain and stay on this device. They are excluded from Drive backups and must be chosen again after recovery. Manual Brain backups still include saved search history and feedback.</p></div>
    {controls.map(control => <label key={control.key} className="flex items-start justify-between gap-4 p-4 rounded-xl border border-surface-border">
      <span><span className="text-sm font-medium">{control.label}</span><span className="block text-xs text-neutral-500 mt-1">{control.detail}</span></span>
      <input type="checkbox" aria-label={control.label} checked={settings?.[control.key] ?? false} disabled={!settings || busy || control.disabled}
        onChange={event => update({[control.key]: event.target.checked})} className="mt-1 accent-blue-600" />
    </label>)}
    <div className="text-xs space-y-2"><label htmlFor="intelligence-exclusions">Exclude document IDs from future research learning (comma separated)</label>
      <input id="intelligence-exclusions" value={exclusions} onChange={event => setExclusions(event.target.value)} disabled={!settings || busy} className="block w-full border border-surface-border rounded p-2 bg-transparent" />
      <button disabled={!settings || busy} onClick={() => update({excluded_document_ids: exclusions.split(",").map(s => s.trim()).filter(Boolean)})} className="text-blue-600 disabled:opacity-50">Save exclusions</button>
      <p className="text-neutral-500">Neural Genesis Lab shows closed-BETA collection, training and document scope. Exclusions do not remove documents from ordinary search.</p></div>
    <div className="flex gap-4 text-xs"><button disabled={!settings?.community_contributions || busy} onClick={prepare} className="text-blue-600 disabled:opacity-50">Preview diagnostic export</button>
      <button disabled={!settings || busy} onClick={() => setResetReview(true)} className="text-red-600 disabled:opacity-50">Reset local personalization</button></div>
    {resetReview && <div className="border border-red-300 rounded-xl p-4 text-xs space-y-3"><p>This deletes local preference votes, feedback audit and neural shadow observations. Documents and saved search history remain. Neural parameters have not been trained.</p>
      <button disabled={busy} onClick={async () => { setBusy(true); try { await resetIntelligencePersonalization(); setResetReview(false); setNotice("Local preferences and feedback diagnostics deleted."); } catch(error) { setNotice((error as Error).message); } finally { setBusy(false); } }} className="text-red-600 mr-4">Delete personalization records</button>
      <button disabled={busy} onClick={() => setResetReview(false)}>Cancel</button></div>}
    {preview && <div className="border border-surface-border rounded-xl p-4 text-xs space-y-3"><h4 className="font-semibold">Review the exact export</h4>
      <p>{preview.destination}</p><p>{preview.privacy}</p><p>{preview.retention}</p><p>{preview.revocation}</p>
      <pre className="overflow-auto max-h-64 bg-neutral-100 dark:bg-neutral-900 p-3 rounded">{JSON.stringify(preview.package, null, 2)}</pre>
      <label className="flex gap-2"><input type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)} />I reviewed these categories and approve this local export for future PESE improvement.</label>
      <button disabled={!reviewed || busy} onClick={download} className="text-blue-600 disabled:opacity-50 mr-4">Download reviewed JSON</button><button disabled={busy} onClick={cancel}>Cancel</button></div>}
    {notice && <p role="status" className="text-xs">{notice}</p>}
  </section>;
}
