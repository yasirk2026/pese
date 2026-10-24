"use client";

import React from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { RelatedSearchItem, sendSessionEvent, sendTelemetryEvent } from "@/lib/api";

interface RelatedSearchesProps {
  relatedSearches: RelatedSearchItem[];
  currentQuery: string;
}

export const RelatedSearches: React.FC<RelatedSearchesProps> = ({
  relatedSearches,
  currentQuery,
}) => {
  if (!relatedSearches || relatedSearches.length === 0) {
    return null;
  }

  const handleRelatedClick = (item: RelatedSearchItem, index: number) => {
    sendSessionEvent("related_search_selected", {
      query: currentQuery,
      selected_related_query: item.query,
      selection_position: index + 1,
    });
    sendTelemetryEvent("related_search_selected", {
      query: currentQuery,
      target_query: item.query,
      rank_position: index + 1,
    });
  };

  return (
    <section aria-label="Related Searches" className="mt-12 pt-6 border-t border-neutral-200 dark:border-neutral-800">
      <div className="flex items-center gap-2 mb-4 text-neutral-900 dark:text-neutral-100">
        <Search className="w-4 h-4 text-neutral-500" />
        <h3 className="text-base font-semibold">Related Searches</h3>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {relatedSearches.map((item, idx) => (
          <Link
            key={`${item.query}-${idx}`}
            href={`/search?q=${encodeURIComponent(item.query)}`}
            onClick={() => handleRelatedClick(item, idx)}
            className="flex items-center gap-3 px-4 py-2.5 rounded-full bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-900 dark:hover:bg-neutral-800 text-sm text-neutral-800 dark:text-neutral-200 transition-colors group"
          >
            <Search className="w-3.5 h-3.5 text-neutral-400 group-hover:text-neutral-700 dark:group-hover:text-neutral-200 shrink-0" />
            <span className="truncate group-hover:underline">{item.query}</span>
          </Link>
        ))}
      </div>
    </section>
  );
};
