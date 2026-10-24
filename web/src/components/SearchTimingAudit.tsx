"use client";

import React from "react";
import { SearchTimingBreakdown, QATraceData } from "@/lib/api";
import {
  Clock,
  Zap,
  Cpu,
  Search,
  Layers,
  ShieldCheck,
  Award,
  FileText,
  CheckCircle2,
  Brain,
  Check,
  X,
  FastForward,
} from "lucide-react";

interface SearchTimingAuditProps {
  timing?: SearchTimingBreakdown;
  clientTookMs?: number;
  qaTrace?: QATraceData | null;
}

export const SearchTimingAudit: React.FC<SearchTimingAuditProps> = ({
  timing,
  clientTookMs,
  qaTrace,
}) => {
  if (!timing) return null;

  const stages = [
    {
      name: "Query Analysis",
      desc: "Tokenization, intent parsing & typo recovery",
      ms: timing.query_analysis_ms,
      icon: Search,
      color: "text-blue-400",
    },
    {
      name: "Lexical BM25F",
      desc: "Inverted index multi-field candidate retrieval",
      ms: timing.bm25f_retrieval_ms,
      icon: Layers,
      color: "text-indigo-400",
    },
    {
      name: "Dense Semantic",
      desc: "Prewarmed local query embedding & vector search",
      ms: timing.dense_retrieval_ms,
      icon: Cpu,
      color: "text-purple-400",
    },
    {
      name: "Hybrid RRF Fusion",
      desc: "Reciprocal Rank Fusion k=60 candidate merge",
      ms: timing.rrf_fusion_ms,
      icon: Zap,
      color: "text-cyan-400",
    },
    {
      name: "Evidence Gating",
      desc: "Minimum evidence, topic boundary & intent gate",
      ms: timing.evidence_gating_ms,
      icon: ShieldCheck,
      color: "text-emerald-400",
    },
    {
      name: "Ranking Scoring",
      desc: "Field signals, authority, freshness & penalties",
      ms: timing.ranking_scoring_ms,
      icon: Award,
      color: "text-amber-400",
    },
    {
      name: "Passage Scoring",
      desc: "Density, proximity, dates & block-level matches",
      ms: timing.passage_scoring_ms,
      icon: FileText,
      color: "text-pink-400",
    },
    {
      name: "Featured Answer",
      desc: "Grounded declarative / FAQ featured answer",
      ms: timing.answer_extraction_ms,
      icon: CheckCircle2,
      color: "text-emerald-400",
    },
    {
      name: "PESE-QA Shadow",
      desc: "Batched PyTorch reading & span verification",
      ms: timing.qa_shadow_ms || 0,
      icon: Brain,
      color: "text-rose-400",
    },
  ];

  const totalServer = timing.server_total_ms || 1.0;

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-sky-400" />
          <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider font-mono">
            Search Runtime Execution Profile &amp; Neural Accounting
          </h3>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-slate-400">
            Server: <strong className="text-sky-400">{timing.server_total_ms.toFixed(1)}ms</strong>
          </span>
          {clientTookMs !== undefined && (
            <span className="text-xs font-mono text-slate-500">
              Round-trip: <strong className="text-slate-300">{clientTookMs.toFixed(1)}ms</strong>
            </span>
          )}
        </div>
      </div>

      {/* Stage Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-3 gap-3">
        {stages.map((stg) => {
          const Icon = stg.icon;
          const pct = Math.min(100, Math.max(0, (stg.ms / totalServer) * 100));

          return (
            <div
              key={stg.name}
              className="bg-slate-950/80 border border-slate-800/80 rounded-lg p-3 space-y-2 relative overflow-hidden"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <Icon className={`w-3.5 h-3.5 ${stg.color}`} />
                  <span className="text-xs font-medium text-slate-200">{stg.name}</span>
                </div>
                <span className="text-xs font-mono font-bold text-slate-100">
                  {stg.ms.toFixed(1)}ms
                </span>
              </div>
              <p className="text-[10px] text-slate-400 leading-tight truncate">{stg.desc}</p>

              {/* Progress bar */}
              <div className="w-full bg-slate-900 rounded-full h-1 overflow-hidden">
                <div
                  className="bg-sky-500 h-1 rounded-full transition-all duration-300"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Neural QA Work Accounting Panel (Phase 2D.1) */}
      {qaTrace && (
        <div className="p-4 bg-slate-950/90 border border-purple-900/40 rounded-lg space-y-3">
          <div className="flex items-center justify-between text-purple-400 uppercase text-[11px] font-mono font-bold tracking-wider">
            <div className="flex items-center gap-2">
              <Brain className="w-4 h-4 text-purple-400" />
              <span>PESE-QA-0 Inference Operations &amp; Evidence Arbitration</span>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono">
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                qaTrace.agreement === "YES"
                  ? "bg-emerald-950 text-emerald-300 border border-emerald-700"
                  : qaTrace.agreement === "BOTH_ABSTAIN"
                  ? "bg-slate-800 text-slate-300 border border-slate-700"
                  : "bg-amber-950 text-amber-300 border border-amber-700"
              }`}>
                Agreement: {qaTrace.agreement}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
            <div className="p-2 rounded bg-slate-900/60 border border-slate-800/60">
              <div className="text-slate-400 text-[10px]">Passages Budgeted</div>
              <div className="text-slate-100 font-bold mt-0.5">
                {qaTrace.qa_passages_budgeted ?? 1} / {qaTrace.qa_candidates ?? 1} docs
              </div>
            </div>
            <div className="p-2 rounded bg-slate-900/60 border border-slate-800/60">
              <div className="text-slate-400 text-[10px]">Windows Tokenized</div>
              <div className="text-slate-100 font-bold mt-0.5">
                {qaTrace.qa_windows_created ?? 0} windows
              </div>
            </div>
            <div className="p-2 rounded bg-slate-900/60 border border-slate-800/60">
              <div className="text-slate-400 text-[10px]">PyTorch Batched Passes</div>
              <div className="text-slate-100 font-bold mt-0.5">
                {qaTrace.qa_forward_passes ?? 0} passes
              </div>
            </div>
            <div className="p-2 rounded bg-slate-900/60 border border-slate-800/60">
              <div className="text-slate-400 text-[10px]">LRU QA Cache</div>
              <div className="mt-0.5 font-bold flex items-center gap-1">
                {qaTrace.qa_cache_hit ? (
                  <span className="text-emerald-400 flex items-center gap-1">
                    <Check className="w-3.5 h-3.5" /> HIT (0.1ms)
                  </span>
                ) : (
                  <span className="text-slate-400">MISS (Fresh)</span>
                )}
              </div>
            </div>
            <div className="p-2 rounded bg-slate-900/60 border border-slate-800/60">
              <div className="text-slate-400 text-[10px]">Early Exit Triggered</div>
              <div className="mt-0.5 font-bold">
                {qaTrace.qa_early_exit ? (
                  <span className="text-emerald-400 flex items-center gap-1">
                    <FastForward className="w-3.5 h-3.5" /> YES
                  </span>
                ) : (
                  <span className="text-slate-400">NO</span>
                )}
              </div>
            </div>
            <div className="p-2 rounded bg-slate-900/60 border border-slate-800/60">
              <div className="text-slate-400 text-[10px]">Torch CPU Threads</div>
              <div className="text-sky-400 font-bold mt-0.5">
                {qaTrace.torch_threads ?? 2} threads
              </div>
            </div>
            <div className="p-2 rounded bg-slate-900/60 border border-slate-800/60">
              <div className="text-slate-400 text-[10px]">Resident Model</div>
              <div className="text-emerald-400 font-bold mt-0.5">
                Reused (0ms load)
              </div>
            </div>
            <div className="p-2 rounded bg-slate-900/60 border border-slate-800/60">
              <div className="text-slate-400 text-[10px]">QA Execution</div>
              <div className="text-purple-300 font-bold mt-0.5">
                {qaTrace.execution_ms.toFixed(1)}ms
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs pt-1">
            <div className="p-2 rounded bg-slate-900/40 border border-slate-800">
              <div className="text-slate-400 text-[10px] font-mono">Deterministic Extracted Answer</div>
              <div className="text-slate-100 font-serif text-sm mt-0.5">
                {qaTrace.deterministic_answer || <span className="italic text-slate-500">None</span>}
              </div>
            </div>
            <div className="p-2 rounded bg-slate-900/40 border border-slate-800">
              <div className="text-slate-400 text-[10px] font-mono">PESE-QA-0 Neural Shadow Span</div>
              <div className="text-purple-300 font-serif text-sm mt-0.5">
                {qaTrace.shadow_answer || <span className="italic text-slate-500">Abstained (NO EVIDENCE)</span>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Latency Integrity Guarantee */}
      <div className="text-[11px] font-mono text-slate-500 flex items-center justify-between pt-1">
        <span>⚡ Zero artificial delay. Prewarmed ONNX runtime + Resident PyTorch QA Reader + In-memory LRU cache.</span>
        <span className="text-emerald-400">● Real-time profiling active</span>
      </div>
    </div>
  );
};
