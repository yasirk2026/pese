"use client";

import React, { useState } from "react";
import { ThumbsUp, ThumbsDown, Check, X } from "lucide-react";
import { sendSearchFeedback, FeedbackSubmission } from "@/lib/api";

const REASONS = [
  "Wrong result",
  "Irrelevant",
  "Outdated",
  "Wrong source",
  "Didn't answer my query",
  "Other",
];

interface SearchFeedbackControlsProps {
  query: string;
  targetType: "SERP_RESULT" | "FEATURED_ANSWER";
  targetId: string;
  targetSlug?: string | null;
  rankPosition?: number | null;
  initialFeedback?: "LIKE" | "DISLIKE" | null;
  searchContextId?: string | null;
  size?: "small" | "normal";
  className?: string;
}

export function SearchFeedbackControls({
  query,
  targetType,
  targetId,
  targetSlug,
  rankPosition,
  initialFeedback = null,
  searchContextId = null,
  size = "small",
  className = "",
}: SearchFeedbackControlsProps) {
  const [activeFeedback, setActiveFeedback] = useState<"LIKE" | "DISLIKE" | null>(initialFeedback);
  const [selectedReason, setSelectedReason] = useState<string | null>(null);
  const [showReasonPicker, setShowReasonPicker] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);

  const handleVote = async (feedback: "LIKE" | "DISLIKE") => {
    // If user clicks the same vote again, keep it active (idempotent)
    const newFeedback = feedback;
    setActiveFeedback(newFeedback);
    setSelectedReason(null);

    if (newFeedback === "DISLIKE") {
      setShowReasonPicker(true);
    } else {
      setShowReasonPicker(false);
    }

    try {
      setSubmitting(true);
      const submission: FeedbackSubmission = {
        search_context_id: searchContextId,
        query,
        target_type: targetType,
        target_id: targetId,
        target_slug: targetSlug,
        rank_position: rankPosition,
        feedback: newFeedback,
        reason: null,
      };
      await sendSearchFeedback(submission);
    } catch (err) {
      console.warn("Search Sync feedback submission error:", err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleReasonSelect = async (reason: string) => {
    setSelectedReason(reason);
    try {
      setSubmitting(true);
      const submission: FeedbackSubmission = {
        search_context_id: searchContextId,
        query,
        target_type: targetType,
        target_id: targetId,
        target_slug: targetSlug,
        rank_position: rankPosition,
        feedback: "DISLIKE",
        reason,
      };
      await sendSearchFeedback(submission);
    } catch (err) {
      console.warn("Search Sync feedback reason submission error:", err);
    } finally {
      setSubmitting(false);
    }
  };

  const isSmall = size === "small";

  return (
    <div
      className={`inline-flex flex-col gap-1.5 ${className}`}
      data-testid="search-sync-feedback-controls"
      data-target-id={targetId}
      data-feedback-state={activeFeedback || "NONE"}
    >
      <div className="inline-flex items-center gap-1">
        {/* LIKE BUTTON */}
        <button
          type="button"
          onClick={() => handleVote("LIKE")}
          disabled={submitting}
          aria-label="Helpful"
          title="Helpful result (Search Sync 👍)"
          className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-mono transition-colors border select-none cursor-pointer ${
            activeFeedback === "LIKE"
              ? "bg-emerald-950/80 border-emerald-500 text-emerald-300 font-semibold shadow-sm"
              : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700"
          } ${isSmall ? "text-[11px]" : "text-xs"}`}
        >
          <ThumbsUp className={`${isSmall ? "w-3 h-3" : "w-3.5 h-3.5"} ${activeFeedback === "LIKE" ? "text-emerald-400 fill-emerald-400/20" : ""}`} />
          {activeFeedback === "LIKE" && <span className="text-[10px] text-emerald-400">Preferred</span>}
        </button>

        {/* DISLIKE BUTTON */}
        <button
          type="button"
          onClick={() => handleVote("DISLIKE")}
          disabled={submitting}
          aria-label="Not helpful"
          title="Not helpful (Search Sync 👎)"
          className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-mono transition-colors border select-none cursor-pointer ${
            activeFeedback === "DISLIKE"
              ? "bg-rose-950/80 border-rose-500 text-rose-300 font-semibold shadow-sm"
              : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700"
          } ${isSmall ? "text-[11px]" : "text-xs"}`}
        >
          <ThumbsDown className={`${isSmall ? "w-3 h-3" : "w-3.5 h-3.5"} ${activeFeedback === "DISLIKE" ? "text-rose-400 fill-rose-400/20" : ""}`} />
          {activeFeedback === "DISLIKE" && <span className="text-[10px] text-rose-400">Rejected</span>}
        </button>
      </div>

      {/* OPTIONAL REASON CHIPS ONLY AFTER DISLIKE (Section 6) */}
      {showReasonPicker && activeFeedback === "DISLIKE" && (
        <div className="flex flex-wrap items-center gap-1 pt-1 animate-in fade-in duration-150">
          <span className="text-[10px] text-slate-400 font-mono mr-1">Optional reason:</span>
          {REASONS.map((r) => {
            const isSelected = selectedReason === r;
            return (
              <button
                key={r}
                type="button"
                onClick={() => handleReasonSelect(r)}
                className={`text-[10px] px-1.5 py-0.5 rounded border transition-colors cursor-pointer ${
                  isSelected
                    ? "bg-rose-900/60 border-rose-400 text-rose-200 font-medium"
                    : "bg-slate-900/80 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700"
                }`}
              >
                {isSelected && <Check className="w-2.5 h-2.5 inline mr-0.5 text-rose-300" />}
                {r}
              </button>
            );
          })}
          <button
            type="button"
            onClick={() => setShowReasonPicker(false)}
            aria-label="Dismiss reasons"
            className="text-slate-500 hover:text-slate-300 p-0.5 ml-0.5 cursor-pointer"
          >
            <X className="w-2.5 h-2.5" />
          </button>
        </div>
      )}
    </div>
  );
}
