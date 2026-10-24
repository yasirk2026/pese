"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getEngineStats, EngineStats, sendTelemetryEvent } from "@/lib/api";
import { SearchAutocomplete } from "@/components/SearchAutocomplete";
import { AppShell } from "@/components/AppShell";
import { PeseLogoMark } from "@/components/PeseLogo";
import { Compass, ShieldCheck } from "lucide-react";

export default function SearchHomePage() {
  const [stats, setStats] = useState<EngineStats | null>(null);
  const router = useRouter();

  useEffect(() => {
    getEngineStats()
      .then(setStats)
      .catch(() => console.debug("Engine initializing..."));
  }, []);

  const handleQuickSearch = () => {
    const clean = "when did I buy my bicycle";
    sendTelemetryEvent("quick_search_click", { query: clean });
    router.push(`/search?q=${encodeURIComponent(clean)}`);
  };

  return (
    <AppShell noPadding={true}>
      <div className="h-full flex flex-col justify-between p-6 sm:p-12 max-w-4xl mx-auto w-full">
        {/* Top: Subtle Brain Custody Status */}
        <div className="flex justify-end items-center">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono text-neutral-500 bg-neutral-100 dark:bg-neutral-900 border border-neutral-200/80 dark:border-neutral-800/80 shadow-2xs">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Brain Active</span>
          </div>
        </div>

        {/* Central Search Core — Search-First with Generous Breathing Room */}
        <div className="flex flex-col items-center justify-center my-auto w-full -mt-10 sm:-mt-16">
          {/* PESE Product Identity */}
          <div className="flex flex-col items-center mb-8 sm:mb-10 text-center select-none">
            <PeseLogoMark size={56} className="mb-4 drop-shadow-md hover:scale-105 transition-transform duration-300" />
            <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-neutral-900 dark:text-neutral-50 font-sans">
              PESE
            </h1>
            <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400 font-normal">
              Private, intelligent local search for your personal knowledge
            </p>
          </div>

          {/* Search Input Container */}
          <div className="w-full max-w-2xl">
            <SearchAutocomplete
              size="large"
              autoFocus={true}
              placeholder="Search notes, documents, journals, and personal knowledge..."
            />

            {/* Action Buttons */}
            <div className="mt-5 flex items-center justify-center gap-3">
              <button
                type="button"
                onClick={() => {
                  const input = document.querySelector('input[role="combobox"]') as HTMLInputElement;
                  if (input && input.value.trim()) {
                    router.push(`/search?q=${encodeURIComponent(input.value.trim())}`);
                  }
                }}
                className="px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium shadow-xs hover:shadow-sm transition-all active:scale-[0.98] cursor-pointer"
              >
                Search
              </button>
              <button
                type="button"
                onClick={handleQuickSearch}
                className="px-5 py-2.5 rounded-xl bg-white dark:bg-neutral-900 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-800 dark:text-neutral-200 text-sm font-medium border border-neutral-300/80 dark:border-neutral-700/80 shadow-2xs transition-all active:scale-[0.98] flex items-center gap-2 cursor-pointer"
              >
                <Compass className="w-3.5 h-3.5 text-neutral-500" />
                <span>Quick Discovery</span>
              </button>
            </div>
          </div>
        </div>

        {/* Minimal, Honest Footer */}
        <footer className="pt-6 border-t border-neutral-200/80 dark:border-neutral-800/80 flex flex-col sm:flex-row items-center justify-between text-xs text-neutral-500 dark:text-neutral-400 gap-2">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
            <span>Local & Offline Custody</span>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono">
            {stats && (
              <span>
                {stats.total_documents} documents · {stats.total_passages} passages
              </span>
            )}
            <span>v0.1.0-alpha.3</span>
          </div>
        </footer>
      </div>
    </AppShell>
  );
}
