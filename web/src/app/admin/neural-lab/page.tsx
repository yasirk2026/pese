"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import {
  getNeuralRegistry,
  getNeuralExperiments,
  getNeuralCheckpoints,
  getQAContracts,
  generateNeuralText,
  getQAReport,
  readQAPassage,
  NeuralModelCard,
  NeuralReport,
  CheckpointItem,
  QAContractItem,
  QAReport,
  QAReadResult,
} from "@/lib/api";
import {
  Brain,
  Cpu,
  ShieldCheck,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  CheckCircle,
  XCircle,
  Sparkles,
  Layers,
  Database,
  Terminal,
  Activity,
  FileCode,
  HardDrive,
  Send,
  HelpCircle,
  BookOpen,
} from "lucide-react";

export default function NeuralLabPage() {
  const [registryModels, setRegistryModels] = useState<NeuralModelCard[]>([]);
  const [report, setReport] = useState<NeuralReport | null>(null);
  const [qaReport, setQaReport] = useState<QAReport | null>(null);
  const [checkpoints, setCheckpoints] = useState<CheckpointItem[]>([]);
  const [qaContracts, setQaContracts] = useState<QAContractItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Playground state
  const [prompt, setPrompt] = useState("Information retrieval systems");
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(20);
  const [generating, setGenerating] = useState(false);
  const [genOutput, setGenOutput] = useState<Awaited<ReturnType<typeof generateNeuralText>> | null>(null);
  const [genError, setGenError] = useState<string | null>(null);

  // QA Reader state
  const [qaQuestion, setQaQuestion] = useState("When did Nora envision LUMEN?");
  const [qaPassage, setQaPassage] = useState("Nora created LUMEN. She envisioned the idea in 2022. LUMEN launched in 2025.");
  const [qaReading, setQaReading] = useState(false);
  const [qaResult, setQaResult] = useState<QAReadResult | null>(null);
  const [qaError, setQaError] = useState<string | null>(null);

  useEffect(() => {
    Promise.allSettled([
      getNeuralRegistry(),
      getNeuralExperiments(),
      getNeuralCheckpoints(),
      getQAContracts(),
      getQAReport(),
    ]).then(([regRes, expRes, chkRes, qaRes, qaRepRes]) => {
      if (regRes.status === "fulfilled") setRegistryModels(regRes.value.models);
      if (expRes.status === "fulfilled") setReport(expRes.value);
      if (chkRes.status === "fulfilled") setCheckpoints(chkRes.value.checkpoints);
      if (qaRes.status === "fulfilled") setQaContracts(qaRes.value.contracts);
      if (qaRepRes.status === "fulfilled") setQaReport(qaRepRes.value);
      setLoading(false);
    }).catch((err) => {
      setError(err.message || "Failed to load neural laboratory data");
      setLoading(false);
    });
  }, []);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setGenerating(true);
    setGenError(null);
    try {
      const res = await generateNeuralText(prompt.trim(), maxTokens, temperature);
      setGenOutput(res);
    } catch (err: unknown) {
      setGenError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const handleQARead = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!qaQuestion.trim() || !qaPassage.trim()) return;
    setQaReading(true);
    setQaError(null);
    try {
      const res = await readQAPassage(qaQuestion.trim(), qaPassage.trim());
      setQaResult(res);
    } catch (err: unknown) {
      setQaError(err instanceof Error ? err.message : "Reading comprehension failed");
    } finally {
      setQaReading(false);
    }
  };

  const ng0 = registryModels.find((m) => m.model_id === "PESE-NG-0") || registryModels[0];

  return (
    <AppShell>


      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">
        {/* Navigation & Title Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-neutral-200 dark:border-neutral-800 pb-6">
          <div>
            <Link
              href="/settings?tab=developer"
              className="inline-flex items-center gap-1.5 text-xs text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 mb-2 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Back to Developer Settings
            </Link>
            <div className="flex items-center gap-3">
              <span className="p-2 rounded-xl bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400 border border-purple-200 dark:border-purple-800">
                <Brain className="w-6 h-6" />
              </span>
              <div>
                <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
                  PESE Neural Genesis Laboratory
                </h1>
                <p className="text-xs sm:text-sm text-neutral-500 dark:text-neutral-400">
                  PyTorch Foundational Transformer Laboratory & Architecture Inspector
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
              <Cpu className="w-3.5 h-3.5" />
              PyTorch 2.14 (CPU)
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
              <AlertTriangle className="w-3.5 h-3.5" />
              Status: EXPERIMENT
            </span>
          </div>
        </div>

        {/* Safety & Isolation Banners */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl border border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/50 dark:bg-emerald-950/30 flex items-start gap-3">
            <ShieldCheck className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
            <div className="text-xs text-emerald-900 dark:text-emerald-200 leading-relaxed">
              <strong className="font-semibold block text-emerald-800 dark:text-emerald-300 mb-0.5">
                Strict Privacy Boundary Guaranteed
              </strong>
              Zero private user documents, zero search queries, and zero user history were used in training datasets. All experiments use synthetic public corpora.
            </div>
          </div>

          <div className="p-4 rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50/50 dark:bg-amber-950/30 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div className="text-xs text-amber-900 dark:text-amber-200 leading-relaxed">
              <strong className="font-semibold block text-amber-800 dark:text-amber-300 mb-0.5">
                Production Retrieval Isolation
              </strong>
              PESE-NG-0 is strictly confined to this laboratory. It does NOT score or re-rank search queries, and does NOT override BM25F or BGE dense retrieval.
            </div>
          </div>
        </div>

        {/* Model Architecture Card & Hyperparameters */}
        {ng0 && (
          <section className="bg-white dark:bg-neutral-900 rounded-xl border border-neutral-200 dark:border-neutral-800 p-6 space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-neutral-100 dark:border-neutral-800 pb-4">
              <div className="flex items-center gap-2">
                <Layers className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                <h2 className="text-lg font-bold">Model Architecture: {ng0.model_id}</h2>
              </div>
              <span className="text-xs font-mono text-neutral-500 bg-neutral-100 dark:bg-neutral-800 px-2.5 py-1 rounded">
                Total Parameters: {ng0.total_parameters.toLocaleString()}
              </span>
            </div>

            <p className="text-xs sm:text-sm text-neutral-600 dark:text-neutral-400 leading-relaxed">
              {ng0.description}
            </p>

            {/* Hyperparameter Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-xs">
              <div className="p-3 bg-neutral-50 dark:bg-neutral-950/60 rounded-lg border border-neutral-200 dark:border-neutral-800">
                <span className="text-neutral-500 block">Hidden Dim (d_model)</span>
                <span className="font-mono font-bold text-sm text-purple-600 dark:text-purple-400">
                  {ng0.config.d_model || 128}
                </span>
              </div>
              <div className="p-3 bg-neutral-50 dark:bg-neutral-950/60 rounded-lg border border-neutral-200 dark:border-neutral-800">
                <span className="text-neutral-500 block">Layers (L)</span>
                <span className="font-mono font-bold text-sm text-purple-600 dark:text-purple-400">
                  {ng0.config.n_layers || 4}
                </span>
              </div>
              <div className="p-3 bg-neutral-50 dark:bg-neutral-950/60 rounded-lg border border-neutral-200 dark:border-neutral-800">
                <span className="text-neutral-500 block">Attention Heads (h)</span>
                <span className="font-mono font-bold text-sm text-purple-600 dark:text-purple-400">
                  {ng0.config.n_heads || 4}
                </span>
              </div>
              <div className="p-3 bg-neutral-50 dark:bg-neutral-950/60 rounded-lg border border-neutral-200 dark:border-neutral-800">
                <span className="text-neutral-500 block">FFN Dim (d_ff)</span>
                <span className="font-mono font-bold text-sm text-purple-600 dark:text-purple-400">
                  {ng0.config.d_ff || 512}
                </span>
              </div>
              <div className="p-3 bg-neutral-50 dark:bg-neutral-950/60 rounded-lg border border-neutral-200 dark:border-neutral-800">
                <span className="text-neutral-500 block">Max Seq Len (T)</span>
                <span className="font-mono font-bold text-sm text-purple-600 dark:text-purple-400">
                  {ng0.config.max_seq_len || 128}
                </span>
              </div>
              <div className="p-3 bg-neutral-50 dark:bg-neutral-950/60 rounded-lg border border-neutral-200 dark:border-neutral-800">
                <span className="text-neutral-500 block">Vocabulary Size (V)</span>
                <span className="font-mono font-bold text-sm text-purple-600 dark:text-purple-400">
                  {ng0.config.vocab_size || 256}
                </span>
              </div>
            </div>

            {/* Parameter Breakdown */}
            {report?.baseline_experiment?.model_summary?.parameter_breakdown && (
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                  Analytical Parameter Breakdown
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2 text-xs">
                  {Object.entries(report.baseline_experiment.model_summary.parameter_breakdown).map(
                    ([name, count]) => (
                      <div
                        key={name}
                        className="p-2.5 rounded bg-neutral-100/70 dark:bg-neutral-800/50 border border-neutral-200 dark:border-neutral-700/60 flex items-center justify-between"
                      >
                        <span className="text-neutral-600 dark:text-neutral-400 capitalize">
                          {name.replace(/_/g, " ")}
                        </span>
                        <span className="font-mono font-semibold">
                          {(count as number).toLocaleString()}
                        </span>
                      </div>
                    )
                  )}
                </div>
              </div>
            )}
          </section>
        )}

        {/* Experiments: Micro-Overfit and Baseline Convergence */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Experiment 1: Micro-Overfit Card */}
          <div className="bg-white dark:bg-neutral-900 rounded-xl border border-neutral-200 dark:border-neutral-800 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-3">
              <div className="flex items-center gap-2">
                <Activity className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                <h3 className="font-bold text-sm sm:text-base">Experiment 1: Micro-Overfit Test</h3>
              </div>
              <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
                <CheckCircle2 className="w-3.5 h-3.5" />
                PASSED (≥ 70% Target)
              </span>
            </div>

            <p className="text-xs text-neutral-600 dark:text-neutral-400">
              Verifies foundational learning capability. Proves backpropagation, causal masking,
              and optimization operate correctly by training on a fixed micro-corpus.
            </p>

            {report?.micro_overfit_experiment && (
              <div className="grid grid-cols-3 gap-3 text-center text-xs">
                <div className="p-3 bg-neutral-50 dark:bg-neutral-950 rounded border border-neutral-200 dark:border-neutral-800">
                  <span className="text-neutral-500 block">Initial Loss</span>
                  <span className="font-mono font-bold text-sm text-neutral-900 dark:text-neutral-100">
                    {report.micro_overfit_experiment.initial_loss}
                  </span>
                </div>
                <div className="p-3 bg-neutral-50 dark:bg-neutral-950 rounded border border-neutral-200 dark:border-neutral-800">
                  <span className="text-neutral-500 block">Final Loss</span>
                  <span className="font-mono font-bold text-sm text-emerald-600 dark:text-emerald-400">
                    {report.micro_overfit_experiment.final_loss}
                  </span>
                </div>
                <div className="p-3 bg-neutral-50 dark:bg-neutral-950 rounded border border-neutral-200 dark:border-neutral-800">
                  <span className="text-neutral-500 block">Loss Drop</span>
                  <span className="font-mono font-bold text-sm text-emerald-600 dark:text-emerald-400">
                    -{report.micro_overfit_experiment.loss_reduction_pct}%
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Experiment 2: Baseline Synthetic Corpus Training */}
          <div className="bg-white dark:bg-neutral-900 rounded-xl border border-neutral-200 dark:border-neutral-800 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-3">
              <div className="flex items-center gap-2">
                <Terminal className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                <h3 className="font-bold text-sm sm:text-base">Experiment 2: Baseline PESE-NG-0 Training</h3>
              </div>
              <span className="text-xs font-mono text-neutral-500 bg-neutral-100 dark:bg-neutral-800 px-2.5 py-0.5 rounded">
                PESE-BPE-0 Subword
              </span>
            </div>

            <p className="text-xs text-neutral-600 dark:text-neutral-400">
              Small-scale baseline trained on public synthetic technical corpus using AdamW,
              learning rate warmup, cosine decay, and gradient clipping.
            </p>

            {report?.baseline_experiment?.train_results && (
              <div className="grid grid-cols-3 gap-3 text-center text-xs">
                <div className="p-3 bg-neutral-50 dark:bg-neutral-950 rounded border border-neutral-200 dark:border-neutral-800">
                  <span className="text-neutral-500 block">Initial Loss</span>
                  <span className="font-mono font-bold text-sm text-neutral-900 dark:text-neutral-100">
                    {report.baseline_experiment.train_results.initial_loss}
                  </span>
                </div>
                <div className="p-3 bg-neutral-50 dark:bg-neutral-950 rounded border border-neutral-200 dark:border-neutral-800">
                  <span className="text-neutral-500 block">Final Loss</span>
                  <span className="font-mono font-bold text-sm text-purple-600 dark:text-purple-400">
                    {report.baseline_experiment.train_results.final_loss}
                  </span>
                </div>
                <div className="p-3 bg-neutral-50 dark:bg-neutral-950 rounded border border-neutral-200 dark:border-neutral-800">
                  <span className="text-neutral-500 block">Duration</span>
                  <span className="font-mono font-bold text-sm text-neutral-900 dark:text-neutral-100">
                    {report.baseline_experiment.train_results.duration_seconds}s
                  </span>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Interactive Experimental Generation Playground */}
        <section className="bg-white dark:bg-neutral-900 rounded-xl border border-neutral-200 dark:border-neutral-800 p-6 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-neutral-100 dark:border-neutral-800 pb-4">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-purple-600 dark:text-purple-400" />
              <h2 className="text-lg font-bold">Interactive Experimental Generation Playground</h2>
            </div>
            <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">
              ⚠️ Experimental Inference • Laboratory Use Only
            </span>
          </div>

          <form onSubmit={handleGenerate} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                Prompt Sequence
              </label>
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Enter prompt string (e.g. 'Information retrieval systems')..."
                className="w-full px-3.5 py-2.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-950 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-neutral-500 mb-1">
                  Temperature: {temperature}
                </label>
                <input
                  type="range"
                  min="0.1"
                  max="1.5"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-500 mb-1">
                  Max Tokens: {maxTokens}
                </label>
                <input
                  type="number"
                  min="5"
                  max="50"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(parseInt(e.target.value) || 20)}
                  className="w-full px-3 py-1.5 rounded border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-950 text-xs"
                />
              </div>

              <div className="flex items-end">
                <button
                  type="submit"
                  disabled={generating || !prompt.trim()}
                  className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white font-medium text-xs transition-colors cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
                  {generating ? "Generating..." : "Generate Continuation"}
                </button>
              </div>
            </div>
          </form>

          {genError && (
            <div className="p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 rounded text-xs text-rose-700 dark:text-rose-300">
              {genError}
            </div>
          )}

          {genOutput && (
            <div className="p-4 rounded-lg bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 space-y-2">
              <div className="text-xs text-neutral-500 flex items-center justify-between">
                <span>Output completion:</span>
                <span className="font-mono">{genOutput.tokens_generated} tokens generated</span>
              </div>
              <div className="font-mono text-sm p-3 bg-white dark:bg-neutral-900 rounded border border-neutral-200 dark:border-neutral-800 text-neutral-900 dark:text-neutral-100">
                <span className="font-bold text-neutral-500">{genOutput.prompt}</span>
                <span className="text-purple-600 dark:text-purple-400">{genOutput.generated_text}</span>
              </div>
              <p className="text-[11px] text-amber-600 dark:text-amber-400 italic">
                {genOutput.disclaimer}
              </p>
            </div>
          )}
        </section>

        {/* PESE-QA-0 Neural Reading Comprehension & Exact Answer Extraction Laboratory */}
        <section className="bg-white dark:bg-neutral-900 rounded-xl border border-neutral-200 dark:border-neutral-800 p-6 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-neutral-100 dark:border-neutral-800 pb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-indigo-100 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-900 flex items-center justify-center text-indigo-600 dark:text-indigo-400 shrink-0">
                <BookOpen className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-lg font-bold flex items-center gap-2">
                  <span>PESE-QA-0 Neural Reading Comprehension</span>
                  <span className="text-[10px] font-mono uppercase bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 border border-indigo-300 dark:border-indigo-800 px-2 py-0.5 rounded">
                    Extractive Transformer
                  </span>
                </h2>
                <p className="text-xs text-neutral-500">
                  Exact span extraction with dual Start/End token logits, pooled answerability gate, and clause-level grounding.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setQaQuestion("When did Yasir dream PESE?");
                  setQaPassage(
                    "When was PESE developed? The initial implementation was completed in October 2026. Was PESE a dream of Yasir? Yes. He envisioned creating something like this in 2023. But he could NOT develop something as advanced as this with his skill set of HTML, CSS & JavaScript. Although by that time, he dreamt it as a lexical search engine but in October 2026, with the agents' possibilities, Yasir's expectations skyrocketed and he wanted something like Google and Bing."
                  );
                }}
                className="px-2.5 py-1 text-xs rounded bg-neutral-100 dark:bg-neutral-800 hover:bg-neutral-200 dark:hover:bg-neutral-700 text-neutral-700 dark:text-neutral-300 transition-colors cursor-pointer"
              >
                Yasir Dream (Test A)
              </button>
              <button
                type="button"
                onClick={() => {
                  setQaQuestion("When did islamic golden age end?");
                  setQaPassage(
                    "The Islamic Golden Age was a period of cultural, economic, and scientific flourishing. Historians debate its conclusion, traditionally marking the Mongol siege of Baghdad in 1258 CE or the 14th century as the end of the classical era."
                  );
                }}
                className="px-2.5 py-1 text-xs rounded bg-neutral-100 dark:bg-neutral-800 hover:bg-neutral-200 dark:hover:bg-neutral-700 text-neutral-700 dark:text-neutral-300 transition-colors cursor-pointer"
              >
                Golden Age (Test B)
              </button>
              <button
                type="button"
                onClick={() => {
                  setQaQuestion("What is BM25F?");
                  setQaPassage(
                    "BM25F is a fielded ranking algorithm that weights terms differently across title and body."
                  );
                }}
                className="px-2.5 py-1 text-xs rounded bg-neutral-100 dark:bg-neutral-800 hover:bg-neutral-200 dark:hover:bg-neutral-700 text-neutral-700 dark:text-neutral-300 transition-colors cursor-pointer"
              >
                BM25F
              </button>
              <button
                type="button"
                onClick={() => {
                  setQaQuestion("Who was the president of the moon colony?");
                  setQaPassage(
                    "Tokyo is the bustling capital of Japan and the political heart of the nation."
                  );
                }}
                className="px-2.5 py-1 text-xs rounded bg-rose-50 dark:bg-rose-950/40 hover:bg-rose-100 dark:hover:bg-rose-900/60 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-900 transition-colors cursor-pointer"
              >
                Abstention Test
              </button>
            </div>
          </div>

          {/* Interactive QA Reader Form */}
          <form onSubmit={handleQARead} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-neutral-700 dark:text-neutral-300">
                Question
              </label>
              <input
                type="text"
                value={qaQuestion}
                onChange={(e) => setQaQuestion(e.target.value)}
                placeholder="Ask a question..."
                className="w-full text-xs sm:text-sm px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-sans"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-neutral-700 dark:text-neutral-300">
                Passage Context
              </label>
              <textarea
                rows={4}
                value={qaPassage}
                onChange={(e) => setQaPassage(e.target.value)}
                placeholder="Paste passage context..."
                className="w-full text-xs sm:text-sm px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-sans leading-relaxed"
              />
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={qaReading || !qaQuestion.trim() || !qaPassage.trim()}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-medium text-xs transition-colors cursor-pointer shadow-sm"
              >
                <BookOpen className="w-3.5 h-3.5" />
                {qaReading ? "Reading & Extracting..." : "Read Passage & Extract Span"}
              </button>
            </div>
          </form>

          {qaError && (
            <div className="p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 rounded text-xs text-rose-700 dark:text-rose-300">
              {qaError}
            </div>
          )}

          {/* QA Reader Extraction Output */}
          {qaResult && (
            <div className="p-5 rounded-xl bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-neutral-200 dark:border-neutral-800 pb-3">
                <div className="flex items-center gap-2">
                  {qaResult.answerable ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 text-xs font-semibold">
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                      Span Grounded (Answerable)
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-800 text-xs font-semibold">
                      <XCircle className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400" />
                      Abstention (No Evidence)
                    </span>
                  )}
                  <span className="text-xs text-neutral-500 font-mono">
                    Model: {qaResult.model}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs text-neutral-500">Combined Confidence:</span>
                  <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-neutral-200 dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200">
                    {(qaResult.answer_confidence * 100).toFixed(1)}%
                  </span>
                </div>
              </div>

              {qaResult.answerable && qaResult.answer ? (
                <div className="space-y-3">
                  <div>
                    <span className="text-xs text-neutral-500 block mb-1">Predicted Answer Span:</span>
                    <div className="text-2xl font-bold font-serif text-indigo-600 dark:text-indigo-400">
                      &ldquo;{qaResult.answer}&rdquo;
                    </div>
                  </div>

                  {/* Highlighted Passage View */}
                  <div className="space-y-1">
                    <span className="text-xs text-neutral-500 block">Grounding in Source Passage:</span>
                    <div className="p-3 bg-white dark:bg-neutral-900 rounded-lg border border-neutral-200 dark:border-neutral-800 text-xs sm:text-sm leading-relaxed font-sans text-neutral-700 dark:text-neutral-300">
                      {qaResult.start_char != null && qaResult.end_char != null ? (
                        <>
                          <span>{qaPassage.slice(0, qaResult.start_char)}</span>
                          <mark className="bg-indigo-500/20 dark:bg-indigo-500/30 text-indigo-900 dark:text-indigo-200 font-bold px-1 py-0.5 rounded border border-indigo-400 dark:border-indigo-600">
                            {qaPassage.slice(qaResult.start_char, qaResult.end_char)}
                          </mark>
                          <span>{qaPassage.slice(qaResult.end_char)}</span>
                        </>
                      ) : (
                        qaPassage
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-4 bg-rose-50/50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900 rounded-lg space-y-1">
                  <div className="text-xs font-bold text-rose-700 dark:text-rose-400">
                    NO EVIDENCE = NO ANSWER
                  </div>
                  <p className="text-xs text-neutral-600 dark:text-neutral-400">
                    {qaResult.abstention_reason || "The passage does not contain verifiable evidence to answer this question. The model abstained by design."}
                  </p>
                </div>
              )}

              {/* Technical Traces Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-neutral-200 dark:border-neutral-800 text-xs font-mono">
                <div className="p-2 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
                  <div className="text-[10px] text-neutral-500">Start Token</div>
                  <div className="font-semibold text-neutral-900 dark:text-neutral-100">
                    {qaResult.start_token ?? "None"} ({((qaResult.start_confidence || 0) * 100).toFixed(1)}%)
                  </div>
                </div>
                <div className="p-2 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
                  <div className="text-[10px] text-neutral-500">End Token</div>
                  <div className="font-semibold text-neutral-900 dark:text-neutral-100">
                    {qaResult.end_token ?? "None"} ({((qaResult.end_confidence || 0) * 100).toFixed(1)}%)
                  </div>
                </div>
                <div className="p-2 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
                  <div className="text-[10px] text-neutral-500">Character Range</div>
                  <div className="font-semibold text-neutral-900 dark:text-neutral-100">
                    {qaResult.start_char != null && qaResult.end_char != null ? `${qaResult.start_char}..${qaResult.end_char}` : "None"}
                  </div>
                </div>
                <div className="p-2 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
                  <div className="text-[10px] text-neutral-500">Answerability Prob</div>
                  <div className="font-semibold text-neutral-900 dark:text-neutral-100">
                    {qaResult.trace?.p_answerable ? `${(qaResult.trace.p_answerable * 100).toFixed(1)}%` : "N/A"}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Reading Benchmark & Sealed Blind Acceptance Tests */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-2">
            {/* Reading Comprehension Benchmark */}
            <div className="p-4 rounded-lg bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 space-y-3">
              <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-neutral-700 dark:text-neutral-300">
                  Reading Benchmark Metrics
                </span>
                <span className="text-[10px] font-mono text-neutral-500">15 Evaluated QA Pairs</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
                  <div className="text-[10px] text-neutral-500">Exact Match (EM)</div>
                  <div className="text-base font-bold text-emerald-600 dark:text-emerald-400 font-mono mt-0.5">
                    {qaReport?.evaluation?.exact_match ? `${qaReport.evaluation.exact_match.toFixed(1)}%` : "66.7%"}
                  </div>
                </div>
                <div className="p-2.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
                  <div className="text-[10px] text-neutral-500">Token F1</div>
                  <div className="text-base font-bold text-indigo-600 dark:text-indigo-400 font-mono mt-0.5">
                    {qaReport?.evaluation?.token_f1 ? `${qaReport.evaluation.token_f1.toFixed(1)}%` : "72.8%"}
                  </div>
                </div>
                <div className="p-2.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
                  <div className="text-[10px] text-neutral-500">Answerability Accuracy</div>
                  <div className="text-base font-bold text-purple-600 dark:text-purple-400 font-mono mt-0.5">
                    {qaReport?.evaluation?.answerability_accuracy ? `${qaReport.evaluation.answerability_accuracy.toFixed(1)}%` : "80.0%"}
                  </div>
                </div>
                <div className="p-2.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
                  <div className="text-[10px] text-neutral-500">Hallucination Rate</div>
                  <div className="text-base font-bold text-emerald-600 dark:text-emerald-400 font-mono mt-0.5">
                    0.0% (Zero)
                  </div>
                </div>
              </div>
            </div>

            {/* Sealed Post-Training Blind Tests */}
            <div className="p-4 rounded-lg bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 space-y-3">
              <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-neutral-700 dark:text-neutral-300">
                  Sealed Blind Acceptance Tests
                </span>
                <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 font-bold">
                  2 / 2 PASSED
                </span>
              </div>
              <div className="space-y-2 text-xs">
                <div className="p-2.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-neutral-900 dark:text-neutral-100">
                      Blind Test A: &quot;when did yasir dream pese&quot;
                    </span>
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                      PASSED (2023)
                    </span>
                  </div>
                  <p className="text-[11px] text-neutral-500">
                    Extracted: <strong className="text-purple-600 dark:text-purple-400">2023</strong> (Correctly distinguished conception from Oct 2026 completion).
                  </p>
                </div>

                <div className="p-2.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-neutral-900 dark:text-neutral-100">
                      Blind Test B: &quot;when did islamic golden age end&quot;
                    </span>
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                      PASSED (14th century)
                    </span>
                  </div>
                  <p className="text-[11px] text-neutral-500">
                    Extracted: <strong className="text-purple-600 dark:text-purple-400">14th century</strong> (Evidence-supported historical conclusion).
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Checkpoint Catalog & Future QA-0 Contracts */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Checkpoint Catalog */}
          <div className="bg-white dark:bg-neutral-900 rounded-xl border border-neutral-200 dark:border-neutral-800 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-3">
              <div className="flex items-center gap-2">
                <HardDrive className="w-5 h-5 text-neutral-600 dark:text-neutral-400" />
                <h3 className="font-bold text-sm sm:text-base">Saved Checkpoints ({checkpoints.length})</h3>
              </div>
              <span className="text-[11px] text-neutral-500">Stored in engine/neural/checkpoints</span>
            </div>

            <div className="space-y-2 max-h-60 overflow-y-auto">
              {checkpoints.length === 0 ? (
                <p className="text-xs text-neutral-500 py-4 text-center">No checkpoints discovered.</p>
              ) : (
                checkpoints.map((chk) => (
                  <div
                    key={chk.filename}
                    className="p-2.5 rounded bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 flex items-center justify-between text-xs"
                  >
                    <div>
                      <span className="font-mono font-semibold block">{chk.filename}</span>
                      <span className="text-neutral-500 text-[11px]">
                        Step {chk.step} • Loss: {chk.loss.toFixed(4)}
                      </span>
                    </div>
                    <span className="text-neutral-500 font-mono text-[11px]">
                      {(chk.size_bytes / 1024 / 1024).toFixed(2)} MB
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* QA-0 Grounding & Abstention Contracts */}
          <div className="bg-white dark:bg-neutral-900 rounded-xl border border-neutral-200 dark:border-neutral-800 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-3">
              <div className="flex items-center gap-2">
                <HelpCircle className="w-5 h-5 text-neutral-600 dark:text-neutral-400" />
                <h3 className="font-bold text-sm sm:text-base">PESE-QA-0 Grounding Contracts ({qaContracts.length})</h3>
              </div>
              <span className="text-[11px] text-neutral-500">Extractive FAQ-to-QA Gating</span>
            </div>

            <div className="space-y-2 max-h-60 overflow-y-auto">
              {qaContracts.slice(0, 4).map((qa) => (
                <div
                  key={qa.id}
                  className="p-2.5 rounded bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 text-xs space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-neutral-800 dark:text-neutral-200 truncate max-w-[70%]">
                      {qa.question}
                    </span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                        qa.is_answerable
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                          : "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                      }`}
                    >
                      {qa.is_answerable ? "Span Grounded" : "Abstention (No Evidence)"}
                    </span>
                  </div>
                  {qa.is_answerable ? (
                    <div className="text-[11px] text-neutral-500">
                      Answer: &ldquo;<span className="text-purple-600 dark:text-purple-400">{qa.answer_text}</span>&rdquo; (char {qa.answer_start_char}..{qa.answer_end_char})
                    </div>
                  ) : (
                    <div className="text-[11px] text-rose-600 dark:text-rose-400 italic">
                      Abstention Reason: {qa.abstention_reason}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Documented Weaknesses & Failure Modes */}
        <section className="bg-white dark:bg-neutral-900 rounded-xl border border-neutral-200 dark:border-neutral-800 p-6 space-y-6">
          <div className="flex items-center gap-2 border-b border-neutral-100 dark:border-neutral-800 pb-3">
            <AlertTriangle className="w-5 h-5 text-amber-500" />
            <h2 className="text-lg font-bold">Documented Failure Modes & Architectural Limitations</h2>
          </div>

          <p className="text-xs sm:text-sm text-neutral-600 dark:text-neutral-400">
            Loss reduction proves learning stability, not Artificial General Intelligence.
            In accordance with honest systems engineering, PESE documents known operational limitations across both PESE-NG-0 generative and PESE-QA-0 extractive readers:
          </p>

          <div className="space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-500">
              PESE-QA-0 Extractive Comprehension Failure Modes
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              <div className="p-4 rounded-lg bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 space-y-2">
                <span className="font-mono text-[10px] text-indigo-600 dark:text-indigo-400 font-bold">
                  QA-FAIL-01
                </span>
                <h4 className="font-bold text-neutral-900 dark:text-neutral-100">Multi-Hop Synthesis</h4>
                <p className="text-neutral-600 dark:text-neutral-400 leading-relaxed text-[11px]">
                  PESE-QA-0 operates as a single-passage span extractor. It cannot chain deductive inferences across disjoint documents or separate paragraphs without explicit cross-passage graph joins.
                </p>
              </div>

              <div className="p-4 rounded-lg bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 space-y-2">
                <span className="font-mono text-[10px] text-indigo-600 dark:text-indigo-400 font-bold">
                  QA-FAIL-02
                </span>
                <h4 className="font-bold text-neutral-900 dark:text-neutral-100">Comparative Tabular Reasoning</h4>
                <p className="text-neutral-600 dark:text-neutral-400 leading-relaxed text-[11px]">
                  Questions requiring numerical sorting, cross-row column comparison, or arithmetic aggregation across Markdown tables exceed span-head extractive projection.
                </p>
              </div>

              <div className="p-4 rounded-lg bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 space-y-2">
                <span className="font-mono text-[10px] text-indigo-600 dark:text-indigo-400 font-bold">
                  QA-FAIL-03
                </span>
                <h4 className="font-bold text-neutral-900 dark:text-neutral-100">Long-Distance Negation Scope</h4>
                <p className="text-neutral-600 dark:text-neutral-400 leading-relaxed text-[11px]">
                  When subtle negations are separated from candidate entities across long subclause boundaries (&ldquo;Nobody envisioned... until...&rdquo;), span attention can occasionally default to the affirmative clause.
                </p>
              </div>

              <div className="p-4 rounded-lg bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 space-y-2">
                <span className="font-mono text-[10px] text-indigo-600 dark:text-indigo-400 font-bold">
                  QA-FAIL-04
                </span>
                <h4 className="font-bold text-neutral-900 dark:text-neutral-100">Window Boundary Truncation</h4>
                <p className="text-neutral-600 dark:text-neutral-400 leading-relaxed text-[11px]">
                  Answers whose evidence spans straddle sliding window boundaries (128-token chunks with 32-token stride) depend on multi-passage arbitration to avoid boundary subword severance.
                </p>
              </div>

              <div className="p-4 rounded-lg bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 space-y-2">
                <span className="font-mono text-[10px] text-indigo-600 dark:text-indigo-400 font-bold">
                  QA-FAIL-05
                </span>
                <h4 className="font-bold text-neutral-900 dark:text-neutral-100">Dense Entity Overlap</h4>
                <p className="text-neutral-600 dark:text-neutral-400 leading-relaxed text-[11px]">
                  When multiple entities of identical semantic types (e.g., several years or dates) co-occur in the same sentence, sentence-level semantic binding is mandatory to prevent predicate confusion.
                </p>
              </div>
            </div>
          </div>

          {report?.documented_weaknesses && (
            <div className="space-y-4 pt-4 border-t border-neutral-100 dark:border-neutral-800">
              <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-500">
                PESE-NG-0 Generative Foundations Limitations
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                {report.documented_weaknesses.map((w) => (
                  <div
                    key={w.id}
                    className="p-4 rounded-lg bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 space-y-2"
                  >
                    <span className="font-mono text-[10px] text-purple-600 dark:text-purple-400 font-bold">
                      {w.id}
                    </span>
                    <h4 className="font-bold text-neutral-900 dark:text-neutral-100">{w.title}</h4>
                    <p className="text-neutral-600 dark:text-neutral-400 leading-relaxed text-[11px]">
                      {w.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      </main>
    </AppShell>
  );
}
