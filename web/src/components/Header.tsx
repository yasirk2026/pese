"use client";

import React, { useState } from "react";
import Link from "next/link";
import { History, ShieldCheck } from "lucide-react";
import { PeseLogo } from "./PeseLogo";
import { SearchAutocomplete } from "./SearchAutocomplete";
import { HistoryPrivacyModal } from "./HistoryPrivacyModal";

interface HeaderProps {
  initialQuery?: string;
  showSearchBar?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  initialQuery = "",
  showSearchBar = true,
}) => {
  const [isHistoryModalOpen, setIsHistoryModalOpen] = useState(false);

  return (
    <>
      <header className="border-b border-surface-border bg-background/80 dark:bg-background/80 backdrop-blur-md sticky top-0 z-30 transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">
          {/* Left: Brand Identity */}
          <div className="flex items-center gap-4">
            <Link href="/" className="flex items-center gap-2 group">
              <PeseLogo size="sm" showWordmark={true} />
            </Link>
          </div>

          {/* Center: Search Autocomplete input */}
          {showSearchBar && (
            <div className="flex-1 max-w-xl mx-2">
              <SearchAutocomplete key={initialQuery} initialQuery={initialQuery} size="medium" />
            </div>
          )}

          {/* Right Utilities */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsHistoryModalOpen(true)}
              title="Search History & Privacy"
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-neutral-600 dark:text-neutral-300 hover:bg-neutral-200/60 dark:hover:bg-neutral-800/60 transition-colors cursor-pointer"
            >
              <History className="w-3.5 h-3.5 text-neutral-500" />
              <span className="hidden sm:inline">History</span>
            </button>

            <div className="h-4 w-px bg-neutral-200 dark:bg-neutral-800 hidden sm:block" />

            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-neutral-100 dark:bg-neutral-800/80 border border-neutral-200 dark:border-neutral-700/60 text-[11px] font-mono text-neutral-600 dark:text-neutral-400">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
              <span>Local Brain</span>
            </span>
          </div>
        </div>
      </header>

      {/* History & Privacy Modal */}
      <HistoryPrivacyModal
        isOpen={isHistoryModalOpen}
        onClose={() => setIsHistoryModalOpen(false)}
      />
    </>
  );
};
