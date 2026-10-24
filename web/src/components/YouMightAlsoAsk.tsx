"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ChevronDown, HelpCircle, ArrowUpRight, Search } from "lucide-react";
import { PAAQuestionItem, sendSessionEvent, sendTelemetryEvent } from "@/lib/api";

interface YouMightAlsoAskProps {
  questions: PAAQuestionItem[];
  currentQuery: string;
}

export const YouMightAlsoAsk: React.FC<YouMightAlsoAskProps> = ({
  questions,
  currentQuery,
}) => {
  const [openIndexes, setOpenIndexes] = useState<Set<number>>(new Set());

  if (!questions || questions.length === 0) {
    return null;
  }

  const toggleAccordion = (index: number, question: PAAQuestionItem) => {
    setOpenIndexes((prev) => {
      const next = new Set(prev);
      const isOpening = !next.has(index);
      if (isOpening) {
        next.add(index);
        // Telemetry
        sendSessionEvent("paa_opened", {
          query: currentQuery,
          paa_question: question.question,
          source_slug: question.source_slug,
        });
        sendTelemetryEvent("paa_opened", {
          query: currentQuery,
          question: question.question,
        });
      } else {
        next.delete(index);
      }
      return next;
    });
  };

  const handleSourceClick = (question: PAAQuestionItem) => {
    sendSessionEvent("paa_source_clicked", {
      query: currentQuery,
      paa_question: question.question,
      target_slug: question.source_slug,
    });
  };

  return (
    <section
      aria-label="You Might Also Ask"
      className="my-6 border border-neutral-200 dark:border-neutral-800 rounded-xl overflow-hidden bg-white dark:bg-neutral-900/60 shadow-xs"
    >
      {/* Header */}
      <div className="px-5 py-3 border-b border-neutral-200 dark:border-neutral-800 flex items-center justify-between bg-neutral-50 dark:bg-neutral-900/90">
        <div className="flex items-center gap-2">
          <HelpCircle className="w-4 h-4 text-blue-500 dark:text-blue-400" />
          <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
            You Might Also Ask
          </h3>
        </div>
        <span className="text-[11px] font-mono text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">
          Grounded Answers
        </span>
      </div>

      {/* Accordion Questions List */}
      <div className="divide-y divide-neutral-200 dark:divide-neutral-800">
        {questions.map((item, idx) => {
          const isOpen = openIndexes.has(idx);
          const contentId = `paa-content-${idx}`;
          const buttonId = `paa-button-${idx}`;

          return (
            <div key={`${item.question}-${idx}`} className="transition-colors">
              {/* Question Trigger */}
              <button
                id={buttonId}
                aria-expanded={isOpen}
                aria-controls={contentId}
                onClick={() => toggleAccordion(idx, item)}
                className="w-full px-5 py-3.5 flex items-center justify-between text-left hover:bg-neutral-50 dark:hover:bg-neutral-800/50 transition-colors focus:outline-none focus-visible:bg-neutral-100 dark:focus-visible:bg-neutral-800 cursor-pointer"
              >
                <span className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                  {item.question}
                </span>
                <ChevronDown
                  className={`w-4 h-4 text-neutral-500 dark:text-neutral-400 transition-transform duration-200 shrink-0 ml-3 ${
                    isOpen ? "rotate-180" : ""
                  }`}
                />
              </button>

              {/* Collapsible Answer Body */}
              {isOpen && (
                <div
                  id={contentId}
                  role="region"
                  aria-labelledby={buttonId}
                  className="px-5 pb-4 pt-1 text-sm bg-neutral-50/50 dark:bg-neutral-950/60"
                >
                  {/* Extracted Direct Answer with High Contrast Dark Theme Support */}
                  <div className="py-3 px-4 rounded-lg bg-neutral-100/90 dark:bg-neutral-800/90 border border-neutral-200 dark:border-neutral-700 shadow-2xs">
                    <div className="text-neutral-900 dark:text-neutral-100 font-normal leading-relaxed text-sm">
                      {item.answer}
                    </div>
                  </div>

                  {/* Grounded Source Reference & Direct Search */}
                  <div className="mt-3 pt-2 border-t border-neutral-200 dark:border-neutral-800/80 flex flex-wrap items-center justify-between gap-2 text-xs">
                    <Link
                      href={`/doc?slug=${encodeURIComponent(item.source_slug)}`}
                      onClick={() => handleSourceClick(item)}
                      className="text-rose-600 dark:text-rose-400 hover:underline flex items-center gap-1 font-medium"
                    >
                      <span>Extracted from: {item.source_title}</span>
                      <ArrowUpRight className="w-3.5 h-3.5" />
                    </Link>

                    <Link
                      href={`/search?q=${encodeURIComponent(item.question)}`}
                      className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 flex items-center gap-1 font-mono text-[11px]"
                    >
                      <Search className="w-3 h-3" />
                      <span>Search this question</span>
                    </Link>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
};
