import type { JSONContent } from "@tiptap/react";
/**
 * PESE API Client
 * Facilitates communication with the Python Search Engine backend.
 */

export function getApiBase(): string {
  if (typeof window !== "undefined") {
    const injected = (window as unknown as { __PESE_CONFIG__?: { apiBase?: string } }).__PESE_CONFIG__?.apiBase;
    if (injected) return injected;
    if (window.location && window.location.origin && window.location.origin !== "null") {
      return window.location.origin;
    }
  }
  return process.env.NEXT_PUBLIC_ENGINE_API_URL || "http://localhost:8000";
}

const API_BASE = {
  toString: () => getApiBase(),
  valueOf: () => getApiBase(),
};

/** Add the in-memory desktop credential only to this API client's requests. */
function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (typeof window !== "undefined") {
    const token = (window as unknown as { __PESE_CONFIG__?: { token?: string } }).__PESE_CONFIG__?.token;
    if (token) headers.set("X-PESE-Token", token);
  }
  return fetch(input, { ...init, headers });
}

export interface IntelligenceSettings {
  version: number;
  neural_search: boolean;
  learn_from_feedback: boolean;
  collect_research_feedback: boolean;
  allow_journal_learning: boolean;
  community_contributions: boolean;
  consent_revision: number;
  excluded_document_ids: string[];
}
export interface ContributionPreview {
  preview_id: string;
  sha256: string;
  package: Record<string, unknown>;
  destination: string;
  retention: string;
  revocation: string;
  privacy: string;
}
async function intelligenceRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(`${API_BASE}/api/intelligence/${path}`, init);
  if (!response.ok) throw new Error("The local intelligence action could not be completed. Your saved choices remain in effect.");
  return response.json();
}
export const getIntelligenceSettings = () => intelligenceRequest<{settings: IntelligenceSettings; neural_available: boolean; neural_status: string}>("settings");
export const saveIntelligenceSettings = (changes: Partial<IntelligenceSettings>) => intelligenceRequest<{settings: IntelligenceSettings}>("settings", {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(changes)});
export const resetIntelligencePersonalization = () => intelligenceRequest("personalization", {method: "DELETE"});
export const previewIntelligenceContribution = () => intelligenceRequest<ContributionPreview>("contributions/preview", {method: "POST"});
export const exportIntelligenceContribution = (preview: ContributionPreview) => intelligenceRequest<Record<string, unknown>>("contributions/export", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({preview_id: preview.preview_id, sha256: preview.sha256, reviewed: true})});
export const cancelIntelligenceContribution = (preview: ContributionPreview) => intelligenceRequest(`contributions/preview/${preview.preview_id}`, {method: "DELETE"});

export interface BetaStatus {
  supported: boolean; channel: string; agreement_hash: string;
  agreement: { title: string; statements: string[] };
  participation: { accepted: boolean; paused?: boolean; neural?: boolean; feedback_scope?: string[]; journal_scope?: string[]; retention_days?: number };
  storage_namespace?: string; brain_id?: string;
  learning_active: boolean; ranking_mode: string; model: { version?: string; checkpoint?: string; trust?: string; status?: string } | null;
  inference: { status: string; latency_ms?: number; peak_bytes?: number; cold?: boolean; authority?: string };
  fallback_events: number; rejected_events: number; evidence: Record<string, number>; training_running: boolean;
  last_job: { job_id?: string; status: string; training_examples?: number; seconds?: number; evaluation?: Record<string, unknown> } | null;
  privacy: Partial<IntelligenceSettings>; rollback_available: boolean; external_uploads: boolean;
}
export interface BetaExample {
  id: string; quality: string; role: string | null; receipt_hash: string;
  payload: { original_query?: string; evidence_text?: string; feedback?: string; reason?: string; source_kind?: string;
    receipt: { effective_query: string; target_id: string; document_revision: string } };
}
export async function betaRequest<T = BetaStatus>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await apiFetch(`${API_BASE}/api/intelligence/beta/${path}`, {method,
    headers: body === undefined ? undefined : {"Content-Type": "application/json"}, body: body === undefined ? undefined : JSON.stringify(body)});
  if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(typeof error.detail === "string" ? error.detail : "The local BETA operation was refused."); }
  return response.json();
}

export interface RankingTrace {
  doc_id: string;
  slug: string;
  title: string;
  retrieval_mode?: string;
  bm25_rank?: number | null;
  semantic_rank?: number | null;
  semantic_similarity?: number;
  rrf_score?: number;
  is_semantic_rescue?: boolean;
  drift_penalty_applied?: number;
  drift_reason?: string | null;
  bm25f_lexical: number;
  bm25f_breakdown: {
    title: number;
    headings: number;
    keywords: number;
    meta_description: number;
    body: number;
  };
  title_signal: number;
  heading_signal: number;
  passage_signal: number;
  phrase_signal: number;
  keyword_signal: number;
  matched_query_terms: number;
  total_query_terms: number;
  coverage_ratio: number;
  coverage_factor: number;
  link_authority: number;
  freshness_bonus: number;
  quality_bonus: number;
  spam_penalty: number;
  spam_reasons: string[];
  base_relevance: number;
  relevance_gated: number;
  positive_total: number;
  final_score: number;
  qa_shadow_answer?: string | null;
  qa_agreement?: string | null;
  qa_confidence?: number | null;
  // Phase 2D.2 — Answer Relevance Gate
  answer_relevance_verdict?: "PASS" | "REJECT" | "ABSTAIN" | null;
  answer_relevance_failure?: string | null;
  answer_relevance_score?: number | null;
  base_score?: number | null;
  search_sync_adjustment?: number;
  search_sync_feedback?: "LIKE" | "DISLIKE" | null;
  // Phase N3-B: Neural Shadow Bridge (PESE-Rel-0 Observer)
  rel_shadow_answers_prob?: number | null;
  rel_shadow_does_not_answer_prob?: number | null;
  rel_shadow_label?: string | null;
  rel_shadow_evidence_id?: string | null;
  rel_shadow_evidence_count?: number;
  rel_shadow_authority?: string;
  rel_shadow_alignment?: string | null;
  rel_shadow_status?: string | null;
}

export interface SearchResult {
  rank: number;
  doc_id: string;
  slug: string;
  title: string;
  snippet_text: string;
  snippet_html: string;
  featured_answer?: string | null;
  featured_justification?: string | null;
  is_featured: boolean;
  source_type: string;
  word_count: number;
  in_links_count: number;
  base_score?: number | null;
  search_sync_adjustment?: number;
  search_sync_feedback?: "LIKE" | "DISLIKE" | null;
  final_score: number;
  is_semantic_rescue?: boolean;
  semantic_similarity?: number;
  rrf_score?: number;
  trace: RankingTrace;
  answer_audit?: {
    source_slug?: string;
    source_passage?: string;
    candidate_span?: string | null;
    producer?: string;
    arbitration_reason?: string;
    validation?: Record<string, unknown> | null;
    qa_status?: string;
    neural_shadow_observation?: Record<string, unknown> | null;
  };
  neural_shadow?: {
    answers_probability?: number | null;
    does_not_answer_probability?: number | null;
    predicted_label?: string | null;
    best_evidence_id?: string | null;
    evidence_count?: number;
    authority?: string;
    status?: string;
    alignment?: string | null;
    observations?: Array<{
      observation_id: string;
      evidence_id: string;
      evidence_summary: string;
      answers_probability: number;
      predicted_label: string;
    }>;
  } | null;
}

export interface TypoCorrectionItem {
  original_token: string;
  corrected_token: string;
  edit_distance: number;
  edit_type: string;
  confidence: number;
  corpus_frequency: number;
}

// Discovery Types (Phase 2A)
export interface AutocompleteSuggestion {
  text: string;
  source: string;
  score: number;
  match_type: string;
  corpus_support: number;
  historical_searches: number;
  recent_searches: number;
  successful_clicks: number;
  session_context_bonus: number;
  highlight_ranges: [number, number][];
  debug_trace: Record<string, unknown>;
}

export interface SuggestResponse {
  query: string;
  effective_prefix: string;
  has_typo_correction: boolean;
  corrected_prefix?: string | null;
  suggestions: AutocompleteSuggestion[];
  took_ms: number;
}

export interface RelatedSearchItem {
  query: string;
  score: number;
  source: string;
  co_occurrence_score: number;
  result_overlap_score: number;
  link_affinity_score: number;
  debug_trace: Record<string, unknown>;
}

export interface RelatedSearchesResponse {
  query: string;
  related_searches: RelatedSearchItem[];
  took_ms: number;
}

export interface PAAQuestionItem {
  question: string;
  answer: string;
  justification: string;
  source_slug: string;
  source_title: string;
  confidence_score: number;
  passage_score: number;
  answerability_status: string;
  intent: string;
  debug_trace: Record<string, unknown>;
}

export interface QuestionsResponse {
  query: string;
  questions: PAAQuestionItem[];
  total_candidates_evaluated: number;
  total_passed_gate: number;
  took_ms: number;
}

export interface HistoryItem {
  query: string;
  session_id?: string | null;
  timestamp?: string | null;
}

export interface HistoryResponse {
  history_enabled: boolean;
  recent_searches: HistoryItem[];
  total_unique_queries: number;
}

export interface QueryAnalysisData {
  original_query: string;
  normalized_query: string;
  effective_query: string;
  intent: string;
  intent_reason: string;
  raw_tokens: string[];
  content_terms: string[];
  intent_terms: string[];
  grammatical_terms: string[];
  corrections: TypoCorrectionItem[];
  has_corrections: boolean;
  correction_confidence: string;
  effective_content_terms: string[];
  effective_stems: string[];
  quoted_phrases: string[];
}

export interface RejectedCandidate {
  doc_id: string;
  slug: string;
  title: string;
  passed: boolean;
  reason: string;
  matched_content_terms: string[];
}

export interface HybridTraceData {
  retrieval_mode: string;
  lexical_candidates_count: number;
  semantic_candidates_count: number;
  fused_candidates_count: number;
  semantic_rescues_count: number;
  rescued_slugs: string[];
}

export interface SearchTimingBreakdown {
  query_analysis_ms: number;
  bm25f_retrieval_ms: number;
  dense_retrieval_ms: number;
  rrf_fusion_ms: number;
  evidence_gating_ms: number;
  ranking_scoring_ms: number;
  passage_scoring_ms: number;
  answer_extraction_ms: number;
  qa_shadow_ms?: number;
  neural_shadow_ms?: number;
  server_total_ms: number;
}

export interface AnswerRelevanceTrace {
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

export interface QATraceData {
  model: string;
  query: string;
  deterministic_answer?: string | null;
  shadow_answer?: string | null;
  is_answerable: boolean;
  confidence: number;
  start_confidence: number;
  end_confidence: number;
  source_passage?: string | null;
  source_doc_id?: string | null;
  source_slug?: string | null;
  start_char?: number | null;
  end_char?: number | null;
  agreement: string;
  execution_ms: number;
  qa_candidates?: number;
  qa_passages_budgeted?: number;
  qa_windows_created?: number;
  qa_forward_passes?: number;
  qa_cache_hit?: boolean;
  qa_early_exit?: boolean;
  model_reused?: boolean;
  torch_threads?: number;
  answer_relevance?: AnswerRelevanceTrace | null;
}

export interface SearchResponse {
  search_id?: string;
  boot_id?: string;
  index_versions?: Record<string,string>;
  query: string;
  effective_query: string;
  has_corrections: boolean;
  correction_confidence: string;
  corrections: TypoCorrectionItem[];
  query_analysis: QueryAnalysisData;
  rejected_candidates: RejectedCandidate[];
  hybrid_trace?: HybridTraceData;
  timing?: SearchTimingBreakdown;
  qa_trace?: QATraceData | null;
  neural_shadow_trace?: {
    model_id: string;
    checkpoint_hash: string;
    authority: string;
    status: string;
    candidates_budgeted: number;
    candidates_evaluated: number;
    search_context_id?: string;
    latency_ms?: number;
  } | null;
  total_results: number;
  took_ms: number;
  results: SearchResult[];
}

export interface SemanticDiagnostics {
  provider_name: string;
  model_name: string;
  vector_dimension: number;
  total_passages_indexed: number;
  total_documents_indexed: number;
  cache_hits: number;
  cache_misses: number;
  index_path: string;
  last_indexed_at: string;
}

export interface FAQItem {
  id: string;
  question: string;
  answer: string;
}

export interface DocumentData {
  id: string;
  slug: string;
  title: string;
  meta_description: string;
  content: string;
  headings: string[];
  keywords: string[];
  internal_links: string[];
  source_type: string;
  status: string;
  created_at: string;
  updated_at: string;
  indexed_at?: string | null;
  content_schema_version?: number;
  structured_content?: JSONContent | null;
  faqs?: FAQItem[];
  link_details?: {
    in_degree: number;
    out_degree: number;
    in_links: string[];
    out_links: string[];
    pagerank: number;
    authority_score: number;
  };
}

export interface ComparativeExplain {
  winner_slug: string;
  winner_title: string;
  winner_score: number;
  loser_slug: string;
  loser_title: string;
  loser_score: number;
  score_difference: number;
  decisive_factors: string[];
  signal_comparison: Record<string, { winner: number; loser: number }>;
}

export interface EngineStats {
  total_documents: number;
  total_passages: number;
  total_terms: number;
  avg_field_lengths: Record<string, number>;
  graph_nodes: number;
  graph_edges: number;
}

export interface BenchmarkSummary {
  total_queries: number;
  mrr: number;
  mean_precision_at_1: number;
  mean_precision_at_3: number;
  mean_recall_at_3: number;
  hit_at_1_rate: number;
  hit_at_3_rate: number;
  hit_at_5_rate: number;
  passage_extraction_accuracy: number;
  passage_evaluated_queries: number;
  spam_violations: number;
  detailed_results: Array<{
    query: string;
    cluster: string;
    top_result: string | null;
    top_score: number;
    reciprocal_rank: number;
    precision_at_1: number;
    hit_at_1: boolean;
    hit_at_3: boolean;
    passage_hit: boolean | null;
  }>;
}

export function getOrCreateSessionId(): string {
  if (typeof window === "undefined") return "ssr-session";
  let sid = window.localStorage.getItem("pese_session_id");
  if (!sid) {
    sid = `pese-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    window.localStorage.setItem("pese_session_id", sid);
  }
  return sid;
}

export async function searchDocuments(
  query: string,
  debug: boolean = true,
  limit: number = 20,
  forceRaw: boolean = false,
  sessionId?: string,
  mode: string = "hybrid",
  signal?: AbortSignal
): Promise<SearchResponse> {
  const sid = sessionId || (typeof window !== "undefined" ? getOrCreateSessionId() : undefined);
  const params = new URLSearchParams({
    q: query,
    debug: String(debug),
    limit: String(limit),
    force_raw: String(forceRaw),
    mode,
  });
  if (sid) {
    params.set("session_id", sid);
  }
  const res = await apiFetch(`${API_BASE}/api/search?${params.toString()}`, {
    cache: "no-store", signal,
  });
  if (!res.ok) {
    throw new Error(`Search failed: ${res.statusText}`);
  }
  return res.json();
}

export async function explainRanking(
  query: string,
  winner: string,
  loser: string
): Promise<ComparativeExplain> {
  const params = new URLSearchParams({ q: query, winner, loser });
  const res = await apiFetch(`${API_BASE}/api/explain?${params.toString()}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Explain failed: ${res.statusText}`);
  }
  return res.json();
}

export async function getEngineStats(): Promise<EngineStats> {
  const res = await apiFetch(`${API_BASE}/api/stats`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error("Failed to load engine stats");
  }
  return res.json();
}

export async function getDocuments(status?: string): Promise<DocumentData[]> {
  const url = status
    ? `${API_BASE}/api/documents?status=${status}`
    : `${API_BASE}/api/documents`;
  const res = await apiFetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error("Failed to load documents");
  }
  return res.json();
}

export async function getDocumentBySlug(slug: string): Promise<DocumentData> {
  const res = await apiFetch(`${API_BASE}/api/documents/${slug}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Document not found: ${slug}`);
  }
  return res.json();
}

export async function saveDocument(doc: Partial<DocumentData>): Promise<DocumentData> {
  const res = await apiFetch(`${API_BASE}/api/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(doc),
  });
  if (!res.ok) {
    throw new Error("Failed to save document");
  }
  return res.json();
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await apiFetch(`${API_BASE}/api/documents/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error("Failed to delete document");
  }
}

export async function reindexAll(): Promise<{status: string; documents_indexed?: number; passages_indexed?: number; took_ms?: number; count?: number}> {
  const res = await apiFetch(`${API_BASE}/api/index`, { method: "POST" });
  if (!res.ok) {
    throw new Error("Failed to trigger reindex");
  }
  return res.json();
}

export async function reseedCorpus(): Promise<{status: string; documents_indexed?: number; passages_indexed?: number; took_ms?: number; count?: number}> {
  const res = await apiFetch(`${API_BASE}/api/seed`, { method: "POST" });
  if (!res.ok) {
    throw new Error("Failed to reseed corpus");
  }
  return res.json();
}

export interface DiscoveryBenchmarkSummary {
  benchmark_timestamp: string;
  total_autocomplete_cases: number;
  autocomplete_mrr: number;
  autocomplete_p_at_1: number;
  autocomplete_p_at_3: number;
  typo_recovery_rate: number;
  total_related_queries: number;
  related_search_accuracy: number;
  total_paa_cases: number;
  paa_answerability_precision: number;
  paa_duplicate_violations: number;
  cold_start_top_suggestion: string | null;
  warm_state_top_suggestion: string | null;
  doc_ranking_uncontaminated: boolean;
  autocomplete_details: Array<unknown>;
  related_details: Array<unknown>;
  paa_details: Array<unknown>;
}

export async function runBenchmark(): Promise<BenchmarkSummary> {
  const res = await apiFetch(`${API_BASE}/api/benchmark`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error("Failed to run benchmark");
  }
  return res.json();
}

export async function runDiscoveryBenchmark(): Promise<DiscoveryBenchmarkSummary> {
  const res = await apiFetch(`${API_BASE}/api/discovery/benchmark`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error("Failed to run discovery benchmark");
  }
  return res.json();
}

export async function sendTelemetryEvent(
  eventType: string,
  data: Record<string, unknown> = {}
): Promise<void> {
  try {
    const sid = typeof window !== "undefined" ? getOrCreateSessionId() : undefined;
    await apiFetch(`${API_BASE}/api/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_type: eventType,
        session_id: sid,
        ...data,
      }),
    });
  } catch (err) {
    // Non-blocking telemetry
    console.debug("Telemetry error:", err);
  }
}

export async function getSuggestions(
  prefix: string,
  sessionId?: string,
  limit: number = 6,
  debug: boolean = false,
  signal?: AbortSignal
): Promise<SuggestResponse> {
  const sid = sessionId || (typeof window !== "undefined" ? getOrCreateSessionId() : undefined);
  const params = new URLSearchParams({
    q: prefix,
    limit: String(limit),
    debug: String(debug),
  });
  if (sid) params.set("session_id", sid);

  const res = await apiFetch(`${API_BASE}/api/suggest?${params.toString()}`, {
    cache: "no-store", signal,
  });
  if (!res.ok) {
    throw new Error(`Failed to load suggestions: ${res.statusText}`);
  }
  return res.json();
}

export async function getRelatedSearches(
  query: string,
  sessionId?: string,
  limit: number = 5,
  debug: boolean = false,
  signal?: AbortSignal,
  searchId?: string
): Promise<RelatedSearchesResponse> {
  const sid = sessionId || (typeof window !== "undefined" ? getOrCreateSessionId() : undefined);
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    debug: String(debug),
  });
  if (sid) params.set("session_id", sid);
  if (searchId) params.set("search_id", searchId);

  const res = await apiFetch(`${API_BASE}/api/related?${params.toString()}`, {
    cache: "no-store", signal,
  });
  if (!res.ok) {
    throw new Error(`Failed to load related searches: ${res.statusText}`);
  }
  return res.json();
}

export async function getPAAQuestions(
  query: string,
  sessionId?: string,
  limit: number = 4,
  debug: boolean = false,
  signal?: AbortSignal,
  searchId?: string
): Promise<QuestionsResponse> {
  const sid = sessionId || (typeof window !== "undefined" ? getOrCreateSessionId() : undefined);
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    debug: String(debug),
  });
  if (sid) params.set("session_id", sid);
  if (searchId) params.set("search_id", searchId);

  const res = await apiFetch(`${API_BASE}/api/questions?${params.toString()}`, {
    cache: "no-store", signal,
  });
  if (!res.ok) {
    throw new Error(`Failed to load PAA questions: ${res.statusText}`);
  }
  return res.json();
}

export async function sendSessionEvent(
  eventType: string,
  data: Record<string, unknown> = {}
): Promise<void> {
  try {
    const sid = typeof window !== "undefined" ? getOrCreateSessionId() : "default-session";
    await apiFetch(`${API_BASE}/api/session/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sid,
        event_type: eventType,
        ...data,
      }),
    });
  } catch (err) {
    console.debug("Session event error:", err);
  }
}

export async function getSearchHistory(
  limit: number = 15,
  sessionId?: string
): Promise<HistoryResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (sessionId) params.set("session_id", sessionId);

  const res = await apiFetch(`${API_BASE}/api/history?${params.toString()}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error("Failed to load search history");
  }
  return res.json();
}

export async function clearSearchHistory(): Promise<void> {
  const res = await apiFetch(`${API_BASE}/api/history`, { method: "DELETE" });
  if (!res.ok) {
    throw new Error("Failed to clear search history");
  }
}

export async function updateHistorySettings(enabled: boolean): Promise<boolean> {
  const res = await apiFetch(`${API_BASE}/api/history/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ history_enabled: enabled }),
  });
  if (!res.ok) {
    throw new Error("Failed to update history settings");
  }
  const data = await res.json();
  return data.history_enabled;
}

export async function getSemanticDiagnostics(): Promise<SemanticDiagnostics> {
  const res = await apiFetch(`${API_BASE}/api/semantic/diagnostics`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error("Failed to load semantic diagnostics");
  }
  return res.json();
}

export async function reindexSemantic(): Promise<{ status: string; took_ms: number; diagnostics: SemanticDiagnostics }> {
  const res = await apiFetch(`${API_BASE}/api/semantic/reindex`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error("Failed to reindex semantic vectors");
  }
  return res.json();
}

// ==================== NEURAL GENESIS API ====================

export interface NeuralModelCard {
  model_id: string;
  architecture: string;
  status: "experiment" | "candidate" | "approved" | "archived";
  description: string;
  config: Record<string, number | string>;
  total_parameters: number;
  allowed_for_ranking: boolean;
  allowed_for_answers: boolean;
  registered_at: string;
  checkpoint_path?: string | null;
  notes: string[];
}

export interface NeuralReport {
  title: string;
  timestamp: string;
  device: string;
  pytorch_version: string;
  privacy_guarantee: string;
  micro_overfit_experiment: {
    status: string;
    initial_loss: number;
    final_loss: number;
    loss_reduction_pct: number;
    steps_completed: number;
    threshold_pct: number;
    history: Array<{ step: number; epoch: number; loss: number; learning_rate: number; grad_norm: number }>;
  };
  baseline_experiment: {
    model_summary: {
      model_name: string;
      vocab_size: number;
      d_model: number;
      n_layers: number;
      n_heads: number;
      d_ff: number;
      max_seq_len: number;
      dropout: number;
      total_parameters: number;
      parameter_breakdown: Record<string, number>;
    };
    tokenizer: {
      name: string;
      vocab_size: number;
      merges_count: number;
    };
    train_results: {
      experiment_name: string;
      initial_loss: number;
      final_loss: number;
      loss_reduction_pct: number;
      steps_completed: number;
      duration_seconds: number;
      saved_checkpoints: string[];
      history: Array<{ step: number; epoch: number; loss: number; val_loss?: number; learning_rate: number; grad_norm: number }>;
    };
    sample_generations: Array<{
      prompt: string;
      generated_text: string;
      full_text: string;
      tokens_generated: number;
      temperature: number;
      model_name: string;
      experimental: boolean;
      disclaimer: string;
    }>;
    checkpoint: string;
  };
  documented_weaknesses: Array<{
    id: string;
    title: string;
    description: string;
  }>;
  checkpoints: string[];
}

export interface CheckpointItem {
  filename: string;
  filepath: string;
  model_name: string;
  step: number;
  loss: number;
  saved_at: string;
  size_bytes: number;
}

export interface QAContractItem {
  id: string;
  question: string;
  context: string;
  answer_text?: string | null;
  answer_start_char?: number | null;
  answer_end_char?: number | null;
  is_answerable: boolean;
  abstention_reason?: string | null;
  source_doc_id?: string | null;
}

export async function getNeuralRegistry(): Promise<{ models: NeuralModelCard[] }> {
  const res = await apiFetch(`${API_BASE}/api/neural/registry`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load neural registry");
  return res.json();
}

export async function getNeuralExperiments(): Promise<NeuralReport> {
  const res = await apiFetch(`${API_BASE}/api/neural/experiments`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load neural experiments");
  return res.json();
}

export async function getNeuralCheckpoints(): Promise<{ checkpoints: CheckpointItem[] }> {
  const res = await apiFetch(`${API_BASE}/api/neural/checkpoints`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load neural checkpoints");
  return res.json();
}

export async function getQAContracts(): Promise<{ count: number; contracts: QAContractItem[] }> {
  const res = await apiFetch(`${API_BASE}/api/neural/qa-contracts`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load QA contracts");
  return res.json();
}

export async function generateNeuralText(
  prompt: string,
  maxNewTokens: number = 20,
  temperature: number = 0.8
): Promise<{
  prompt: string;
  generated_text: string;
  full_text: string;
  tokens_generated: number;
  temperature: number;
  model_name: string;
  experimental: boolean;
  disclaimer: string;
}> {
  const res = await apiFetch(`${API_BASE}/api/neural/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, max_new_tokens: maxNewTokens, temperature, top_k: 40 }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Neural generation failed");
  }
  return res.json();
}

export interface QAReadResult {
  answer: string | null;
  answerable: boolean;
  answer_confidence: number;
  start_confidence: number;
  end_confidence: number;
  start_char: number | null;
  end_char: number | null;
  start_token: number | null;
  end_token: number | null;
  source_passage: string;
  source_doc_id?: string | null;
  source_slug?: string | null;
  model: string;
  abstention_reason?: string | null;
  trace: {p_answerable?: number; [key: string]: unknown};
}

export interface QAReport {
  status: string;
  stage_a?: Record<string, unknown>;
  stage_b?: Record<string, unknown>;
  stage_c?: Record<string, unknown>;
  evaluation?: {
    total_evaluated: number;
    exact_match: number;
    token_f1: number;
    answerability_accuracy: number;
    no_answer_f1: number;
    hallucination_rate: number;
  };
  model_card?: Record<string, unknown>;
  generated_at?: string;
}

export async function getQAReport(): Promise<QAReport> {
  const res = await apiFetch(`${API_BASE}/api/neural/qa/report`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load QA report");
  return res.json();
}

export async function readQAPassage(
  question: string,
  passage: string
): Promise<QAReadResult> {
  const res = await apiFetch(`${API_BASE}/api/neural/qa/read`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, passage }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "QA reading failed");
  }
  return res.json();
}


// Search Sync Feedback (Phase N3-A)
export interface FeedbackSubmission {
  search_context_id?: string | null;
  query: string;
  target_type: "SERP_RESULT" | "FEATURED_ANSWER";
  target_id: string;
  target_slug?: string | null;
  rank_position?: number | null;
  feedback: "LIKE" | "DISLIKE";
  reason?: string | null;
  metadata?: Record<string, unknown>;
}

export async function sendSearchFeedback(submission: FeedbackSubmission): Promise<{
  status: string;
  event_id: string;
  search_sync_adjustment: number;
}> {
  const res = await apiFetch(`${API_BASE}/api/search/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(submission),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to submit search feedback");
  }
  return res.json();
}

// Phase N3-B: Neural Shadow Bridge Inspection
export async function getNeuralShadowRecords(query?: string): Promise<{
  model_id: string;
  authority: string;
  total_records: number;
  records: Array<{
    search_context_id: string;
    query: string;
    target_id: string;
    target_slug?: string;
    rank_position?: number;
    maae_base_score?: number;
    human_feedback?: string;
    reason?: string;
    evidence_id?: string;
    evidence_summary?: string;
    answers_probability?: number;
    predicted_label?: string;
    diagnostic_alignment?: string;
  }>;
}> {
  const params = query ? `?q=${encodeURIComponent(query)}` : "";
  const res = await apiFetch(`${API_BASE}/api/search/neural-shadow${params}`);
  if (!res.ok) throw new Error("Failed to fetch neural shadow records");
  return res.json();
}

export async function getNeuralShadowStats(): Promise<{
  total_observations: number;
  mean_p_answers: number;
  high_confidence_answers_count: number;
  high_confidence_does_not_answer_count: number;
  linked_feedback_count: number;
  neural_human_agreements: number;
  neural_human_disagreements: number;
  model_authority: string;
}> {
  const res = await apiFetch(`${API_BASE}/api/search/neural-shadow/stats`);
  if (!res.ok) throw new Error("Failed to fetch neural shadow stats");
  return res.json();
}

export interface BrainInfoData {
  brain_id: string;
  schema_version: number;
  created_at: string;
  name?: string | null;
  path: string;
  status: string;
  document_count: number;
  has_feedback_db?: boolean;
  has_privacy_settings?: boolean;
  has_history_log?: boolean;
}

export async function getBrainInfo(): Promise<BrainInfoData> {
  const res = await apiFetch(`${API_BASE}/api/brain/info`);
  if (!res.ok) throw new Error("Failed to fetch Brain info");
  return res.json();
}

export interface UserProfileData {
  schema_version: number;
  display_name: string;
  about: string;
  avatar: { relative_path?: string } | null;
  updated_at: string;
}

export async function getUserProfile(): Promise<UserProfileData> {
  const res = await apiFetch(`${API_BASE}/api/profile`);
  if (!res.ok) throw new Error("Failed to fetch user profile");
  return res.json();
}

export async function updateUserProfile(displayName: string, about: string): Promise<UserProfileData> {
  const res = await apiFetch(`${API_BASE}/api/profile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_name: displayName, about }),
  });
  if (!res.ok) throw new Error("Failed to update user profile");
  return res.json();
}

export async function uploadUserAvatar(imageBase64: string, filename?: string): Promise<UserProfileData> {
  const res = await apiFetch(`${API_BASE}/api/profile/avatar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_base64: imageBase64, filename: filename || "avatar.png" }),
  });
  if (!res.ok) throw new Error("Failed to upload avatar");
  return res.json();
}

export async function deleteUserAvatar(): Promise<UserProfileData> {
  const res = await apiFetch(`${API_BASE}/api/profile/avatar`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete avatar");
  return res.json();
}

export function getUserAvatarUrl(): string {
  return `${getApiBase()}/api/profile/avatar`;
}

// ==================== GOOGLE DRIVE SYNC ====================

export type SyncStatusType = "not_configured" | "not_connected" | "connecting" | "connected" | "syncing" | "error";

export interface SyncStatusData {
  configured: boolean;
  connected: boolean;
  status: SyncStatusType;
  account_email?: string | null;
  last_synced_at?: string | null;
  latest_snapshot_id?: string | null;
  latest_snapshot_time?: string | null;
  restore_enabled: boolean;
  restore_disabled_reason: string;
  message?: string | null;
}

export interface SyncSnapshotItem {
  id: string;
  name: string;
  created_time: string;
  size_bytes?: number | null;
  brain_id?: string | null;
  snapshot_id?: string | null;
  compatible?: boolean;
  local_changes?: boolean;
  archive_sha256?: string | null;
}

export async function getSyncStatus(): Promise<SyncStatusData> {
  const res = await apiFetch(`${API_BASE}/api/sync/status`);
  if (!res.ok) throw new Error("Failed to fetch Google Drive sync status");
  return res.json();
}

export async function startSyncConnect(): Promise<{ status: string; auth_url?: string; port?: number; message?: string }> {
  const res = await apiFetch(`${API_BASE}/api/sync/connect`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to start Google Drive connection");
  }
  return res.json();
}

export async function disconnectSync(): Promise<{ ok: boolean; message: string }> {
  const res = await apiFetch(`${API_BASE}/api/sync/disconnect`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to disconnect Google Drive");
  return res.json();
}

export async function syncNow(): Promise<{ ok: boolean; snapshot_id: string; drive_file_id: string; last_synced_at: string; message: string }> {
  const res = await apiFetch(`${API_BASE}/api/sync/now`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Google Drive sync failed");
  }
  return res.json();
}

export async function restoreFromSync(snapshotId?: string): Promise<{ success: boolean; brain_id: string; snapshot_id: string; restored_at: string; backup_path?: string; files_restored: number; message: string }> {
  const res = await apiFetch(`${API_BASE}/api/sync/restore`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ snapshot_id: snapshotId || null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Restore from Google Drive failed");
  }
  return res.json();
}

export async function getSyncSnapshots(): Promise<{ snapshots: SyncSnapshotItem[] }> {
  const res = await apiFetch(`${API_BASE}/api/sync/snapshots`);
  if (!res.ok) throw new Error("Failed to list Google Drive snapshots");
  return res.json();
}
