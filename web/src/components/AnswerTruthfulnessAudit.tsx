/**
 * PESE Developer Debug: Answer Truthfulness Audit Panel
 * Phase 2D.2 — Displays the Answer Relevance Gate decision for the top result.
 * Inspects entity alignment, predicate alignment, property alignment,
 * answer type compatibility, and the final entailment verdict.
 *
 * Debug-only. Never shown in normal search mode.
 */

"use client";

import React, { useState } from "react";
import { ShieldCheck, ShieldX, ShieldAlert, ChevronDown, ChevronRight } from "lucide-react";

export interface AnswerRelevanceData {
  verdict: "PASS" | "REJECT" | "ABSTAIN" | null;
  failure_class: string | null;
  score: number | null;
  entity_alignment: number | null;
  predicate_alignment: number | null;
  property_alignment: number | null;
  answer_type_alignment: number | null;
  semantic_support?: number | null;
  reason: string | null;
  negation_preserved?: boolean | null;
  interrogative_contract?: string | null;
  debug_lines?: string[] | null;
}

export interface QATraceWithRelevance {
  model?: string;
  query?: string;
  deterministic_answer?: string | null;
  shadow_answer?: string | null;
  is_answerable?: boolean;
  confidence?: number;
  agreement?: string;
  execution_ms?: number;
  answer_relevance?: AnswerRelevanceData | null;
}

interface Props {
  qaTrace: QATraceWithRelevance | null;
  topResult: {
    title: string;
    slug: string;
    featured_answer?: string | null;
    is_featured: boolean;
    trace: {
      answer_relevance_verdict?: "PASS" | "REJECT" | "ABSTAIN" | null;
      answer_relevance_failure?: string | null;
      answer_relevance_score?: number | null;
    };
  } | null;
  query: string;
}

function ScoreBar({ value, label }: { value: number | null; label: string }) {
  if (value === null || value === undefined) return null;
  const pct = Math.round(value * 100);
  const color =
    value >= 0.6
      ? "bg-emerald-500"
      : value >= 0.35
      ? "bg-amber-500"
      : "bg-rose-500";
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between items-center text-[11px] font-mono">
        <span className="text-slate-400">{label}</span>
        <span
          className={
            value >= 0.6
              ? "text-emerald-400"
              : value >= 0.35
              ? "text-amber-400"
              : "text-rose-400"
          }
        >
          {pct}%
        </span>
      </div>
      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function VerdictBadge({ verdict }: { verdict: string | null | undefined }) {
  if (!verdict)
    return (
      <span className="text-slate-500 text-[11px] font-mono">NOT EVALUATED</span>
    );
  if (verdict === "PASS")
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-emerald-950/60 border border-emerald-800 text-emerald-400">
        <ShieldCheck className="w-3.5 h-3.5" /> PASS
      </span>
    );
  if (verdict === "ABSTAIN")
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-amber-950/60 border border-amber-800 text-amber-400">
        <ShieldAlert className="w-3.5 h-3.5" /> ABSTAIN
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-rose-950/60 border border-rose-800 text-rose-400">
      <ShieldX className="w-3.5 h-3.5" /> REJECT
    </span>
  );
}

export function AnswerTruthfulnessAudit({ qaTrace, topResult, query }: Props) {
  const [expanded, setExpanded] = useState(false);

  // Pull relevance data from qa_trace.answer_relevance (preferred) or from trace fields
  const relevance: AnswerRelevanceData | null =
    qaTrace?.answer_relevance ??
    (topResult?.trace
      ? {
          verdict: topResult.trace.answer_relevance_verdict ?? null,
          failure_class: topResult.trace.answer_relevance_failure ?? null,
          score: topResult.trace.answer_relevance_score ?? null,
          entity_alignment: null,
          predicate_alignment: null,
          property_alignment: null,
          answer_type_alignment: null,
          reason: null,
        }
      : null);

  const verdict = relevance?.verdict ?? null;
  const hasFeatured = topResult?.is_featured && topResult?.featured_answer;

  // Determine overall truthfulness status
  let overallStatus: "safe" | "suppressed" | "unknown" = "unknown";
  if (verdict === "PASS" && hasFeatured) overallStatus = "safe";
  else if (verdict === "REJECT" || verdict === "ABSTAIN") overallStatus = "suppressed";
  else if (!hasFeatured) overallStatus = "suppressed"; // No answer was shown

  const headerBg =
    overallStatus === "safe"
      ? "bg-emerald-950/40 border-emerald-800/60"
      : overallStatus === "suppressed"
      ? "bg-rose-950/40 border-rose-800/60"
      : "bg-slate-900 border-slate-800";

  const headerLabel =
    overallStatus === "safe"
      ? "Answer Truthfulness: VERIFIED ✓"
      : overallStatus === "suppressed"
      ? "Answer Truthfulness: SUPPRESSED ✗"
      : "Answer Truthfulness: NOT EVALUATED";

  return (
    <div className={`rounded-xl border text-sm font-mono overflow-hidden ${headerBg}`}>
      {/* Header */}
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-colors text-left"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-3">
          {overallStatus === "safe" ? (
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
          ) : overallStatus === "suppressed" ? (
            <ShieldX className="w-4 h-4 text-rose-400 shrink-0" />
          ) : (
            <ShieldAlert className="w-4 h-4 text-slate-400 shrink-0" />
          )}
          <span
            className={`text-xs font-bold tracking-wider uppercase ${
              overallStatus === "safe"
                ? "text-emerald-400"
                : overallStatus === "suppressed"
                ? "text-rose-400"
                : "text-slate-400"
            }`}
          >
            {headerLabel}
          </span>
        </div>
        {expanded ? (
          <ChevronDown className="w-4 h-4 text-slate-400 shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-slate-400 shrink-0" />
        )}
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="px-4 pb-4 space-y-4 text-[12px]">
          {/* Section: Query + Document + Candidate */}
          <div className="grid grid-cols-1 gap-2 pt-2">
            <div>
              <span className="text-slate-500 uppercase tracking-wider text-[10px]">Query</span>
              <div className="text-slate-200 mt-0.5 font-sans text-sm italic">{query}</div>
            </div>
            {topResult && (
              <div>
                <span className="text-slate-500 uppercase tracking-wider text-[10px]">Top Document</span>
                <div className="text-slate-200 mt-0.5 font-sans">{topResult.title}</div>
              </div>
            )}
            {topResult?.featured_answer ? (
              <div>
                <span className="text-slate-500 uppercase tracking-wider text-[10px]">Featured Answer</span>
                <div className="text-slate-100 mt-0.5 font-sans font-semibold">
                  &ldquo;{topResult.featured_answer}&rdquo;
                </div>
              </div>
            ) : (
              <div>
                <span className="text-slate-500 uppercase tracking-wider text-[10px]">Featured Answer</span>
                <div className="text-slate-400 mt-0.5 italic">None — Suppressed or not found</div>
              </div>
            )}
          </div>

          {/* Section: Gate Decision */}
          <div className="border-t border-slate-800 pt-3 space-y-2">
            <div className="text-slate-500 uppercase tracking-wider text-[10px] mb-1">
              Answer Relevance Gate
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <span className="text-slate-400">Verdict:</span>
                <VerdictBadge verdict={verdict} />
              </div>
              {relevance?.interrogative_contract && (
                <div className="flex items-center gap-2">
                  <span className="text-slate-400">Contract:</span>
                  <span className="text-sky-400 font-bold text-[11px]">
                    {relevance.interrogative_contract}
                  </span>
                </div>
              )}
              {relevance?.score !== null && relevance?.score !== undefined && (
                <div className="flex items-center gap-2">
                  <span className="text-slate-400">Entailment Score:</span>
                  <span
                    className={
                      (relevance.score ?? 0) >= 0.38
                        ? "text-emerald-400"
                        : (relevance.score ?? 0) >= 0.18
                        ? "text-amber-400"
                        : "text-rose-400"
                    }
                  >
                    {relevance.score.toFixed(3)}
                  </span>
                </div>
              )}
            </div>

            {relevance?.failure_class && (
              <div className="flex items-center gap-2 mt-1">
                <span className="text-slate-400">Failure Class:</span>
                <span className="text-rose-300 font-bold">{relevance.failure_class}</span>
              </div>
            )}

            {relevance?.reason && (
              <div className="mt-1">
                <span className="text-slate-400">Reason: </span>
                <span className="text-slate-300 font-sans">{relevance.reason}</span>
              </div>
            )}
          </div>

          {/* Section: Component Scores */}
          {(relevance?.entity_alignment !== null ||
            relevance?.predicate_alignment !== null ||
            relevance?.property_alignment !== null ||
            relevance?.answer_type_alignment !== null) && (
            <div className="border-t border-slate-800 pt-3 space-y-2">
              <div className="text-slate-500 uppercase tracking-wider text-[10px] mb-2">
                Component Alignment Scores
              </div>
              <div className="space-y-2">
                <ScoreBar
                  value={relevance?.entity_alignment ?? null}
                  label="Entity Alignment"
                />
                <ScoreBar
                  value={relevance?.predicate_alignment ?? null}
                  label="Predicate Alignment"
                />
                <ScoreBar
                  value={relevance?.property_alignment ?? null}
                  label="Property / Attribute Alignment"
                />
                <ScoreBar
                  value={relevance?.answer_type_alignment ?? null}
                  label="Answer Type Compatibility"
                />
                {relevance?.semantic_support !== undefined &&
                  relevance?.semantic_support !== null && (
                    <ScoreBar
                      value={relevance.semantic_support}
                      label="Semantic Support"
                    />
                  )}
              </div>

              {relevance?.negation_preserved === false && (
                <div className="mt-2 flex items-center gap-2 text-rose-400 text-[11px]">
                  <ShieldX className="w-3.5 h-3.5 shrink-0" />
                  <span>⚠ Negation conflict: answer stripped negation from passage</span>
                </div>
              )}
            </div>
          )}

          {/* Section: Separation of Document vs Answer Score */}
          {topResult?.trace && (
            <div className="border-t border-slate-800 pt-3 space-y-1">
              <div className="text-slate-500 uppercase tracking-wider text-[10px] mb-1">
                Document vs Answer Separation
              </div>
              <div className="text-[11px] text-slate-300 leading-relaxed font-sans">
                A high document relevance score does NOT imply a valid answer.
                The Answer Relevance Gate evaluates them independently.
              </div>
              <div className="grid grid-cols-3 gap-2 mt-2 text-center">
                <div className="bg-slate-900 rounded p-2">
                  <div className="text-slate-500 text-[10px] uppercase mb-0.5">Doc Relevance</div>
                  <div className="text-amber-400 font-bold text-sm">
                    {topResult.trace?.answer_relevance_score !== undefined
                      ? "SEPARATED"
                      : "N/A"}
                  </div>
                </div>
                <div className="bg-slate-900 rounded p-2">
                  <div className="text-slate-500 text-[10px] uppercase mb-0.5">Answer Gate</div>
                  <div
                    className={`font-bold text-sm ${
                      verdict === "PASS"
                        ? "text-emerald-400"
                        : verdict === "ABSTAIN"
                        ? "text-amber-400"
                        : "text-rose-400"
                    }`}
                  >
                    {verdict ?? "N/A"}
                  </div>
                </div>
                <div className="bg-slate-900 rounded p-2">
                  <div className="text-slate-500 text-[10px] uppercase mb-0.5">Answer Shown</div>
                  <div
                    className={`font-bold text-sm ${
                      hasFeatured ? "text-emerald-400" : "text-slate-500"
                    }`}
                  >
                    {hasFeatured ? "YES" : "NO"}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Section: PESE-QA Shadow */}
          {qaTrace && (
            <div className="border-t border-slate-800 pt-3 space-y-1">
              <div className="text-slate-500 uppercase tracking-wider text-[10px] mb-1">
                PESE-QA-0 Shadow Mode
              </div>
              <div className="flex flex-wrap gap-x-6 gap-y-1 text-[11px]">
                <div>
                  <span className="text-slate-400">Shadow Answer: </span>
                  <span className="text-slate-200">
                    {qaTrace.shadow_answer ?? "abstained"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400">Is Answerable: </span>
                  <span
                    className={
                      qaTrace.is_answerable ? "text-emerald-400" : "text-slate-400"
                    }
                  >
                    {qaTrace.is_answerable ? "Yes" : "No"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400">Agreement: </span>
                  <span
                    className={
                      qaTrace.agreement === "YES"
                        ? "text-emerald-400"
                        : qaTrace.agreement === "BOTH_ABSTAIN"
                        ? "text-slate-400"
                        : "text-amber-400"
                    }
                  >
                    {qaTrace.agreement ?? "N/A"}
                  </span>
                </div>
                {qaTrace.confidence !== undefined && (
                  <div>
                    <span className="text-slate-400">Confidence: </span>
                    <span className="text-slate-200">{(qaTrace.confidence * 100).toFixed(1)}%</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Section: Debug Lines */}
          {relevance?.debug_lines && relevance.debug_lines.length > 0 && (
            <div className="border-t border-slate-800 pt-3">
              <div className="text-slate-500 uppercase tracking-wider text-[10px] mb-2">
                Gate Debug Trace
              </div>
              <div className="bg-slate-950 rounded p-2 text-[10px] text-slate-400 font-mono space-y-0.5 max-h-48 overflow-y-auto">
                {relevance.debug_lines.map((line, i) => (
                  <div key={i} className="leading-relaxed">
                    {line}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Principle Note */}
          <div className="border-t border-slate-800 pt-3 text-[10px] text-slate-500 font-sans italic leading-relaxed">
            PESE Phase 2D.2 — &quot;I know something about this subject&quot; ≠ &quot;I know the answer to this question.&quot;
            A missing snippet is preferable to an unrelated snippet.
          </div>
        </div>
      )}
    </div>
  );
}
