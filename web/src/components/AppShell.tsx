"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Search,
  FileText,
  Settings,
  History,
  Sun,
  Moon,
  Laptop,
  Cpu,
  BarChart2,
  User,
  ArrowUpCircle,
  X,
  Download,
  CheckCircle2,
  AlertCircle,
  RotateCw,
} from "lucide-react";
import { PeseLogoMark } from "./PeseLogo";
import { useApp } from "@/context/AppContext";
import { HistoryPrivacyModal } from "./HistoryPrivacyModal";

interface AppShellProps {
  children: React.ReactNode;
  headerContent?: React.ReactNode;
  noPadding?: boolean;
}

export const AppShell: React.FC<AppShellProps> = ({
  children,
  headerContent,
  noPadding = false,
}) => {
  const pathname = usePathname();
  const {
    theme,
    setTheme,
    developerMode,
    profile,
    profileAvatarUrl,
    updateInfo,
    showUpdateModal,
    setShowUpdateModal,
    dismissUpdateNotification,
    downloadUpdate,
    installAndRestart,
  } = useApp();

  const [isHistoryOpen, setIsHistoryOpen] = useState(false);

  // Check active navigation link
  const isSearchActive = pathname === "/" || pathname?.startsWith("/search");
  const isNotesActive =
    pathname?.startsWith("/admin") &&
    !pathname?.startsWith("/admin/eval") &&
    !pathname?.startsWith("/admin/neural-lab");
  const isSettingsActive = pathname?.startsWith("/settings");
  const isNeuralLabActive = pathname?.startsWith("/admin/neural-lab");
  const isBenchmarkActive = pathname?.startsWith("/admin/eval");

  const cycleTheme = () => {
    if (theme === "dark") setTheme("light");
    else if (theme === "light") setTheme("system");
    else setTheme("dark");
  };

  const hasUpdateReady = updateInfo.status === "available" || updateInfo.status === "ready";

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground antialiased select-none font-sans">
      {/* ==================== MINIMAL NAVIGATION RAIL ==================== */}
      <aside className="w-14 sm:w-16 shrink-0 flex flex-col justify-between items-center py-3.5 px-1.5 glass-sidebar border-r border-neutral-200/80 dark:border-neutral-800/80 z-30 transition-all duration-200 select-none">
        {/* Top: PESE Mark & Core Destinations */}
        <div className="flex flex-col items-center space-y-4 w-full">
          {/* PESE Anchor Mark */}
          <Link
            href="/"
            title="PESE Home"
            className="p-1.5 rounded-xl hover:bg-neutral-200/50 dark:hover:bg-neutral-800/50 transition-all hover:scale-105 active:scale-95 group focus:outline-none"
          >
            <PeseLogoMark size={30} />
          </Link>

          <div className="w-8 h-[1px] bg-neutral-200 dark:bg-neutral-800" />

          {/* Primary Navigation Icons */}
          <nav className="flex flex-col items-center space-y-2 w-full">
            {/* Search */}
            <Link
              href="/"
              title="Search"
              className={`w-10 h-10 flex items-center justify-center rounded-xl transition-all ${
                isSearchActive
                  ? "bg-blue-600 text-white shadow-xs font-semibold scale-100"
                  : "text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-200/60 dark:hover:bg-neutral-800/60"
              }`}
            >
              <Search className="w-5 h-5" />
            </Link>

            {/* Notes */}
            <Link
              href="/admin"
              title="Notes"
              className={`w-10 h-10 flex items-center justify-center rounded-xl transition-all ${
                isNotesActive
                  ? "bg-blue-600 text-white shadow-xs font-semibold scale-100"
                  : "text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-200/60 dark:hover:bg-neutral-800/60"
              }`}
            >
              <FileText className="w-5 h-5" />
            </Link>

            {/* History */}
            <button
              type="button"
              onClick={() => setIsHistoryOpen(true)}
              title="Search History & Privacy"
              className="w-10 h-10 flex items-center justify-center rounded-xl text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-200/60 dark:hover:bg-neutral-800/60 transition-all cursor-pointer"
            >
              <History className="w-5 h-5" />
            </button>

            {/* Developer Mode Conditional Icons */}
            {developerMode && (
              <>
                <div className="w-6 h-[1px] bg-neutral-200 dark:bg-neutral-800 my-1" />
                <Link
                  href="/admin/neural-lab"
                  title="Neural Laboratory"
                  className={`w-10 h-10 flex items-center justify-center rounded-xl transition-all ${
                    isNeuralLabActive
                      ? "bg-purple-600 text-white shadow-xs font-semibold"
                      : "text-neutral-500 hover:text-purple-600 dark:hover:text-purple-400 hover:bg-neutral-200/60 dark:hover:bg-neutral-800/60"
                  }`}
                >
                  <Cpu className="w-5 h-5" />
                </Link>

                <Link
                  href="/admin/eval"
                  title="Evaluation & Benchmarks"
                  className={`w-10 h-10 flex items-center justify-center rounded-xl transition-all ${
                    isBenchmarkActive
                      ? "bg-purple-600 text-white shadow-xs font-semibold"
                      : "text-neutral-500 hover:text-purple-600 dark:hover:text-purple-400 hover:bg-neutral-200/60 dark:hover:bg-neutral-800/60"
                  }`}
                >
                  <BarChart2 className="w-5 h-5" />
                </Link>
              </>
            )}
          </nav>
        </div>

        {/* Bottom: Profile, Update Indicator, Theme, Settings */}
        <div className="flex flex-col items-center space-y-2.5 w-full">
          {/* Update Indicator Pill (if available) */}
          {hasUpdateReady && (
            <button
              type="button"
              onClick={() => setShowUpdateModal(true)}
              title={`Update available: ${updateInfo.targetVersion || "New version"}`}
              className="w-10 h-10 flex items-center justify-center rounded-xl text-emerald-500 hover:bg-emerald-500/10 transition-colors animate-pulse cursor-pointer"
            >
              <ArrowUpCircle className="w-5 h-5" />
            </button>
          )}

          {/* User Account / Profile Entry */}
          <Link
            href="/settings?tab=account"
            title={profile ? `${profile.display_name} — Account` : "Account"}
            className="w-10 h-10 rounded-xl flex items-center justify-center text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-200/60 dark:hover:bg-neutral-800/60 transition-all overflow-hidden"
          >
            {profileAvatarUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={profileAvatarUrl}
                alt="Profile"
                className="w-8 h-8 rounded-full object-cover border border-neutral-300 dark:border-neutral-700 shadow-2xs"
              />
            ) : (
              <div className="w-8 h-8 rounded-full bg-blue-600/10 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400 flex items-center justify-center text-xs font-semibold">
                {profile?.display_name ? profile.display_name[0].toUpperCase() : <User className="w-4 h-4" />}
              </div>
            )}
          </Link>

          {/* Theme Quick Cycle */}
          <button
            type="button"
            onClick={cycleTheme}
            title={`Current theme: ${theme} (Click to cycle)`}
            className="w-10 h-10 flex items-center justify-center rounded-xl text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-200/60 dark:hover:bg-neutral-800/60 transition-colors cursor-pointer"
          >
            {theme === "dark" ? (
              <Moon className="w-4 h-4" />
            ) : theme === "light" ? (
              <Sun className="w-4 h-4" />
            ) : (
              <Laptop className="w-4 h-4" />
            )}
          </button>

          {/* Settings Persistent Bottom-Left Icon */}
          <Link
            href="/settings"
            title="Settings"
            className={`w-10 h-10 flex items-center justify-center rounded-xl transition-all ${
              isSettingsActive
                ? "bg-blue-600 text-white shadow-xs font-semibold scale-100"
                : "text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-200/60 dark:hover:bg-neutral-800/60"
            }`}
          >
            <Settings className="w-5 h-5" />
          </Link>
        </div>
      </aside>

      {/* ==================== MAIN CONTENT PANE ==================== */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden relative">
        {headerContent && (
          <div className="shrink-0 border-b border-neutral-200/80 dark:border-neutral-800/80 bg-background/90 backdrop-blur-md z-20">
            {headerContent}
          </div>
        )}

        <main
          className={`flex-1 overflow-y-auto ${
            noPadding ? "p-0" : "p-4 sm:p-6 lg:p-8"
          } focus:outline-none`}
        >
          {children}
        </main>
      </div>

      {/* ==================== UPDATE NOTIFICATION MODAL ==================== */}
      {showUpdateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="w-full max-w-md bg-white dark:bg-neutral-900 rounded-2xl p-6 border border-neutral-200 dark:border-neutral-800 shadow-2xl relative">
            <button
              type="button"
              onClick={dismissUpdateNotification}
              className="absolute top-4 right-4 p-1.5 rounded-lg text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-blue-600/10 text-blue-600 flex items-center justify-center">
                <ArrowUpCircle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-semibold text-neutral-900 dark:text-neutral-100 text-base">
                  PESE {updateInfo.targetVersion || "Update"} available
                </h3>
                <p className="text-xs text-neutral-500 dark:text-neutral-400">
                  Current version: {updateInfo.currentVersion}
                </p>
              </div>
            </div>

            <p className="text-sm text-neutral-600 dark:text-neutral-300 mb-5 leading-relaxed">
              A new release of PESE is available. Your personal Brain and search data remain completely preserved during updates.
            </p>

            {updateInfo.releaseNotes && <pre className="whitespace-pre-wrap font-sans text-xs max-h-48 overflow-y-auto mb-5">{updateInfo.releaseNotes}</pre>}
            {updateInfo.status === "downloading" && (
              <div className="mb-5 space-y-2">
                <div className="flex justify-between text-xs font-mono text-neutral-500">
                  <span>Downloading update...</span>
                  <span>{updateInfo.progress || 0}%</span>
                </div>
                <div className="w-full h-2 rounded-full bg-neutral-200 dark:bg-neutral-800 overflow-hidden">
                  <div
                    className="h-full bg-blue-600 transition-all duration-300"
                    style={{ width: `${updateInfo.progress || 0}%` }}
                  />
                </div>
              </div>
            )}

            {updateInfo.status === "ready" && (
              <div className="mb-5 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>Update verified and staged. Ready to restart.</span>
              </div>
            )}

            {updateInfo.status === "failed" && (
              <div className="mb-5 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{updateInfo.error || "Update check or download failed."}</span>
              </div>
            )}

            <div className="flex items-center justify-end gap-2.5">
              <button
                type="button"
                onClick={dismissUpdateNotification}
                className="px-4 py-2 rounded-xl text-xs font-medium text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors cursor-pointer"
              >
                Later
              </button>

              {updateInfo.status === "ready" ? (
                <button
                  type="button"
                  onClick={installAndRestart}
                  className="px-4 py-2 rounded-xl text-xs font-medium bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  <RotateCw className="w-3.5 h-3.5" />
                  <span>Update and restart</span>
                </button>
              ) : updateInfo.status === "downloading" ? (
                <button
                  type="button"
                  disabled
                  className="px-4 py-2 rounded-xl text-xs font-medium bg-blue-600/70 text-white cursor-not-allowed flex items-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5 animate-bounce" />
                  <span>Downloading...</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={downloadUpdate}
                  disabled={updateInfo.status !== "available" && updateInfo.status !== "failed"}
                  className="px-4 py-2 rounded-xl text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download Update</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* History and Privacy Modal */}
      <HistoryPrivacyModal
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
      />
    </div>
  );
};
