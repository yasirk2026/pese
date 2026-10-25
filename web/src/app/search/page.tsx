"use client";

import React, { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { SearchAutocomplete } from "@/components/SearchAutocomplete";
import { RankingTraceAudit } from "@/components/RankingTraceAudit";
import { QueryAnalysisAudit } from "@/components/QueryAnalysisAudit";
import { YouMightAlsoAsk } from "@/components/YouMightAlsoAsk";
import { RelatedSearches } from "@/components/RelatedSearches";
import { DiscoveryAudit } from "@/components/DiscoveryAudit";
import { HybridRetrievalAudit } from "@/components/HybridRetrievalAudit";
import { SearchTimingAudit } from "@/components/SearchTimingAudit";
import { AnswerTruthfulnessAudit } from "@/components/AnswerTruthfulnessAudit";
import { SearchFeedbackControls } from "@/components/SearchFeedbackControls";
import { useApp } from "@/context/AppContext";
import {
  searchDocuments,
  getPAAQuestions,
  getRelatedSearches,
  SearchResult,
  SearchResponse,
  PAAQuestionItem,
  RelatedSearchItem,
  sendTelemetryEvent,
  getOrCreateSessionId,
} from "@/lib/api";
import { FileText, Link2, AlertCircle, ArrowUpRight, Sparkles, Sliders } from "lucide-react";

function SearchResultsContent() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q") || "";
  const initialDebug = searchParams.get("debug") === "true";
  const forceRaw = searchParams.get("force_raw") === "true";
  const [debugMode, setDebugMode] = useState(initialDebug);
  return <SearchQuery key={JSON.stringify([query, forceRaw, debugMode])} query={query} forceRaw={forceRaw} debugMode={debugMode} setDebugMode={setDebugMode} />;
}

function SearchQuery({query, forceRaw, debugMode, setDebugMode}: {
  query: string; forceRaw: boolean; debugMode: boolean; setDebugMode: (value: boolean) => void;
}) {
  const { developerMode } = useApp();
  const [searchData, setSearchData] = useState<SearchResponse | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [paaQuestions, setPaaQuestions] = useState<PAAQuestionItem[]>([]);
  const [relatedSearches, setRelatedSearches] = useState<RelatedSearchItem[]>([]);
  const [loading, setLoading] = useState(Boolean(query.trim()));
  const [loadingStage, setLoadingStage] = useState<"idle" | "subtle" | "text">("idle");
  const [error, setError] = useState<string | null>(null);
  const [tookMs, setTookMs] = useState<number>(0);
  const [clientTookMs, setClientTookMs] = useState<number>(0);
  const [visibleTookMs, setVisibleTookMs] = useState<number>(0);
  const [discoveryErrors, setDiscoveryErrors] = useState<string[]>([]);

  useEffect(() => {
    if (!loading) {
      return;
    }

    const timerSubtle = setTimeout(() => {
      setLoadingStage("subtle");
    }, 150);

    const timerText = setTimeout(() => {
      setLoadingStage("text");
    }, 400);

    return () => {
      clearTimeout(timerSubtle);
      clearTimeout(timerText);
    };
  }, [loading]);

  useEffect(() => {
    if (!query.trim()) {
      return;
    }

    const t0 = performance.now();
    let active = true;
    const controller = new AbortController();
    const sid = getOrCreateSessionId();

    const loadDiscovery = () => {
      getPAAQuestions(query, sid, 4, debugMode, controller.signal)
        .then((paaRes) => {
          if (!active) return;
          setPaaQuestions(paaRes.questions || []);
        })
        .catch((err) => {
          if (!active) return;
          setPaaQuestions([]);
          setDiscoveryErrors((errors) => [...errors, `PAA: ${err.message}`]);
        });

      getRelatedSearches(query, sid, 5, debugMode, controller.signal)
        .then((relRes) => {
          if (!active) return;
          setRelatedSearches(relRes.related_searches || []);
        })
        .catch((err) => {
          if (!active) return;
          setRelatedSearches([]);
          setDiscoveryErrors((errors) => [...errors, `Related: ${err.message}`]);
        });
    };

    // Load discovery (You Might Also Ask & Related Searches) in parallel with primary retrieval
    loadDiscovery();

    searchDocuments(query, debugMode, 20, forceRaw, sid, "hybrid", controller.signal)
      .then((searchRes) => {
        if (!active) return;
        setSearchData(searchRes);
        setResults(searchRes.results);
        setTookMs(searchRes.took_ms);
        setClientTookMs(performance.now() - t0);
        setLoading(false);
        requestAnimationFrame(() => requestAnimationFrame(() => {
          if (active) setVisibleTookMs(performance.now() - t0);
        }));
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message || "Failed to retrieve search results");
        setLoading(false);
      });

    return () => { active = false; controller.abort(); };
  }, [query, forceRaw, debugMode]);

  const handleResultClick = (result: SearchResult) => {
    sendTelemetryEvent("result_clicked", {
      query,
      target_slug: result.slug,
      rank_position: result.rank,
      final_score: result.final_score,
    });
  };

  const topResults = results.slice(0, 2);
  const remainingResults = results.slice(2);

  const header = (
    <div className="w-full flex items-center justify-between gap-4">
      <div className="flex-1 max-w-2xl">
        <SearchAutocomplete initialQuery={query} size="medium" />
      </div>
      {!loading && (
        <span className="text-xs font-mono text-neutral-500 hidden sm:inline">
          {results.length} {results.length === 1 ? "result" : "results"} · {tookMs} ms
        </span>
      )}
    </div>
  );

  return (
    <AppShell headerContent={header} noPadding={true}>
      <div className="min-h-full bg-background text-foreground transition-colors p-6 sm:p-8 max-w-4xl mx-auto w-full">
        {/* Progress Bar */}
        {loading && loadingStage !== "idle" && (
          <div className="fixed top-0 left-64 right-0 z-50 h-1 bg-neutral-200 dark:bg-neutral-800 overflow-hidden">
            <div className="h-full bg-blue-600 animate-[pulse_1s_ease-in-out_infinite] w-full" />
          </div>
        )}

        {/* Developer Diagnostics Bar (Visible ONLY when Developer Mode is ON) */}
        {developerMode && (
          <div className="mb-6 p-3 rounded-xl bg-blue-50/60 dark:bg-blue-950/20 border border-blue-200/60 dark:border-blue-900/40 flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2 text-blue-700 dark:text-blue-300 font-medium">
              <Sliders className="w-3.5 h-3.5" />
              <span>Developer Diagnostics</span>
            </div>
            <label className="flex items-center gap-2 cursor-pointer select-none text-neutral-700 dark:text-neutral-300">
              <input
                type="checkbox"
                checked={debugMode}
                onChange={(e) => setDebugMode(e.target.checked)}
                className="rounded border-neutral-300 dark:border-neutral-700 text-blue-600 focus:ring-blue-500 cursor-pointer"
              />
              <span className="text-xs font-medium">Inspect Ranking Traces &amp; Stage Timing</span>
            </label>
          </div>
        )}

        {/* Developer Debug Panels */}
        {developerMode && debugMode && (
          <div className="mb-8 space-y-4">
            <AnswerTruthfulnessAudit
              qaTrace={searchData?.qa_trace ?? null}
              topResult={results[0] ?? null}
              query={query}
            />

            {searchData?.timing && (
              <SearchTimingAudit
                timing={searchData.timing}
                clientTookMs={clientTookMs}
                qaTrace={searchData.qa_trace}
              />
            )}

            {searchData && (
              <QueryAnalysisAudit
                analysis={searchData.query_analysis}
                rejectedCandidates={searchData.rejected_candidates}
                forceRaw={forceRaw}
              />
            )}

            {searchData?.hybrid_trace && (
              <HybridRetrievalAudit
                trace={searchData.hybrid_trace}
                totalResults={results.length}
              />
            )}

            <DiscoveryAudit
              paaQuestions={paaQuestions}
              relatedSearches={relatedSearches}
              query={query}
            />
          </div>
        )}

        {/* Typo Recovery Banner */}
        {!loading && searchData?.has_corrections && !forceRaw && (
          <div className="mb-6 py-2.5 px-4 rounded-xl bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 text-sm">
            <div className="text-neutral-800 dark:text-neutral-200">
              <span>Showing results for: </span>
              <Link
                href={`/search?q=${encodeURIComponent(searchData.effective_query)}`}
                className="font-semibold text-blue-600 dark:text-blue-400 hover:underline italic"
              >
                {searchData.effective_query}
              </Link>
            </div>
            <div className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
              <span>Search instead for: </span>
              <Link
                href={`/search?q=${encodeURIComponent(query)}&force_raw=true`}
                className="text-blue-500 hover:underline"
              >
                {query}
              </Link>
            </div>
          </div>
        )}

        {/* Forced Raw Query Banner */}
        {!loading && forceRaw && (
          <div className="mb-6 py-2 px-3 rounded-xl bg-neutral-100 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-xs text-neutral-600 dark:text-neutral-400">
            <span>Showing raw uncorrected results for: <strong>{query}</strong>. </span>
            <Link
              href={`/search?q=${encodeURIComponent(query)}`}
              className="text-blue-600 dark:text-blue-400 hover:underline ml-1"
            >
              Turn typo recovery back on
            </Link>
          </div>
        )}

        {/* Loading State */}
        {loading && loadingStage === "text" && results.length === 0 && (
          <div className="py-20 text-center space-y-3">
            <div className="inline-block w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-neutral-500 dark:text-neutral-400 font-medium">Searching PESE...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="my-8 p-4 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/60 rounded-xl text-rose-800 dark:text-rose-200 text-sm flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold">Search Engine Error</div>
              <p className="mt-1">{error}</p>
              <p className="mt-2 text-xs text-rose-600 dark:text-rose-400">
                Restart PESE if your Brain connection was interrupted.
              </p>
            </div>
          </div>
        )}

        {/* No Results State */}
        {!loading && !error && results.length === 0 && (
          <div className="py-20 text-center space-y-3">
            <p className="text-lg text-neutral-800 dark:text-neutral-200">
              No results found for <strong className="font-semibold">&quot;{query}&quot;</strong>
            </p>
            <p className="text-sm text-neutral-500 dark:text-neutral-400">
              Check spelling, try broader terms, or create a note in your Brain.
            </p>
          </div>
        )}

        {/* Results Stream */}
        {results.length > 0 && (
          <div className={`space-y-6 transition-opacity duration-150 ${loading ? "opacity-60" : "opacity-100"}`}>
            {/* Featured Snippet Box */}
            {results[0].is_featured && results[0].featured_answer && (
              <div className="p-6 rounded-2xl bg-white dark:bg-neutral-900/90 border border-neutral-200 dark:border-neutral-800 shadow-md relative overflow-hidden">
                <div className="absolute top-0 right-0 bg-blue-600 text-white px-3 py-1 text-[10px] font-mono font-bold tracking-wider uppercase rounded-bl-lg">
                  Featured Answer
                </div>

                <div className="text-2xl sm:text-3xl font-bold text-neutral-900 dark:text-neutral-50 mt-1 mb-3">
                  {results[0].featured_answer}
                </div>

                <div
                  className="text-neutral-700 dark:text-neutral-300 text-sm leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: results[0].snippet_html }}
                />

                <div className="mt-4 pt-3 border-t border-neutral-100 dark:border-neutral-800/80 flex items-center justify-between text-xs">
                  <Link
                    href={`/doc?slug=${encodeURIComponent(results[0].slug)}`}
                    onClick={() => handleResultClick(results[0])}
                    className="text-blue-600 dark:text-blue-400 font-medium hover:underline flex items-center gap-1"
                  >
                    <span>Extracted from: {results[0].title}</span>
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </Link>
                  <span className="text-neutral-400 font-mono text-[11px]">
                    Passage Score: {results[0].trace.passage_signal.toFixed(2)}
                  </span>
                </div>

                <div className="mt-3 pt-2 border-t border-neutral-100 dark:border-neutral-800/60 flex items-center justify-between text-xs">
                  <span className="text-[11px] text-neutral-500 font-mono">Was this answer helpful?</span>
                  <SearchFeedbackControls
                    query={query}
                    targetType="FEATURED_ANSWER"
                    targetId={results[0].doc_id}
                    targetSlug={results[0].slug}
                    rankPosition={1}
                    searchContextId={searchData?.search_id}
                  />
                </div>
              </div>
            )}

            {/* Top Ranked Search Results */}
            {topResults.map((result) => (
              <article key={result.slug} className="p-5 rounded-2xl bg-white dark:bg-neutral-900/70 border border-neutral-200/90 dark:border-neutral-800/90 hover:border-neutral-300 dark:hover:border-neutral-700 shadow-2xs hover:shadow-xs transition-all group">
                <div className="flex items-center gap-1.5 text-xs text-neutral-400 font-mono mb-1">
                  <span className="text-neutral-500">note://{result.slug}</span>
                  <span>•</span>
                  <span className="text-[11px] font-bold text-blue-600 dark:text-blue-400">
                    #{result.rank}
                  </span>
                </div>

                <h2 className="text-lg font-semibold tracking-tight">
                  <Link
                    href={`/doc?slug=${encodeURIComponent(result.slug)}`}
                    onClick={() => handleResultClick(result)}
                    className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 hover:underline transition-colors"
                  >
                    {result.title}
                  </Link>
                </h2>

                <div
                  className="mt-1.5 text-sm text-neutral-600 dark:text-neutral-300 leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: result.snippet_html }}
                />

                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-neutral-400 font-mono">
                  {result.is_semantic_rescue && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-200 dark:border-emerald-800/70 px-2 py-0.5 rounded-full">
                      <Sparkles className="w-3 h-3 text-emerald-500" />
                      Semantic Rescue
                    </span>
                  )}
                  <span className="flex items-center gap-1">
                    <FileText className="w-3 h-3 text-neutral-400" />
                    {result.word_count} words
                  </span>
                  <span className="flex items-center gap-1">
                    <Link2 className="w-3 h-3 text-neutral-400" />
                    {result.in_links_count} in-links
                  </span>
                  <span className="text-neutral-700 dark:text-neutral-300 font-medium">
                    Score: {result.final_score.toFixed(4)}
                  </span>
                </div>

                {/* Search Sync Feedback Controls */}
                <div className="mt-3 pt-2 border-t border-neutral-100 dark:border-neutral-800/80 flex flex-wrap items-center justify-between gap-2">
                  <SearchFeedbackControls
                    query={query}
                    targetType="SERP_RESULT"
                    targetId={result.doc_id}
                    targetSlug={result.slug}
                    rankPosition={result.rank}
                    initialFeedback={result.search_sync_feedback}
                    searchContextId={searchData?.search_id}
                  />
                  {result.search_sync_adjustment !== undefined && result.search_sync_adjustment !== 0 && (
                    <span className="text-[10px] font-mono text-neutral-400">
                      Sync: {result.search_sync_adjustment > 0 ? `+${result.search_sync_adjustment.toFixed(2)}` : result.search_sync_adjustment.toFixed(2)}
                    </span>
                  )}
                </div>

                {developerMode && debugMode && (
                  <RankingTraceAudit
                    currentResult={result}
                    allResults={results}
                    query={query}
                  />
                )}
              </article>
            ))}

            {/* Questions Accordion */}
            <YouMightAlsoAsk questions={paaQuestions} currentQuery={query} />

            {/* Remaining Results */}
            {remainingResults.map((result) => (
              <article key={result.slug} className="p-5 rounded-2xl bg-white dark:bg-neutral-900/70 border border-neutral-200/90 dark:border-neutral-800/90 hover:border-neutral-300 dark:hover:border-neutral-700 shadow-2xs hover:shadow-xs transition-all group">
                <div className="flex items-center gap-1.5 text-xs text-neutral-400 font-mono mb-1">
                  <span className="text-neutral-500">note://{result.slug}</span>
                  <span>•</span>
                  <span className="text-[11px] font-bold text-blue-600 dark:text-blue-400">
                    #{result.rank}
                  </span>
                </div>

                <h2 className="text-lg font-semibold tracking-tight">
                  <Link
                    href={`/doc?slug=${encodeURIComponent(result.slug)}`}
                    onClick={() => handleResultClick(result)}
                    className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 hover:underline transition-colors"
                  >
                    {result.title}
                  </Link>
                </h2>

                <div
                  className="mt-1.5 text-sm text-neutral-600 dark:text-neutral-300 leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: result.snippet_html }}
                />

                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-neutral-400 font-mono">
                  {result.is_semantic_rescue && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-200 dark:border-emerald-800/70 px-2 py-0.5 rounded-full">
                      <Sparkles className="w-3 h-3 text-emerald-500" />
                      Semantic Rescue
                    </span>
                  )}
                  <span className="flex items-center gap-1">
                    <FileText className="w-3 h-3 text-neutral-400" />
                    {result.word_count} words
                  </span>
                  <span className="flex items-center gap-1">
                    <Link2 className="w-3 h-3 text-neutral-400" />
                    {result.in_links_count} in-links
                  </span>
                  <span className="text-neutral-700 dark:text-neutral-300 font-medium">
                    Score: {result.final_score.toFixed(4)}
                  </span>
                </div>

                {/* Search Sync Feedback Controls */}
                <div className="mt-3 pt-2 border-t border-neutral-100 dark:border-neutral-800/80 flex flex-wrap items-center justify-between gap-2">
                  <SearchFeedbackControls
                    query={query}
                    targetType="SERP_RESULT"
                    targetId={result.doc_id}
                    targetSlug={result.slug}
                    rankPosition={result.rank}
                    initialFeedback={result.search_sync_feedback}
                    searchContextId={searchData?.search_id}
                  />
                  {result.search_sync_adjustment !== undefined && result.search_sync_adjustment !== 0 && (
                    <span className="text-[10px] font-mono text-neutral-400">
                      Sync: {result.search_sync_adjustment > 0 ? `+${result.search_sync_adjustment.toFixed(2)}` : result.search_sync_adjustment.toFixed(2)}
                    </span>
                  )}
                </div>

                {developerMode && debugMode && (
                  <RankingTraceAudit
                    currentResult={result}
                    allResults={results}
                    query={query}
                  />
                )}
              </article>
            ))}

            {/* Related Searches */}
            <RelatedSearches relatedSearches={relatedSearches} currentQuery={query} />
          </div>
        )}
      </div>
    </AppShell>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-sm text-neutral-500">Loading search...</div>}>
      <SearchResultsContent />
    </Suspense>
  );
}
