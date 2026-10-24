"use client";

import React from "react";
import { Sparkles, Layers, Search, Cpu } from "lucide-react";
import { HybridTraceData } from "@/lib/api";

interface HybridRetrievalAuditProps {
  trace?: HybridTraceData;
  totalResults: number;
}

export const HybridRetrievalAudit: React.FC<HybridRetrievalAuditProps> = ({
  trace,
  totalResults,
}) => {
  if (!trace) return null;

  return (
    <div className="mb-4 p-4 rounded-xl border border-cyan-200 dark:border-cyan-900/60 bg-cyan-50/40 dark:bg-cyan-950/20 font-mono text-xs">
      <div className="flex items-center justify-between pb-2 border-b border-cyan-200/60 dark:border-cyan-900/40">
        <div className="flex items-center gap-2 text-cyan-950 dark:text-cyan-200">
          <Layers className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
          <span className="font-bold font-sans text-sm">Hybrid Retrieval & Candidate Fusion Audit (Phase 2B)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded bg-cyan-600/10 text-cyan-700 dark:text-cyan-300 border border-cyan-300 dark:border-cyan-800 text-[11px] font-semibold">
            mode: {trace.retrieval_mode}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mt-3">
        <div className="p-2.5 rounded-lg bg-white dark:bg-neutral-900/80 border border-cyan-200/70 dark:border-cyan-900/40">
          <div className="text-[10px] text-neutral-500 uppercase tracking-wider font-sans">BM25F Lexical</div>
          <div className="text-sm font-bold text-neutral-800 dark:text-neutral-200 mt-0.5">
            {trace.lexical_candidates_count} candidates
          </div>
        </div>

        <div className="p-2.5 rounded-lg bg-white dark:bg-neutral-900/80 border border-cyan-200/70 dark:border-cyan-900/40">
          <div className="text-[10px] text-neutral-500 uppercase tracking-wider font-sans">Dense Semantic</div>
          <div className="text-sm font-bold text-neutral-800 dark:text-neutral-200 mt-0.5">
            {trace.semantic_candidates_count} candidates
          </div>
        </div>

        <div className="p-2.5 rounded-lg bg-white dark:bg-neutral-900/80 border border-cyan-200/70 dark:border-cyan-900/40">
          <div className="text-[10px] text-neutral-500 uppercase tracking-wider font-sans">RRF Fused Pool</div>
          <div className="text-sm font-bold text-purple-700 dark:text-purple-300 mt-0.5">
            {trace.fused_candidates_count} pooled
          </div>
        </div>

        <div className="p-2.5 rounded-lg bg-white dark:bg-neutral-900/80 border border-cyan-200/70 dark:border-cyan-900/40">
          <div className="text-[10px] text-neutral-500 uppercase tracking-wider font-sans">Semantic Rescues</div>
          <div className="text-sm font-bold text-emerald-600 dark:text-emerald-400 mt-0.5 flex items-center gap-1">
            <Sparkles className="w-3.5 h-3.5" />
            {trace.semantic_rescues_count} rescued
          </div>
        </div>

        <div className="p-2.5 rounded-lg bg-white dark:bg-neutral-900/80 border border-cyan-200/70 dark:border-cyan-900/40">
          <div className="text-[10px] text-neutral-500 uppercase tracking-wider font-sans">Final SERP</div>
          <div className="text-sm font-bold text-amber-600 dark:text-amber-400 mt-0.5">
            {totalResults} ranked
          </div>
        </div>
      </div>

      {trace.rescued_slugs && trace.rescued_slugs.length > 0 && (
        <div className="mt-2.5 pt-2 border-t border-cyan-200/50 dark:border-cyan-900/40 text-[11px] text-neutral-600 dark:text-neutral-400 flex items-center gap-2">
          <span className="font-semibold text-emerald-600 dark:text-emerald-400">Rescued Documents:</span>
          <span>{trace.rescued_slugs.join(", ")}</span>
        </div>
      )}
    </div>
  );
};
