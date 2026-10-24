"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { History, Trash2, Shield, X, Clock, ToggleLeft, ToggleRight, Check } from "lucide-react";
import {
  getSearchHistory,
  clearSearchHistory,
  updateHistorySettings,
  HistoryItem,
} from "@/lib/api";

interface HistoryPrivacyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const HistoryPrivacyModal: React.FC<HistoryPrivacyModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyEnabled, setHistoryEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    let active = true;
    getSearchHistory(20).then(data => {
      if (active) { setHistory(data.recent_searches || []); setHistoryEnabled(data.history_enabled); }
    }).catch(err => console.debug("Failed to load history:", err))
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [isOpen]);

  const handleClearHistory = async () => {
    if (!confirm("Are you sure you want to clear your local search history? This cannot be undone.")) {
      return;
    }
    try {
      await clearSearchHistory();
      setHistory([]);
      showTemporaryMessage("Search history cleared.");
    } catch (err) {
      console.debug("Failed to clear history:", err);
    }
  };

  const handleTogglePrivacy = async () => {
    const nextState = !historyEnabled;
    try {
      const updated = await updateHistorySettings(nextState);
      setHistoryEnabled(updated);
      showTemporaryMessage(
        updated
          ? "Discovery personalization enabled."
          : "History collection paused. Personalization disabled."
      );
    } catch (err) {
      console.debug("Failed to toggle settings:", err);
    }
  };

  const showTemporaryMessage = (msg: string) => {
    setActionMessage(msg);
    setTimeout(() => setActionMessage(null), 3000);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
      <div className="w-full max-w-lg bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-5 py-4 border-b border-neutral-200 dark:border-neutral-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-neutral-700 dark:text-neutral-300" />
            <h3 className="font-semibold text-neutral-900 dark:text-neutral-100 text-base">
              Search History &amp; Privacy Controls
            </h3>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 transition-colors p-1"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-5">
          {actionMessage && (
            <div className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-200 flex items-center gap-2">
              <Check className="w-3.5 h-3.5" />
              <span>{actionMessage}</span>
            </div>
          )}

          {/* Privacy Toggle Card */}
          <div className="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-800/40 border border-neutral-200 dark:border-neutral-800 flex items-center justify-between gap-4">
            <div>
              <div className="font-medium text-sm text-neutral-900 dark:text-neutral-100">
                Personalized Discovery History
              </div>
              <p className="text-xs text-neutral-500 mt-0.5">
                Record local queries and clicks to personalize autocomplete suggestions. Document ranking remains strictly unaffected.
              </p>
            </div>
            <button
              onClick={handleTogglePrivacy}
              className={`shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
                historyEnabled
                  ? "bg-emerald-600 text-white"
                  : "bg-neutral-200 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300"
              }`}
            >
              {historyEnabled ? (
                <>
                  <ToggleRight className="w-4 h-4" />
                  <span>Enabled</span>
                </>
              ) : (
                <>
                  <ToggleLeft className="w-4 h-4" />
                  <span>Paused</span>
                </>
              )}
            </button>
          </div>

          {/* Recent Searches List */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-neutral-700 dark:text-neutral-300 uppercase tracking-wider font-mono">
                <Clock className="w-3.5 h-3.5" />
                <span>Recent Searches ({history.length})</span>
              </div>
              {history.length > 0 && (
                <button
                  onClick={handleClearHistory}
                  className="text-xs text-rose-600 hover:text-rose-700 dark:text-rose-400 flex items-center gap-1 hover:underline"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Clear All</span>
                </button>
              )}
            </div>

            {loading ? (
              <div className="py-8 text-center text-xs text-neutral-400">Loading history...</div>
            ) : history.length === 0 ? (
              <div className="py-8 text-center text-xs text-neutral-500 rounded-lg border border-dashed border-neutral-200 dark:border-neutral-800">
                No recent searches found.
              </div>
            ) : (
              <div className="max-h-56 overflow-y-auto divide-y divide-neutral-100 dark:divide-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900">
                {history.map((item, idx) => (
                  <div
                    key={`${item.query}-${idx}`}
                    className="px-3.5 py-2 flex items-center justify-between text-xs hover:bg-neutral-50 dark:hover:bg-neutral-800/60 transition-colors"
                  >
                    <Link
                      href={`/search?q=${encodeURIComponent(item.query)}`}
                      onClick={onClose}
                      className="text-blue-700 dark:text-blue-400 hover:underline truncate max-w-xs"
                    >
                      {item.query}
                    </Link>
                    {item.timestamp && (
                      <span className="text-[10px] text-neutral-400 font-mono shrink-0 ml-2">
                        {item.timestamp.split("T")[0]}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-neutral-200 dark:border-neutral-800 bg-neutral-50/70 dark:bg-neutral-800/30 flex items-center justify-between text-xs text-neutral-500">
          <span>All search events stored locally on your machine.</span>
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg bg-neutral-200 hover:bg-neutral-300 dark:bg-neutral-800 dark:hover:bg-neutral-700 text-neutral-800 dark:text-neutral-200 font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
