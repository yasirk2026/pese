"use client";

import React, { useState } from "react";
import { RankingTrace, SearchResult, ComparativeExplain, explainRanking } from "@/lib/api";
import { ChevronDown, ChevronUp, AlertTriangle, CheckCircle, ArrowRight, ShieldCheck, Scale } from "lucide-react";

interface RankingTraceAuditProps {
  currentResult: SearchResult;
  allResults: SearchResult[];
  query: string;
}

export const RankingTraceAudit: React.FC<RankingTraceAuditProps> = ({
  currentResult,
  allResults,
  query,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [compareSlug, setCompareSlug] = useState<string>("");
  const [comparison, setComparison] = useState<ComparativeExplain | null>(null);
  const [comparingLoading, setComparingLoading] = useState(false);

  const trace = currentResult.trace;

  const handleCompare = async (targetSlug: string) => {
    setCompareSlug(targetSlug);
    if (!targetSlug) {
      setComparison(null);
      return;
    }
    setComparingLoading(true);
    try {
      const data = await explainRanking(query, currentResult.slug, targetSlug);
      setComparison(data);
    } catch (err) {
      console.error("Comparison error:", err);
    } finally {
      setComparingLoading(false);
    }
  };

  return (
    <div className="mt-2 text-xs font-mono">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-900 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-800 transition-colors"
      >
        <span>Audit Ranking Trace (Score: {currentResult.final_score.toFixed(4)})</span>
        {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      {isOpen && (
        <div className="mt-3 p-4 bg-neutral-950 text-neutral-200 rounded-lg border border-neutral-800 space-y-4 shadow-xl">
          {/* Header */}
          <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-neutral-800">
            <div>
              <span className="text-emerald-400 font-bold">Trace Audit: </span>
              <span className="text-neutral-300">{currentResult.title}</span>
              <span className="text-neutral-500 ml-2">({currentResult.slug})</span>
            </div>
            <div className="flex items-center gap-3">
              {trace.is_semantic_rescue && (
                <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-700">
                  Semantic Rescue
                </span>
              )}
              <div className="text-amber-400 font-bold">
                Final Score: {currentResult.final_score.toFixed(4)}
              </div>
            </div>
          </div>

          {/* Hybrid Retrieval & Fusion Summary (Phase 2B) */}
          <div className="p-3 bg-neutral-900/80 rounded border border-neutral-800 space-y-2">
            <div className="flex items-center justify-between text-neutral-400 uppercase text-[10px] tracking-wider font-semibold">
              <span>Hybrid Retrieval & Reciprocal Rank Fusion</span>
              <span className="text-cyan-400 font-mono lowercase">mode: {trace.retrieval_mode || "hybrid"}</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              <div className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60">
                <div className="text-neutral-500 text-[10px]">BM25 Rank</div>
                <div className="text-neutral-200 font-semibold mt-0.5">
                  {trace.bm25_rank ? `#${trace.bm25_rank}` : "None (Rescued)"}
                </div>
              </div>
              <div className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60">
                <div className="text-neutral-500 text-[10px]">Semantic Rank</div>
                <div className="text-neutral-200 font-semibold mt-0.5">
                  {trace.semantic_rank ? `#${trace.semantic_rank}` : "N/A"}
                </div>
              </div>
              <div className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60">
                <div className="text-neutral-500 text-[10px]">Dense Similarity</div>
                <div className="text-emerald-400 font-semibold mt-0.5">
                  {(trace.semantic_similarity ?? 0).toFixed(4)}
                </div>
              </div>
              <div className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60">
                <div className="text-neutral-500 text-[10px]">RRF Score (k=60)</div>
                <div className="text-purple-400 font-semibold mt-0.5">
                  {(trace.rrf_score ?? 0).toFixed(6)}
                </div>
              </div>
            </div>
            {trace.drift_penalty_applied && trace.drift_penalty_applied > 0 ? (
              <div className="text-xs text-rose-400 bg-rose-950/40 p-2 rounded border border-rose-900/60">
                ⚠️ Drift Penalty: -{Math.round(trace.drift_penalty_applied * 100)}% ({trace.drift_reason})
              </div>
            ) : null}
          </div>

          {/* PESE-QA-0 Reading Comprehension (Shadow Mode) */}
          {(trace.qa_shadow_answer !== undefined || trace.qa_agreement !== undefined) && (
            <div className="p-3 bg-neutral-900/80 rounded border border-purple-900/40 space-y-2">
              <div className="flex items-center justify-between text-neutral-400 uppercase text-[10px] tracking-wider font-semibold">
                <span className="flex items-center gap-1.5 text-purple-400">
                  <span>PESE-QA-0 Neural Reading (Shadow Mode)</span>
                </span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-bold ${
                  trace.qa_agreement === "YES"
                    ? "bg-emerald-950 text-emerald-300 border border-emerald-700"
                    : trace.qa_agreement === "BOTH_ABSTAIN"
                    ? "bg-slate-800 text-slate-300 border border-slate-700"
                    : "bg-amber-950 text-amber-300 border border-amber-700"
                }`}>
                  Agreement: {trace.qa_agreement || "N/A"}
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                <div className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60">
                  <div className="text-neutral-500 text-[10px]">Shadow Extracted Answer</div>
                  <div className="text-purple-300 font-semibold mt-0.5 font-sans">
                    {trace.qa_shadow_answer ? `"${trace.qa_shadow_answer}"` : <span className="italic text-neutral-500">Abstained (NO EVIDENCE)</span>}
                  </div>
                </div>
                <div className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60">
                  <div className="text-neutral-500 text-[10px]">Reader Confidence</div>
                  <div className="text-emerald-400 font-semibold mt-0.5">
                    {trace.qa_confidence ? `${(trace.qa_confidence * 100).toFixed(1)}%` : "N/A"}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Search Sync Preference Audit (Phase N3-A) */}
          <div className="p-3 bg-neutral-900/80 rounded border border-sky-900/40 space-y-2">
            <div className="flex items-center justify-between text-neutral-400 uppercase text-[10px] tracking-wider font-semibold">
              <span className="flex items-center gap-1.5 text-sky-400">
                <span>Search Sync: Adaptive Feedback Memory (N3-A)</span>
              </span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-bold ${
                trace.search_sync_feedback === "LIKE"
                  ? "bg-emerald-950 text-emerald-300 border border-emerald-700"
                  : trace.search_sync_feedback === "DISLIKE"
                  ? "bg-rose-950 text-rose-300 border border-rose-700"
                  : "bg-slate-900 text-slate-400 border border-slate-800"
              }`}>
                {trace.search_sync_feedback === "LIKE"
                  ? "👍 Preferred (+2.0000)"
                  : trace.search_sync_feedback === "DISLIKE"
                  ? "👎 Rejected (-4.0000)"
                  : "No Feedback (0.0000)"}
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
              <div className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60">
                <div className="text-neutral-500 text-[10px]">MAAE Base Score</div>
                <div className="text-neutral-200 font-semibold mt-0.5 font-mono">
                  {(trace.base_score ?? trace.final_score).toFixed(4)}
                </div>
              </div>
              <div className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60">
                <div className="text-neutral-500 text-[10px]">Search Sync Adjustment</div>
                <div className={`font-semibold mt-0.5 font-mono ${
                  (trace.search_sync_adjustment ?? 0) > 0
                    ? "text-emerald-400"
                    : (trace.search_sync_adjustment ?? 0) < 0
                    ? "text-rose-400"
                    : "text-neutral-400"
                }`}>
                  {(trace.search_sync_adjustment ?? 0) > 0 ? `+${(trace.search_sync_adjustment ?? 0).toFixed(4)}` : (trace.search_sync_adjustment ?? 0).toFixed(4)}
                </div>
              </div>
              <div className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60">
                <div className="text-neutral-500 text-[10px]">Final Ranking Score</div>
                <div className="text-amber-400 font-semibold mt-0.5 font-mono">
                  {trace.final_score.toFixed(4)}
                </div>
              </div>
            </div>
          </div>

          {/* Neural Shadow Bridge: PESE-Rel-0 Observer (Phase N3-B — Authority: NONE) */}
          <div className="p-3 bg-neutral-900/80 rounded border border-neutral-800 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <span className="flex items-center gap-1.5 text-purple-400 font-semibold">
                <span>Neural Shadow: PESE-Rel-0 Cross-Encoder Observer (N3-B)</span>
              </span>
              <div className="flex items-center gap-2">
                <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-purple-950/80 text-purple-300 border border-purple-800 font-mono">
                  Authority: NONE
                </span>
                {trace.rel_shadow_alignment && (
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded font-mono border ${
                    trace.rel_shadow_alignment.includes("DISLIKE") && trace.rel_shadow_alignment.includes("HIGH")
                      ? "bg-amber-950/80 text-amber-300 border-amber-700"
                      : trace.rel_shadow_alignment.includes("LIKE") && trace.rel_shadow_alignment.includes("HIGH")
                      ? "bg-emerald-950/80 text-emerald-300 border-emerald-700"
                      : "bg-neutral-900 text-neutral-400 border-neutral-700"
                  }`}>
                    {trace.rel_shadow_alignment}
                  </span>
                )}
              </div>
            </div>

            {trace.rel_shadow_answers_prob !== undefined && trace.rel_shadow_answers_prob !== null ? (
              <div className="space-y-2">
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 text-xs">
                  <div className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60">
                    <div className="text-neutral-500 text-[10px]">P(ANSWERS)</div>
                    <div className="text-emerald-400 font-semibold mt-0.5 font-mono text-sm">
                      {trace.rel_shadow_answers_prob.toFixed(4)}
                    </div>
                  </div>
                  <div className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60">
                    <div className="text-neutral-500 text-[10px]">P(DOES_NOT_ANSWER)</div>
                    <div className="text-neutral-400 font-semibold mt-0.5 font-mono text-sm">
                      {(trace.rel_shadow_does_not_answer_prob ?? (1.0 - trace.rel_shadow_answers_prob)).toFixed(4)}
                    </div>
                  </div>
                  <div className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60">
                    <div className="text-neutral-500 text-[10px]">Diagnostic Label</div>
                    <div className={`font-semibold mt-0.5 font-mono text-sm ${
                      trace.rel_shadow_label === "ANSWERS" ? "text-emerald-400" : "text-neutral-400"
                    }`}>
                      {trace.rel_shadow_label || "DOES_NOT_ANSWER"}
                    </div>
                  </div>
                  <div className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60">
                    <div className="text-neutral-500 text-[10px]">Evaluated Evidence</div>
                    <div className="text-neutral-300 font-mono text-xs mt-0.5 truncate" title={trace.rel_shadow_evidence_id || ""}>
                      {trace.rel_shadow_evidence_id || "None"}
                    </div>
                  </div>
                </div>

                {/* Probability Bar */}
                <div className="w-full h-1.5 bg-neutral-800 rounded-full overflow-hidden flex">
                  <div
                    className="bg-emerald-500 h-full transition-all duration-300"
                    style={{ width: `${Math.round(trace.rel_shadow_answers_prob * 100)}%` }}
                    title={`P(ANSWERS): ${(trace.rel_shadow_answers_prob * 100).toFixed(1)}%`}
                  />
                  <div
                    className="bg-neutral-600 h-full transition-all duration-300"
                    style={{ width: `${Math.round((1 - trace.rel_shadow_answers_prob) * 100)}%` }}
                    title={`P(DOES_NOT): ${((1 - trace.rel_shadow_answers_prob) * 100).toFixed(1)}%`}
                  />
                </div>
              </div>
            ) : (
              <div className="text-xs text-neutral-500 font-mono py-1">
                {trace.rel_shadow_status === "DISABLED"
                  ? "Neural shadow disabled via PESE_REL_SHADOW_ENABLED"
                  : "No neural shadow observation recorded for this candidate"}
              </div>
            )}

            <div className="text-[10px] text-neutral-500 italic pt-1 border-t border-neutral-800/60">
              Observation only: PESE-Rel-0 evaluates evidence candidates in shadow mode. Scores have strictly ZERO authority over ranking or answers.
            </div>
          </div>

          {/* Mathematical Signals Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Column 1: Lexical & Field Signals */}
            <div className="space-y-2 bg-neutral-900/60 p-3 rounded border border-neutral-800/80">
              <div className="font-semibold text-neutral-400 uppercase text-[10px] tracking-wider">
                Relevance Signals
              </div>
              <div className="flex justify-between">
                <span className="text-neutral-400">BM25F Lexical Total:</span>
                <span className="text-neutral-200 font-bold">{trace.bm25f_lexical.toFixed(4)}</span>
              </div>
              {/* Field breakdown */}
              <div className="pl-3 text-[11px] text-neutral-500 space-y-0.5 border-l border-neutral-800">
                <div className="flex justify-between">
                  <span>Title (w=3.5):</span>
                  <span>{trace.bm25f_breakdown.title.toFixed(4)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Headings (w=2.5):</span>
                  <span>{trace.bm25f_breakdown.headings.toFixed(4)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Keywords (w=2.8):</span>
                  <span>{trace.bm25f_breakdown.keywords.toFixed(4)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Meta (w=1.8):</span>
                  <span>{trace.bm25f_breakdown.meta_description.toFixed(4)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Body (w=1.0):</span>
                  <span>{trace.bm25f_breakdown.body.toFixed(4)}</span>
                </div>
              </div>

              <div className="flex justify-between pt-1 border-t border-neutral-800">
                <span className="text-neutral-400">Passage Relevance:</span>
                <span className="text-cyan-400 font-semibold">{trace.passage_signal.toFixed(4)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-neutral-400">Title Token Match:</span>
                <span>+{trace.title_signal.toFixed(4)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-neutral-400">Heading Token Match:</span>
                <span>+{trace.heading_signal.toFixed(4)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-neutral-400">Exact Phrase Match:</span>
                <span>+{trace.phrase_signal.toFixed(4)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-neutral-400">Query Coverage Gating:</span>
                <span className="text-amber-300">
                  {trace.coverage_factor.toFixed(4)} ({trace.matched_query_terms}/{trace.total_query_terms} terms)
                </span>
              </div>
            </div>

            {/* Column 2: Graph, Freshness, Quality & Spam */}
            <div className="space-y-2 bg-neutral-900/60 p-3 rounded border border-neutral-800/80">
              <div className="font-semibold text-neutral-400 uppercase text-[10px] tracking-wider">
                Graph, Freshness & Penalties
              </div>
              <div className="flex justify-between">
                <span className="text-neutral-400">Internal Link Authority:</span>
                <span className="text-purple-400 font-semibold">+{trace.link_authority.toFixed(4)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-neutral-400">Freshness Bonus:</span>
                <span className="text-emerald-400">+{trace.freshness_bonus.toFixed(4)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-neutral-400">Content Quality Score:</span>
                <span className="text-blue-400">+{trace.quality_bonus.toFixed(4)}</span>
              </div>

              {/* Spam Penalty Section */}
              <div className="pt-2 border-t border-neutral-800">
                <div className="flex justify-between items-center">
                  <span className="text-neutral-400 flex items-center gap-1">
                    {trace.spam_penalty > 0 ? (
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-500" />
                    ) : (
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                    )}
                    Spam Penalty:
                  </span>
                  <span
                    className={
                      trace.spam_penalty > 0
                        ? "text-rose-400 font-bold bg-rose-950/60 px-1.5 py-0.5 rounded border border-rose-800"
                        : "text-emerald-400"
                    }
                  >
                    -{Math.round(trace.spam_penalty * 100)}%
                  </span>
                </div>
                {trace.spam_reasons.length > 0 && (
                  <div className="mt-1.5 text-[11px] text-neutral-400 space-y-0.5">
                    {trace.spam_reasons.map((r, i) => (
                      <div key={i} className="text-neutral-400">
                        • {r}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Formula summary */}
              <div className="pt-2 border-t border-neutral-800 text-[11px] text-neutral-400">
                <div className="text-neutral-500 text-[10px]">Formula:</div>
                <div className="text-neutral-300">
                  ({trace.relevance_gated.toFixed(2)} + {trace.link_authority.toFixed(2)} +{" "}
                  {trace.freshness_bonus.toFixed(2)} + {trace.quality_bonus.toFixed(2)}) × (1 -{" "}
                  {trace.spam_penalty.toFixed(2)}) ={" "}
                  <strong className="text-amber-400">{trace.final_score.toFixed(4)}</strong>
                </div>
              </div>
            </div>
          </div>

          {/* Comparative Audit: Why did this defeat / lose to Result #X? */}
          <div className="pt-3 border-t border-neutral-800">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-neutral-400 font-medium flex items-center gap-1">
                <Scale className="w-3.5 h-3.5 text-amber-400" />
                Compare with another candidate:
              </span>
              <select
                value={compareSlug}
                onChange={(e) => handleCompare(e.target.value)}
                className="bg-neutral-900 border border-neutral-700 text-neutral-200 text-xs rounded px-2.5 py-1 focus:outline-none focus:ring-1 focus:ring-amber-400"
              >
                <option value="">Select a document to compare...</option>
                {allResults
                  .filter((r) => r.slug !== currentResult.slug)
                  .map((r) => (
                    <option key={r.slug} value={r.slug}>
                      #{r.rank} {r.title} (Score: {r.final_score.toFixed(2)})
                    </option>
                  ))}
              </select>
            </div>

            {comparingLoading && (
              <div className="mt-3 text-neutral-500 animate-pulse">Running comparative signal audit...</div>
            )}

            {comparison && (
              <div className="mt-3 p-3 bg-neutral-900 rounded border border-neutral-800 space-y-2">
                <div className="flex items-center gap-2 font-semibold text-neutral-200">
                  <span>{comparison.winner_title}</span>
                  <span className="text-emerald-400">({comparison.winner_score.toFixed(2)})</span>
                  <ArrowRight className="w-3.5 h-3.5 text-neutral-500" />
                  <span>{comparison.loser_title}</span>
                  <span className="text-rose-400">({comparison.loser_score.toFixed(2)})</span>
                  <span className="text-neutral-400 text-xs ml-auto">
                    Δ {comparison.score_difference.toFixed(4)}
                  </span>
                </div>

                <div className="space-y-1 text-xs text-neutral-300">
                  {comparison.decisive_factors.map((factor, idx) => (
                    <div key={idx} className="bg-neutral-950/60 p-2 rounded border border-neutral-800">
                      {factor}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
