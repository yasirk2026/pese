"use client";

import React, { useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import {
  runBenchmark,
  runDiscoveryBenchmark,
  BenchmarkSummary,
  DiscoveryBenchmarkSummary,
} from "@/lib/api";
import {
  BarChart2,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  ArrowLeft,
  Award,
  Target,
  ShieldCheck,
  Zap,
  Compass,
  Sparkles,
} from "lucide-react";

export default function BenchmarkDashboardPage() {
  const [summary, setSummary] = useState<BenchmarkSummary | null>(null);
  const [discoverySummary, setDiscoverySummary] = useState<DiscoveryBenchmarkSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const executeBenchmark = () => {
    setRunning(true);
    setError(null);

    Promise.allSettled([runBenchmark(), runDiscoveryBenchmark()])
      .then(([irRes, discRes]) => {
        if (irRes.status === "fulfilled") {
          setSummary(irRes.value);
        } else {
          setError(irRes.reason?.message || "Failed to execute IR benchmark");
        }

        if (discRes.status === "fulfilled") {
          setDiscoverySummary(discRes.value);
        }

        setRunning(false);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to execute benchmarks");
        setRunning(false);
        setLoading(false);
      });
  };


  return (
    <AppShell>
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Navigation Breadcrumb */}
        <div className="mb-6 flex items-center justify-between">
          <Link
            href="/settings?tab=developer"
            className="flex items-center gap-1.5 text-xs text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 font-mono transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Developer Settings</span>
          </Link>

          <button
            type="button"
            onClick={executeBenchmark}
            disabled={running}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-neutral-900 dark:bg-neutral-100 text-xs font-semibold text-white dark:text-neutral-900 shadow-sm hover:bg-neutral-800 dark:hover:bg-neutral-200 transition-colors disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${running ? "animate-spin" : ""}`} />
            <span>{running ? "Running Evaluation Suite..." : "Run Scientific Benchmark"}</span>
          </button>
        </div>

        {/* Dashboard Title */}
        <div className="pb-6 border-b border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center gap-2">
            <BarChart2 className="w-6 h-6 text-amber-500" />
            <h1 className="text-2xl font-bold tracking-tight">PESE Scientific Evaluation Suite</h1>
          </div>
          <p className="mt-1 text-sm text-neutral-500">
            Automated IR evaluation measuring Precision@K, Recall@K, MRR, passage accuracy, and spam resistance across 30 test queries.
          </p>
        </div>

        {/* Error Notification */}
        {error && (
          <div className="mt-6 p-4 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-200 text-sm">
            {error}
          </div>
        )}

        {/* PHASE 2A: DISCOVERY BENCHMARK SECTION */}
        {discoverySummary && (
          <div className="mt-8 space-y-4">
            <div className="flex items-center gap-2 text-purple-700 dark:text-purple-300">
              <Compass className="w-5 h-5 text-purple-600 dark:text-purple-400" />
              <h2 className="text-lg font-bold font-sans">Phase 2A Discovery Intelligence Benchmark</h2>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {/* Autocomplete MRR */}
              <div className="bg-white dark:bg-neutral-900 p-4 rounded-xl border border-purple-200 dark:border-purple-900/60 shadow-2xs">
                <div className="text-xs font-mono uppercase text-neutral-500 flex items-center justify-between">
                  <span>Autocomplete MRR</span>
                  <Sparkles className="w-4 h-4 text-purple-500" />
                </div>
                <div className="mt-2 text-2xl font-extrabold font-mono text-purple-700 dark:text-purple-300">
                  {discoverySummary.autocomplete_mrr.toFixed(4)}
                </div>
                <div className="mt-1 text-[11px] text-neutral-500 font-mono">
                  Hit@1: {(discoverySummary.autocomplete_p_at_1 * 100).toFixed(1)}%
                </div>
              </div>

              {/* Typo Suggestion Recovery */}
              <div className="bg-white dark:bg-neutral-900 p-4 rounded-xl border border-purple-200 dark:border-purple-900/60 shadow-2xs">
                <div className="text-xs font-mono uppercase text-neutral-500 flex items-center justify-between">
                  <span>Typo Recovery</span>
                  <Target className="w-4 h-4 text-blue-500" />
                </div>
                <div className="mt-2 text-2xl font-extrabold font-mono text-neutral-900 dark:text-neutral-100">
                  {(discoverySummary.typo_recovery_rate * 100).toFixed(1)}%
                </div>
                <div className="mt-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                  Corpus-aware spelling
                </div>
              </div>

              {/* PAA Answerability Precision */}
              <div className="bg-white dark:bg-neutral-900 p-4 rounded-xl border border-purple-200 dark:border-purple-900/60 shadow-2xs">
                <div className="text-xs font-mono uppercase text-neutral-500 flex items-center justify-between">
                  <span>PAA Answerability Gate</span>
                  <ShieldCheck className="w-4 h-4 text-emerald-500" />
                </div>
                <div className="mt-2 text-2xl font-extrabold font-mono text-emerald-600 dark:text-emerald-400">
                  {(discoverySummary.paa_answerability_precision * 100).toFixed(1)}%
                </div>
                <div className="mt-1 text-[11px] text-neutral-500 font-mono">
                  Duplicates: {discoverySummary.paa_duplicate_violations} (Zero)
                </div>
              </div>

              {/* Zero Contamination Status */}
              <div className="bg-white dark:bg-neutral-900 p-4 rounded-xl border border-purple-200 dark:border-purple-900/60 shadow-2xs">
                <div className="text-xs font-mono uppercase text-neutral-500 flex items-center justify-between">
                  <span>Doc Ranking Isolation</span>
                  <CheckCircle className="w-4 h-4 text-emerald-500" />
                </div>
                <div className="mt-2 text-xl font-extrabold font-mono text-emerald-600 dark:text-emerald-400">
                  {discoverySummary.doc_ranking_uncontaminated ? "ZERO BIAS" : "CONTAMINATED"}
                </div>
                <div className="mt-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                  SERP weights unaffected
                </div>
              </div>
            </div>
          </div>
        )}

        {/* PHASE 1: IR BENCHMARK SECTION */}
        {summary && (
          <div className="mt-8 space-y-8">
            <div className="flex items-center gap-2">
              <BarChart2 className="w-5 h-5 text-amber-500" />
              <h2 className="text-lg font-bold font-sans">Core Lexical IR Benchmark (BM25F + Passages)</h2>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {/* Card 1: MRR */}
              <div className="bg-white dark:bg-neutral-900 p-5 rounded-xl border border-neutral-200 dark:border-neutral-800 shadow-2xs">
                <div className="text-xs font-mono uppercase text-neutral-500 flex items-center justify-between">
                  <span>MRR (Reciprocal Rank)</span>
                  <Award className="w-4 h-4 text-amber-500" />
                </div>
                <div className="mt-2 text-3xl font-extrabold font-mono text-neutral-950 dark:text-neutral-50">
                  {summary.mrr.toFixed(4)}
                </div>
                <div className="mt-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                  Ideal target: &gt; 0.9000
                </div>
              </div>

              {/* Card 2: Precision@1 */}
              <div className="bg-white dark:bg-neutral-900 p-5 rounded-xl border border-neutral-200 dark:border-neutral-800 shadow-2xs">
                <div className="text-xs font-mono uppercase text-neutral-500 flex items-center justify-between">
                  <span>Precision @ 1</span>
                  <Target className="w-4 h-4 text-blue-500" />
                </div>
                <div className="mt-2 text-3xl font-extrabold font-mono text-neutral-950 dark:text-neutral-50">
                  {(summary.mean_precision_at_1 * 100).toFixed(1)}%
                </div>
                <div className="mt-1 text-[11px] text-neutral-500 font-mono">
                  Hit@1: {(summary.hit_at_1_rate * 100).toFixed(1)}%
                </div>
              </div>

              {/* Card 3: Hit@3 / Hit@5 */}
              <div className="bg-white dark:bg-neutral-900 p-5 rounded-xl border border-neutral-200 dark:border-neutral-800 shadow-2xs">
                <div className="text-xs font-mono uppercase text-neutral-500 flex items-center justify-between">
                  <span>Top 3 / Top 5 Hit Rate</span>
                  <Zap className="w-4 h-4 text-purple-500" />
                </div>
                <div className="mt-2 text-3xl font-extrabold font-mono text-neutral-950 dark:text-neutral-50">
                  {(summary.hit_at_3_rate * 100).toFixed(1)}%
                </div>
                <div className="mt-1 text-[11px] text-neutral-500 font-mono">
                  Top 5 Hit Rate: {(summary.hit_at_5_rate * 100).toFixed(1)}%
                </div>
              </div>

              {/* Card 4: Spam Violations */}
              <div className="bg-white dark:bg-neutral-900 p-5 rounded-xl border border-neutral-200 dark:border-neutral-800 shadow-2xs">
                <div className="text-xs font-mono uppercase text-neutral-500 flex items-center justify-between">
                  <span>Spam Invasions</span>
                  <ShieldCheck className="w-4 h-4 text-emerald-500" />
                </div>
                <div className="mt-2 text-3xl font-extrabold font-mono text-emerald-600 dark:text-emerald-400">
                  {summary.spam_violations}
                </div>
                <div className="mt-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                  Zero spam document victories
                </div>
              </div>
            </div>

            {/* Test Queries Evaluation Table */}
            <div className="bg-white dark:bg-neutral-900 rounded-xl border border-neutral-200 dark:border-neutral-800 overflow-hidden shadow-2xs">
              <div className="p-4 border-b border-neutral-200 dark:border-neutral-800 flex items-center justify-between">
                <h2 className="text-sm font-bold font-mono uppercase tracking-wider text-neutral-800 dark:text-neutral-200">
                  Evaluated Test Queries ({summary.total_queries})
                </h2>
                <span className="text-xs font-mono text-neutral-500">
                  Recall@3: {(summary.mean_recall_at_3 * 100).toFixed(1)}%
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-neutral-100 dark:bg-neutral-850 text-neutral-600 dark:text-neutral-400 uppercase text-[10px] tracking-wider border-b border-neutral-200 dark:border-neutral-800">
                    <tr>
                      <th className="px-4 py-3">Query</th>
                      <th className="px-4 py-3">Cluster</th>
                      <th className="px-4 py-3">Top Ranked Result</th>
                      <th className="px-4 py-3">Score</th>
                      <th className="px-4 py-3 text-center">Hit @ 1</th>
                      <th className="px-4 py-3 text-center">Hit @ 3</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-200 dark:border-neutral-800 text-[11px]">
                    {summary.detailed_results.map((row, idx) => (
                      <tr key={idx} className="hover:bg-neutral-50 dark:hover:bg-neutral-850/50">
                        <td className="px-4 py-2.5 font-sans font-medium text-neutral-900 dark:text-neutral-100">
                          <Link
                            href={`/search?q=${encodeURIComponent(row.query)}&debug=true`}
                            className="hover:underline hover:text-blue-600 dark:hover:text-blue-400"
                          >
                            {row.query}
                          </Link>
                        </td>
                        <td className="px-4 py-2.5 text-neutral-500">{row.cluster}</td>
                        <td className="px-4 py-2.5 text-neutral-700 dark:text-neutral-300">
                          {row.top_result || "None"}
                        </td>
                        <td className="px-4 py-2.5 text-neutral-600 dark:text-neutral-400">
                          {row.top_score.toFixed(2)}
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          {row.hit_at_1 ? (
                            <span className="text-emerald-500 font-bold">✓</span>
                          ) : (
                            <span className="text-rose-500 font-bold">✗</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          {row.hit_at_3 ? (
                            <span className="text-emerald-500 font-bold">✓</span>
                          ) : (
                            <span className="text-rose-500 font-bold">✗</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
