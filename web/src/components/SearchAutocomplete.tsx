"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, Sparkles, CornerDownLeft } from "lucide-react";
import {
  getSuggestions,
  AutocompleteSuggestion,
  sendSessionEvent,
  sendTelemetryEvent,
  getOrCreateSessionId,
} from "@/lib/api";

interface SearchAutocompleteProps {
  initialQuery?: string;
  placeholder?: string;
  autoFocus?: boolean;
  onSearchSubmit?: (query: string) => void;
  size?: "large" | "medium";
  className?: string;
  disabled?: boolean;
}

export const SearchAutocomplete: React.FC<SearchAutocompleteProps> = ({
  initialQuery = "",
  placeholder = "Search knowledge pages, notes, engineering, journals...",
  autoFocus = false,
  onSearchSubmit,
  size = "medium",
  className = "",
  disabled = false,
}) => {
  const [query, setQuery] = useState(initialQuery);
  const [suggestions, setSuggestions] = useState<AutocompleteSuggestion[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState<number>(-1);
  const [correctedPrefix, setCorrectedPrefix] = useState<string | null>(null);
  const [hasTypo, setHasTypo] = useState(false);

  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const suggestionGeneration = useRef(0);
  const suggestionAbort = useRef<AbortController | null>(null);

  useEffect(() => () => {
    suggestionGeneration.current += 1;
    suggestionAbort.current?.abort();
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
  }, []);

  useEffect(() => {
    if (autoFocus) {
      inputRef.current?.focus();
    }
  }, [autoFocus]);

  // Handle outside clicks to close dropdown
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Fetch suggestions with debounce
  const fetchSuggestions = useCallback((val: string) => {
    const generation = ++suggestionGeneration.current;
    suggestionAbort.current?.abort();
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    const clean = val.trim();
    if (!clean) {
      setSuggestions([]);
      setIsOpen(false);
      setCorrectedPrefix(null);
      setHasTypo(false);
      return;
    }

    debounceTimerRef.current = setTimeout(async () => {
      try {
        const sid = getOrCreateSessionId();
        const controller = new AbortController();
        suggestionAbort.current = controller;
        const data = await getSuggestions(clean, sid, 6, false, controller.signal);
        if (generation !== suggestionGeneration.current) return;
        setSuggestions(data.suggestions);
        setHasTypo(data.has_typo_correction);
        setCorrectedPrefix(data.corrected_prefix || null);
        setSelectedIndex(-1);
        if (data.suggestions.length > 0) {
          setIsOpen(true);
          // Telemetry
          sendSessionEvent("autocomplete_shown", {
            prefix: clean,
            suggestions_shown: data.suggestions.map((s) => s.text),
            has_typo: data.has_typo_correction,
          });
        } else {
          setIsOpen(false);
        }
      } catch (err) {
        console.debug("Autocomplete fetch failed:", err);
      }
    }, 150);
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    setSelectedIndex(-1);
    fetchSuggestions(val);
  };

  const executeSearch = (targetQuery: string, source: string = "manual", rankPos?: number) => {
    const clean = targetQuery.trim();
    if (!clean) return;

    setIsOpen(false);
    suggestionGeneration.current += 1;
    suggestionAbort.current?.abort();
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    if (source === "autocomplete" && rankPos !== undefined) {
      sendSessionEvent("autocomplete_selected", {
        prefix: query,
        selected_suggestion: clean,
        selection_position: rankPos,
      });
      sendTelemetryEvent("autocomplete_selected", {
        query: clean,
        rank_position: rankPos,
      });
    } else {
      sendSessionEvent("query_submitted", { query: clean });
      sendTelemetryEvent("query_submitted", { query: clean });
    }

    if (onSearchSubmit) {
      onSearchSubmit(clean);
    } else {
      router.push(`/search?q=${encodeURIComponent(clean)}`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!isOpen && suggestions.length > 0) {
        setIsOpen(true);
        return;
      }
      setSelectedIndex((prev) => (prev < suggestions.length - 1 ? prev + 1 : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : suggestions.length - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (isOpen && selectedIndex >= 0 && selectedIndex < suggestions.length) {
        executeSearch(suggestions[selectedIndex].text, "autocomplete", selectedIndex + 1);
      } else {
        executeSearch(query, "manual");
      }
    } else if (e.key === "Escape") {
      setIsOpen(false);
    }
  };

  const renderHighlightedText = (text: string, ranges: [number, number][]) => {
    if (!ranges || ranges.length === 0) {
      return <span>{text}</span>;
    }
    const [start, end] = ranges[0];
    const before = text.substring(0, start);
    const match = text.substring(start, end);
    const after = text.substring(end);

    return (
      <span>
        {before}
        <strong className="font-bold text-neutral-950 dark:text-neutral-50 underline decoration-neutral-300 dark:decoration-neutral-700 underline-offset-2">
          {match}
        </strong>
        {after}
      </span>
    );
  };

  const isLarge = size === "large";

  return (
    <div ref={containerRef} className={`relative w-full ${className}`}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          executeSearch(query, "manual");
        }}
        className="w-full"
      >
        <div className="relative group">
          <div
            className={`absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-neutral-400 group-focus-within:text-neutral-700 dark:group-focus-within:text-neutral-200 transition-colors`}
          >
            <Search className={isLarge ? "w-5 h-5" : "w-4 h-4"} />
          </div>

          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={isOpen}
            aria-controls="autocomplete-dropdown"
            aria-activedescendant={
              selectedIndex >= 0 ? `suggestion-item-${selectedIndex}` : undefined
            }
            value={query}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onFocus={() => {
              if (suggestions.length > 0 && query.trim()) setIsOpen(true);
            }}
            disabled={disabled}
            placeholder={placeholder}
            className={`w-full bg-white dark:bg-neutral-900/90 border border-neutral-300 dark:border-neutral-700/80 text-neutral-900 dark:text-neutral-100 placeholder-neutral-400 dark:placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-all ${
              disabled ? "opacity-60 cursor-not-allowed " : ""
            }${
              isLarge
                ? "py-3.5 pl-12 pr-12 text-base sm:text-lg rounded-2xl shadow-xs hover:border-neutral-400 dark:hover:border-neutral-600 focus:shadow-md"
                : "py-2 pl-10 pr-10 text-sm rounded-xl shadow-xs"
            }`}
          />

          <button
            type="submit"
            aria-label="Search"
            disabled={disabled}
            className={`absolute inset-y-0 right-0 pr-4 flex items-center text-neutral-400 transition-colors ${
              disabled ? "cursor-not-allowed opacity-40" : "hover:text-neutral-700 dark:hover:text-neutral-200 cursor-pointer"
            }`}
          >
            <CornerDownLeft className={isLarge ? "w-5 h-5" : "w-4 h-4"} />
          </button>
        </div>
      </form>

      {/* Autocomplete Dropdown List */}
      {isOpen && suggestions.length > 0 && (
        <ul
          id="autocomplete-dropdown"
          role="listbox"
          className="absolute z-50 left-0 right-0 mt-2 bg-white/95 dark:bg-neutral-900/95 backdrop-blur-xl border border-neutral-200 dark:border-neutral-800 rounded-2xl shadow-xl overflow-hidden py-1.5 transition-all text-sm"
        >
          {/* Typo indicator header if recovered */}
          {hasTypo && correctedPrefix && (
            <div className="px-4 py-1.5 bg-neutral-50 dark:bg-neutral-800 border-b border-neutral-200 dark:border-neutral-800 text-xs text-neutral-600 dark:text-neutral-400 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              <span>
                Typo recovered: suggesting for <strong>{correctedPrefix}</strong>
              </span>
            </div>
          )}

          {suggestions.map((sug, idx) => {
            const isSelected = idx === selectedIndex;
            return (
              <li
                key={`${sug.text}-${idx}`}
                id={`suggestion-item-${idx}`}
                role="option"
                aria-selected={isSelected}
                onMouseEnter={() => setSelectedIndex(idx)}
                onClick={() => executeSearch(sug.text, "autocomplete", idx + 1)}
                className={`px-4 py-2.5 cursor-pointer flex items-center justify-between transition-colors ${
                  isSelected
                    ? "bg-neutral-100 dark:bg-neutral-800 text-neutral-950 dark:text-neutral-50"
                    : "text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-800"
                }`}
              >
                <div className="flex items-center gap-3 overflow-hidden">
                  <Search className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
                  <span className="truncate">
                    {renderHighlightedText(sug.text, sug.highlight_ranges)}
                  </span>
                </div>

                <div className="flex items-center gap-2 shrink-0 text-[11px] text-neutral-400 font-mono">
                  {sug.session_context_bonus > 0 && (
                    <span className="px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 font-sans text-[10px]">
                      Session
                    </span>
                  )}
                  {sug.source === "query_history" && (
                    <span className="text-neutral-400 text-[10px]">History</span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};
