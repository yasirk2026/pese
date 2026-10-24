"use client";

import React, { useState } from "react";
import { QueryAnalysisData, RejectedCandidate } from "@/lib/api";
import { HelpCircle, CheckCircle, XCircle, SpellCheck, Shield, ChevronDown, ChevronUp } from "lucide-react";

interface QueryAnalysisAuditProps {
  analysis?: QueryAnalysisData;
  rejectedCandidates?: RejectedCandidate[];
  forceRaw?: boolean;
}

export const QueryAnalysisAudit: React.FC<QueryAnalysisAuditProps> = ({
  analysis,
  rejectedCandidates = [],
  forceRaw = false,
}) => {
  const [showRejected, setShowRejected] = useState(false);

  if (!analysis) return null;

  const getIntentBadgeColor = (intent: string) => {
    switch (intent) {
      case "WHEN":
        return "bg-blue-900/60 text-blue-300 border-blue-700";
      case "WHAT":
        return "bg-purple-900/60 text-purple-300 border-purple-700";
      case "WHY":
        return "bg-amber-900/60 text-amber-300 border-amber-700";
      case "HOW":
        return "bg-emerald-900/60 text-emerald-300 border-emerald-700";
      case "WHO":
        return "bg-indigo-900/60 text-indigo-300 border-indigo-700";
      case "WHERE":
        return "bg-teal-900/60 text-teal-300 border-teal-700";
      default:
        return "bg-neutral-800 text-neutral-300 border-neutral-700";
    }
  };

  return (
    <div className="mb-6 p-4 rounded-xl bg-neutral-950 text-neutral-200 border border-neutral-800 font-mono text-xs space-y-4 shadow-xl">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-neutral-800">
        <div className="flex items-center gap-2">
          <span className="text-amber-400 font-bold">Query Analysis & Evidence Gate Audit</span>
          {forceRaw && (
            <span className="px-1.5 py-0.5 rounded bg-rose-950 border border-rose-800 text-rose-300 text-[10px]">
              force_raw: true
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-neutral-500">Intent:</span>
          <span
            className={`px-2 py-0.5 rounded border text-[11px] font-bold ${getIntentBadgeColor(
              analysis.intent
            )}`}
          >
            {analysis.intent}
          </span>
        </div>
      </div>

      {/* Grid of analysis columns */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Left column: Query Tokens Breakdown */}
        <div className="space-y-2 bg-neutral-900/50 p-3 rounded-lg border border-neutral-800">
          <div className="font-semibold text-neutral-400 text-[11px] uppercase tracking-wider flex items-center gap-1.5">
            <HelpCircle className="w-3.5 h-3.5 text-neutral-400" />
            Lexical Token Breakdown
          </div>

          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-neutral-500">Raw query:</span>
              <span className="text-neutral-200 font-bold">{analysis.original_query}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-500">Effective query:</span>
              <span className="text-emerald-400 font-bold">{analysis.effective_query}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-500">Intent reason:</span>
              <span className="text-neutral-300 italic">{analysis.intent_reason}</span>
            </div>
          </div>

          <div className="pt-2 border-t border-neutral-800 space-y-1.5">
            <div>
              <span className="text-neutral-500">Content terms: </span>
              {analysis.content_terms && analysis.content_terms.length > 0 ? (
                analysis.content_terms.map((t) => (
                  <span
                    key={t}
                    className="inline-block mr-1 px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-200 border border-neutral-700"
                  >
                    {t}
                  </span>
                ))
              ) : (
                <span className="text-neutral-600 italic">None</span>
              )}
            </div>

            <div>
              <span className="text-neutral-500">Intent terms: </span>
              {analysis.intent_terms && analysis.intent_terms.length > 0 ? (
                analysis.intent_terms.map((t) => (
                  <span
                    key={t}
                    className="inline-block mr-1 px-1.5 py-0.5 rounded bg-blue-950/70 text-blue-300 border border-blue-900"
                  >
                    {t}
                  </span>
                ))
              ) : (
                <span className="text-neutral-600 italic">None</span>
              )}
            </div>

            <div>
              <span className="text-neutral-500">Grammatical terms: </span>
              {analysis.grammatical_terms && analysis.grammatical_terms.length > 0 ? (
                analysis.grammatical_terms.map((t) => (
                  <span
                    key={t}
                    className="inline-block mr-1 px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-400"
                  >
                    {t}
                  </span>
                ))
              ) : (
                <span className="text-neutral-600 italic">None</span>
              )}
            </div>
          </div>
        </div>

        {/* Right column: Spelling Recovery & Typo Detection */}
        <div className="space-y-2 bg-neutral-900/50 p-3 rounded-lg border border-neutral-800">
          <div className="font-semibold text-neutral-400 text-[11px] uppercase tracking-wider flex items-center gap-1.5">
            <SpellCheck className="w-3.5 h-3.5 text-neutral-400" />
            Corpus Typo Recovery
          </div>

          {analysis.corrections && analysis.corrections.length > 0 ? (
            <div className="space-y-2">
              <div className="text-emerald-400 font-semibold">
                Applied {analysis.corrections.length} correction(s) (Confidence: {analysis.correction_confidence}):
              </div>
              {analysis.corrections.map((corr, idx) => (
                <div
                  key={idx}
                  className="p-2 rounded bg-neutral-950 border border-neutral-800 space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span>
                      <span className="text-rose-400 line-through">{corr.original_token}</span>
                      <span className="text-neutral-500 mx-1.5">&rarr;</span>
                      <span className="text-emerald-400 font-bold">{corr.corrected_token}</span>
                    </span>
                    <span className="text-neutral-400 font-semibold">
                      {(corr.confidence * 100).toFixed(1)}% conf
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-neutral-500">
                    <span>Distance: {corr.edit_distance}</span>
                    <span>•</span>
                    <span>Edit: {corr.edit_type}</span>
                    <span>•</span>
                    <span>Corpus Freq: {corr.corpus_frequency}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-4 text-center text-neutral-500 italic">
              No typos detected. All content terms are recognized in corpus dictionary or conservatively preserved.
            </div>
          )}
        </div>
      </div>

      {/* Minimum Evidence Gate Summary Bar */}
      <div className="pt-2 border-t border-neutral-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-amber-400" />
            <span className="font-semibold text-neutral-300">Minimum Evidence Gate:</span>
            <span className="text-neutral-400">
              Suppressed {rejectedCandidates.length} weak/ungrounded candidate(s)
            </span>
          </div>

          {rejectedCandidates.length > 0 && (
            <button
              type="button"
              onClick={() => setShowRejected(!showRejected)}
              className="inline-flex items-center gap-1 text-amber-400 hover:text-amber-300 transition-colors"
            >
              <span>{showRejected ? "Hide Rejected Candidates" : "Inspect Rejected Candidates"}</span>
              {showRejected ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          )}
        </div>

        {/* Expandable Rejected Candidates Table */}
        {showRejected && rejectedCandidates.length > 0 && (
          <div className="mt-3 space-y-2">
            {rejectedCandidates.map((cand, idx) => (
              <div
                key={idx}
                className="p-2.5 rounded bg-rose-950/20 border border-rose-900/60 flex flex-col gap-1 text-[11px]"
              >
                <div className="flex items-center justify-between text-rose-300 font-semibold">
                  <span>{cand.title}</span>
                  <span className="text-rose-400/80 font-mono text-[10px]">REJECTED</span>
                </div>
                <div className="text-neutral-400 text-[10px]">
                  Reason: <span className="text-neutral-300">{cand.reason}</span>
                </div>
                {cand.matched_content_terms && cand.matched_content_terms.length > 0 && (
                  <div className="text-neutral-500 text-[10px]">
                    Matched terms: {cand.matched_content_terms.join(", ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
