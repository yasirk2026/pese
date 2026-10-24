"use client";

import React, { useState } from "react";
import { Compass, HelpCircle, Search, ChevronDown, ChevronRight, CheckCircle2, ShieldAlert } from "lucide-react";
import { RelatedSearchItem, PAAQuestionItem } from "@/lib/api";

interface DiscoveryAuditProps {
  relatedSearches: RelatedSearchItem[];
  paaQuestions: PAAQuestionItem[];
  query: string;
}

export const DiscoveryAudit: React.FC<DiscoveryAuditProps> = ({
  relatedSearches,
  paaQuestions,
  query,
}) => {
  const [activeTab, setActiveTab] = useState<"paa" | "related">("paa");

  return (
    <div className="mb-6 p-4 rounded-xl border border-purple-200 dark:border-purple-900/60 bg-purple-50/40 dark:bg-purple-950/20 font-mono text-xs">
      <div className="flex items-center justify-between pb-3 border-b border-purple-200/60 dark:border-purple-900/40">
        <div className="flex items-center gap-2 text-purple-950 dark:text-purple-200">
          <Compass className="w-4 h-4 text-purple-600 dark:text-purple-400" />
          <span className="font-bold font-sans text-sm">Discovery Intelligence Audit (Phase 2A)</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab("paa")}
            className={`px-2.5 py-1 rounded text-xs transition-colors ${
              activeTab === "paa"
                ? "bg-purple-600 text-white font-medium"
                : "text-purple-800 dark:text-purple-300 hover:bg-purple-100 dark:hover:bg-purple-900/40"
            }`}
          >
            PAA Gate Audit ({paaQuestions.length})
          </button>
          <button
            onClick={() => setActiveTab("related")}
            className={`px-2.5 py-1 rounded text-xs transition-colors ${
              activeTab === "related"
                ? "bg-purple-600 text-white font-medium"
                : "text-purple-800 dark:text-purple-300 hover:bg-purple-100 dark:hover:bg-purple-900/40"
            }`}
          >
            Related Searches Audit ({relatedSearches.length})
          </button>
        </div>
      </div>

      {/* PAA Answerability Gate Audit */}
      {activeTab === "paa" && (
        <div className="mt-3 space-y-3">
          <div className="text-[11px] text-purple-800 dark:text-purple-300 font-sans">
            Every candidate question is strictly gated through the real retrieval &amp; featured-answer pipeline.
            Zero hallucinated questions permitted.
          </div>

          {paaQuestions.length === 0 ? (
            <div className="p-3 rounded bg-white dark:bg-neutral-900 border border-purple-200 dark:border-purple-900/40 text-neutral-500">
              Zero PAA questions surfaced. System correctly suppressed speculative questions due to insufficient passage evidence.
            </div>
          ) : (
            <div className="space-y-2">
              {paaQuestions.map((q, idx) => (
                <div
                  key={`${q.question}-${idx}`}
                  className="p-3 rounded-lg bg-white dark:bg-neutral-900 border border-purple-200 dark:border-purple-900/40 space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-neutral-900 dark:text-neutral-100">
                      {q.question}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 font-bold text-[10px] flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" />
                      GATE: {q.answerability_status}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-neutral-600 dark:text-neutral-400 pt-1">
                    <div>
                      <span className="text-neutral-400">Source Doc:</span>{" "}
                      <span className="font-semibold text-neutral-800 dark:text-neutral-200">{q.source_slug}</span>
                    </div>
                    <div>
                      <span className="text-neutral-400">Passage Signal:</span>{" "}
                      <span className="font-semibold">{q.passage_score.toFixed(2)}</span>
                    </div>
                    <div>
                      <span className="text-neutral-400">Intent:</span>{" "}
                      <span className="font-semibold">{q.intent}</span>
                    </div>
                    <div>
                      <span className="text-neutral-400">Final PAA Score:</span>{" "}
                      <span className="font-semibold text-purple-700 dark:text-purple-300">{q.confidence_score.toFixed(2)}</span>
                    </div>
                  </div>

                  <div className="mt-1 text-[11px] text-neutral-700 dark:text-neutral-300 bg-neutral-50 dark:bg-neutral-800 p-2 rounded border border-neutral-200 dark:border-neutral-800">
                    <span className="text-neutral-400 font-sans block mb-0.5">Extracted Answer Verification:</span>
                    <span className="font-serif italic">&quot;{q.answer}&quot;</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Related Searches Audit */}
      {activeTab === "related" && (
        <div className="mt-3 space-y-3">
          <div className="text-[11px] text-purple-800 dark:text-purple-300 font-sans">
            Related search candidates scored by topic overlap, graph link affinity, and session reformulation patterns.
          </div>

          {relatedSearches.length === 0 ? (
            <div className="p-3 rounded bg-white dark:bg-neutral-900 border border-purple-200 dark:border-purple-900/40 text-neutral-500">
              Zero related searches surfaced. System avoided inventing nonsense candidates for low-evidence query.
            </div>
          ) : (
            <div className="space-y-2">
              {relatedSearches.map((r, idx) => (
                <div
                  key={`${r.query}-${idx}`}
                  className="p-3 rounded-lg bg-white dark:bg-neutral-900 border border-purple-200 dark:border-purple-900/40 space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-neutral-900 dark:text-neutral-100">
                      {r.query}
                    </span>
                    <span className="text-purple-700 dark:text-purple-300 font-bold">
                      Score: {r.score.toFixed(2)}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-neutral-600 dark:text-neutral-400">
                    <div>
                      <span className="text-neutral-400">Source:</span>{" "}
                      <span className="font-semibold">{r.source}</span>
                    </div>
                    <div>
                      <span className="text-neutral-400">Topic Overlap:</span>{" "}
                      <span className="font-semibold">+{r.co_occurrence_score.toFixed(2)}</span>
                    </div>
                    <div>
                      <span className="text-neutral-400">Link Affinity:</span>{" "}
                      <span className="font-semibold">+{r.link_affinity_score.toFixed(2)}</span>
                    </div>
                    <div>
                      <span className="text-neutral-400">Reformulation:</span>{" "}
                      <span className="font-semibold">+{String(r.debug_trace?.reformulation_score ?? 0)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
