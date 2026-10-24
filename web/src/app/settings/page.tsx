"use client";

import React, { useState, useEffect, Suspense, useRef } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { useApp, Theme } from "@/context/AppContext";
import {
  getBrainInfo,
  BrainInfoData,
  clearSearchHistory,
  updateHistorySettings,
  getSearchHistory,
  uploadUserAvatar,
  deleteUserAvatar,
} from "@/lib/api";
import {
  Settings as SettingsIcon,
  HardDrive,
  Palette,
  Shield,
  Code2,
  Info,
  Check,
  FolderOpen,
  PlusCircle,
  RefreshCw,
  Sun,
  Moon,
  Laptop,
  CheckCircle2,
  ExternalLink,
  Trash2,
  Copy,
  Brain,
  BarChart2,
  Sliders,
  AlertTriangle,
  User,
  ArrowUpCircle,
  Upload,
  RotateCw,
  Download,
  AlertCircle,
} from "lucide-react";

type SettingsTab =
  | "general"
  | "account"
  | "appearance"
  | "brain"
  | "privacy"
  | "updates"
  | "developer";

function SettingsContent() {
  const searchParams = useSearchParams();
  const initialTab = (searchParams.get("tab") as SettingsTab) || "general";
  const [activeTab, setActiveTab] = useState<SettingsTab>(initialTab);

  const {
    theme,
    resolvedTheme,
    setTheme,
    developerMode,
    setDeveloperMode,
    profile,
    profileAvatarUrl,
    reloadProfile,
    updateProfile,
    updateInfo,
    checkForUpdates,
    downloadUpdate,
    installAndRestart,
  } = useApp();

  const [brainInfo, setBrainInfo] = useState<BrainInfoData | null>(null);
  const [loadingBrain, setLoadingBrain] = useState(true);
  const [copiedPath, setCopiedPath] = useState(false);
  const [historySaved, setHistorySaved] = useState(false);
  const [historyCleared, setHistoryCleared] = useState(false);
  const [saveQueries, setSaveQueries] = useState(true);

  // Profile Form State
  const [displayName, setDisplayName] = useState(profile?.display_name || "");
  const [aboutText, setAboutText] = useState(profile?.about || "");
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState(false);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (profile) {
      setDisplayName(profile.display_name || "");
      setAboutText(profile.about || "");
    }
  }, [profile]);

  // Sync tab from search params
  useEffect(() => {
    const tabParam = searchParams.get("tab") as SettingsTab;
    if (
      tabParam &&
      [
        "general",
        "account",
        "appearance",
        "brain",
        "privacy",
        "updates",
        "developer",
      ].includes(tabParam)
    ) {
      setActiveTab(tabParam);
    }
  }, [searchParams]);

  useEffect(() => {
    getBrainInfo()
      .then((data) => {
        setBrainInfo(data);
        setLoadingBrain(false);
      })
      .catch(() => {
        setBrainInfo({
          brain_id: "local-alpha-001",
          name: "Local Brain",
          path:
            (typeof window !== "undefined" &&
              (window as unknown as { __PESE_CONFIG__?: { brainPath?: string } })
                .__PESE_CONFIG__?.brainPath) ||
            "C:\\Users\\Yasir\\AppData\\Local\\ManiacSoftwares\\PESE\\Brain",
          status: "active",
          document_count: 222,
          schema_version: 1,
          created_at: new Date().toISOString(),
        });
        setLoadingBrain(false);
      });

    getSearchHistory(1)
      .then((s) => setSaveQueries(s.history_enabled))
      .catch(() => {});
  }, []);

  const handleCopyPath = () => {
    if (brainInfo?.path) {
      navigator.clipboard.writeText(brainInfo.path);
      setCopiedPath(true);
      setTimeout(() => setCopiedPath(false), 2000);
    }
  };

  const handleDesktopAction = (action: "change_brain" | "locate_brain" | "new_brain") => {
    const webview = (window as unknown as { chrome?: { webview?: { postMessage: (msg: string) => void } } }).chrome?.webview;
    if (webview) {
      webview.postMessage(action);
    } else {
      alert(`In desktop mode, this action opens the native Windows folder selector.\nAction: ${action}\nCurrent Brain: ${brainInfo?.path}`);
    }
  };

  const handleClearHistory = async () => {
    if (confirm("Are you sure you want to clear your local search query history?")) {
      await clearSearchHistory();
      setHistoryCleared(true);
      setTimeout(() => setHistoryCleared(false), 3000);
    }
  };

  const handleToggleHistory = async (enabled: boolean) => {
    setSaveQueries(enabled);
    await updateHistorySettings(enabled);
    setHistorySaved(true);
    setTimeout(() => setHistorySaved(false), 2000);
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingProfile(true);
    try {
      await updateProfile(displayName, aboutText);
      setProfileSuccess(true);
      setTimeout(() => setProfileSuccess(false), 2500);
    } catch (err) {
      console.error(err);
      alert("Failed to save profile");
    } finally {
      setSavingProfile(false);
    }
  };

  const handleAvatarFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setAvatarUploading(true);
    try {
      const reader = new FileReader();
      reader.onload = async () => {
        const base64 = reader.result as string;
        await uploadUserAvatar(base64, file.name);
        await reloadProfile();
        setAvatarUploading(false);
      };
      reader.readAsDataURL(file);
    } catch (err) {
      console.error(err);
      alert("Failed to upload avatar");
      setAvatarUploading(false);
    }
  };

  const handleDeleteAvatar = async () => {
    if (confirm("Remove profile avatar?")) {
      setAvatarUploading(true);
      try {
        await deleteUserAvatar();
        await reloadProfile();
      } catch (err) {
        console.error(err);
      } finally {
        setAvatarUploading(false);
      }
    }
  };

  return (
    <AppShell>
      <div className="max-w-5xl mx-auto space-y-8 pb-12">
        {/* Page Title */}
        <div className="pb-6 border-b border-surface-border">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 border border-blue-200/50 dark:border-blue-800/50">
              <SettingsIcon className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-neutral-900 dark:text-neutral-50">
                Settings
              </h1>
              <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
                Manage your PESE application preferences, Brain custody, and account identity.
              </p>
            </div>
          </div>
        </div>

        {/* Tab Navigation & Body Grid */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
          {/* Navigation Tabs (Left side) */}
          <nav className="md:col-span-3 space-y-1">
            <button
              type="button"
              onClick={() => setActiveTab("general")}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all text-left cursor-pointer ${
                activeTab === "general"
                  ? "bg-blue-600 text-white font-semibold shadow-xs"
                  : "text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800/60"
              }`}
            >
              <Info className="w-4 h-4 shrink-0" />
              <span>General</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("account")}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all text-left cursor-pointer ${
                activeTab === "account"
                  ? "bg-blue-600 text-white font-semibold shadow-xs"
                  : "text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800/60"
              }`}
            >
              <User className="w-4 h-4 shrink-0" />
              <span>Account & Profile</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("appearance")}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all text-left cursor-pointer ${
                activeTab === "appearance"
                  ? "bg-blue-600 text-white font-semibold shadow-xs"
                  : "text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800/60"
              }`}
            >
              <Palette className="w-4 h-4 shrink-0" />
              <span>Appearance</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("brain")}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all text-left cursor-pointer ${
                activeTab === "brain"
                  ? "bg-blue-600 text-white font-semibold shadow-xs"
                  : "text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800/60"
              }`}
            >
              <HardDrive className="w-4 h-4 shrink-0" />
              <span>Brain Storage</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("privacy")}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all text-left cursor-pointer ${
                activeTab === "privacy"
                  ? "bg-blue-600 text-white font-semibold shadow-xs"
                  : "text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800/60"
              }`}
            >
              <Shield className="w-4 h-4 shrink-0" />
              <span>Privacy & Local</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("updates")}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all text-left cursor-pointer ${
                activeTab === "updates"
                  ? "bg-blue-600 text-white font-semibold shadow-xs"
                  : "text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800/60"
              }`}
            >
              <ArrowUpCircle className="w-4 h-4 shrink-0" />
              <span>Updates</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("developer")}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all text-left cursor-pointer ${
                activeTab === "developer"
                  ? "bg-blue-600 text-white font-semibold shadow-xs"
                  : "text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800/60"
              }`}
            >
              <Code2 className="w-4 h-4 shrink-0" />
              <span>Developer</span>
            </button>
          </nav>

          {/* Tab Content Panel (Right side) */}
          <div className="md:col-span-9 space-y-6">
            {/* ==================== GENERAL TAB ==================== */}
            {activeTab === "general" && (
              <div className="space-y-6">
                <div className="p-6 rounded-2xl bg-surface border border-surface-border shadow-xs space-y-4">
                  <h3 className="text-base font-semibold text-neutral-900 dark:text-neutral-100">
                    Application Information
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                    <div className="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800/80">
                      <span className="text-xs text-neutral-500 dark:text-neutral-400">Release Version</span>
                      <p className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mt-0.5">
                        0.1.0-alpha.3
                      </p>
                    </div>
                    <div className="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800/80">
                      <span className="text-xs text-neutral-500 dark:text-neutral-400">Environment</span>
                      <p className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mt-0.5">
                        Windows x64 Native Desktop
                      </p>
                    </div>
                  </div>
                </div>

                <div className="p-6 rounded-2xl bg-surface border border-surface-border shadow-xs space-y-3">
                  <h3 className="text-base font-semibold text-neutral-900 dark:text-neutral-100">
                    Search-First Interaction
                  </h3>
                  <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
                    PESE operates as a dedicated personal knowledge search engine. Content is the interface, with minimal navigation and zero unsolicited tracking.
                  </p>
                </div>
              </div>
            )}

            {/* ==================== ACCOUNT TAB ==================== */}
            {activeTab === "account" && (
              <div className="space-y-6">
                <form
                  onSubmit={handleSaveProfile}
                  className="p-6 rounded-2xl bg-surface border border-surface-border shadow-xs space-y-6"
                >
                  <div>
                    <h3 className="text-base font-semibold text-neutral-900 dark:text-neutral-100">
                      Local Owner Profile
                    </h3>
                    <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                      Define who owns this Brain. Profile data is saved locally inside your Brain directory and remains completely portable.
                    </p>
                  </div>

                  {/* Avatar Upload / Preview */}
                  <div className="flex items-center gap-5 pt-2">
                    <div className="relative">
                      {profileAvatarUrl ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={profileAvatarUrl}
                          alt="Avatar"
                          className="w-20 h-20 rounded-full object-cover border-2 border-neutral-300 dark:border-neutral-700 shadow-sm"
                        />
                      ) : (
                        <div className="w-20 h-20 rounded-full bg-blue-600/10 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400 flex items-center justify-center text-2xl font-bold border-2 border-dashed border-blue-300 dark:border-blue-700">
                          {displayName ? displayName[0].toUpperCase() : <User className="w-8 h-8" />}
                        </div>
                      )}
                      {avatarUploading && (
                        <div className="absolute inset-0 rounded-full bg-black/40 flex items-center justify-center">
                          <RotateCw className="w-5 h-5 text-white animate-spin" />
                        </div>
                      )}
                    </div>

                    <div className="space-y-2">
                      <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleAvatarFileSelect}
                        accept="image/png,image/jpeg,image/webp,image/gif"
                        className="hidden"
                      />
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => fileInputRef.current?.click()}
                          disabled={avatarUploading}
                          className="px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                        >
                          <Upload className="w-3.5 h-3.5" />
                          <span>Change Avatar</span>
                        </button>
                        {profile?.avatar && (
                          <button
                            type="button"
                            onClick={handleDeleteAvatar}
                            disabled={avatarUploading}
                            className="px-3 py-2 rounded-xl bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/60 text-xs font-medium border border-red-200/50 dark:border-red-800/50 transition-colors cursor-pointer"
                          >
                            Remove
                          </button>
                        )}
                      </div>
                      <p className="text-[11px] text-neutral-400">
                        PNG, JPEG, WebP up to 5MB. Stored directly with your Brain.
                      </p>
                    </div>
                  </div>

                  {/* Display Name */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-neutral-700 dark:text-neutral-300">
                      Display Name
                    </label>
                    <input
                      type="text"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      placeholder="e.g. Yasir"
                      className="w-full max-w-md px-3.5 py-2 rounded-xl bg-neutral-50 dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 text-sm text-neutral-900 dark:text-neutral-100 focus:outline-none focus:border-blue-500"
                    />
                  </div>

                  {/* About / Bio */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-neutral-700 dark:text-neutral-300">
                      About / Biography
                    </label>
                    <textarea
                      rows={3}
                      value={aboutText}
                      onChange={(e) => setAboutText(e.target.value)}
                      placeholder="Short personal description or knowledge explorer notes..."
                      className="w-full max-w-md px-3.5 py-2 rounded-xl bg-neutral-50 dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 text-sm text-neutral-900 dark:text-neutral-100 focus:outline-none focus:border-blue-500 resize-none"
                    />
                  </div>

                  {/* Save Button */}
                  <div className="flex items-center gap-3 pt-2">
                    <button
                      type="submit"
                      disabled={savingProfile}
                      className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                    >
                      {savingProfile ? "Saving..." : "Save Profile"}
                    </button>
                    {profileSuccess && (
                      <span className="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Profile updated in Brain!</span>
                      </span>
                    )}
                  </div>
                </form>

                <div className="p-6 rounded-2xl bg-surface border border-surface-border shadow-xs space-y-2">
                  <h4 className="text-xs font-semibold text-neutral-900 dark:text-neutral-100">
                    Portability Guarantee
                  </h4>
                  <p className="text-xs text-neutral-500 dark:text-neutral-400 leading-relaxed">
                    Your profile schema is versioned and platform-independent. In future cloud backups or syncing to other devices, your profile restores identically with your Brain.
                  </p>
                </div>
              </div>
            )}

            {/* ==================== APPEARANCE TAB ==================== */}
            {activeTab === "appearance" && (
              <div className="space-y-6">
                <div className="p-6 rounded-2xl bg-surface border border-surface-border shadow-xs space-y-4">
                  <div>
                    <h3 className="text-base font-semibold text-neutral-900 dark:text-neutral-100">
                      Theme Mode
                    </h3>
                    <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                      Choose between Dark midnight surfaces, crisp Light slate, or match your Windows system preference.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => setTheme("dark")}
                      className={`flex items-center justify-between p-4 rounded-xl border text-left transition-all cursor-pointer ${
                        theme === "dark"
                          ? "bg-blue-600/10 border-blue-600 text-blue-600 dark:text-blue-400 font-semibold"
                          : "bg-surface border-surface-border hover:bg-neutral-50 dark:hover:bg-neutral-800/40 text-neutral-800 dark:text-neutral-200"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <Moon className="w-5 h-5 shrink-0" />
                        <div>
                          <span className="text-sm block">Dark</span>
                          <span className="text-[11px] text-neutral-500 font-normal">Midnight void</span>
                        </div>
                      </div>
                      {theme === "dark" && <Check className="w-4 h-4 shrink-0" />}
                    </button>

                    <button
                      type="button"
                      onClick={() => setTheme("light")}
                      className={`flex items-center justify-between p-4 rounded-xl border text-left transition-all cursor-pointer ${
                        theme === "light"
                          ? "bg-blue-600/10 border-blue-600 text-blue-600 dark:text-blue-400 font-semibold"
                          : "bg-surface border-surface-border hover:bg-neutral-50 dark:hover:bg-neutral-800/40 text-neutral-800 dark:text-neutral-200"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <Sun className="w-5 h-5 shrink-0" />
                        <div>
                          <span className="text-sm block">Light</span>
                          <span className="text-[11px] text-neutral-500 font-normal">Crisp slate</span>
                        </div>
                      </div>
                      {theme === "light" && <Check className="w-4 h-4 shrink-0" />}
                    </button>

                    <button
                      type="button"
                      onClick={() => setTheme("system")}
                      className={`flex items-center justify-between p-4 rounded-xl border text-left transition-all cursor-pointer ${
                        theme === "system"
                          ? "bg-blue-600/10 border-blue-600 text-blue-600 dark:text-blue-400 font-semibold"
                          : "bg-surface border-surface-border hover:bg-neutral-50 dark:hover:bg-neutral-800/40 text-neutral-800 dark:text-neutral-200"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <Laptop className="w-5 h-5 shrink-0" />
                        <div>
                          <span className="text-sm block">System</span>
                          <span className="text-[11px] text-neutral-500 font-normal">Auto-detect</span>
                        </div>
                      </div>
                      {theme === "system" && <Check className="w-4 h-4 shrink-0" />}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ==================== BRAIN STORAGE TAB ==================== */}
            {activeTab === "brain" && (
              <div className="space-y-6">
                <div className="p-6 rounded-2xl bg-surface border border-surface-border shadow-xs space-y-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-base font-semibold text-neutral-900 dark:text-neutral-100">
                        Current Brain Storage
                      </h3>
                      <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                        All documents, vector indexes, and search feedback are stored inside this locally-owned folder.
                      </p>
                    </div>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-medium text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                      Active
                    </span>
                  </div>

                  {/* Brain Path Display */}
                  <div className="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800/80 space-y-2">
                    <span className="text-xs text-neutral-500 dark:text-neutral-400">Folder Location</span>
                    <div className="flex items-center justify-between gap-3 font-mono text-xs text-neutral-800 dark:text-neutral-200 overflow-hidden">
                      <span className="truncate">{brainInfo?.path || "Loading path..."}</span>
                      <button
                        type="button"
                        onClick={handleCopyPath}
                        className="shrink-0 p-1.5 rounded-lg text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200 hover:bg-neutral-200/60 dark:hover:bg-neutral-800 transition-colors cursor-pointer"
                        title="Copy Brain path"
                      >
                        {copiedPath ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  {/* Brain Stats */}
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    <div className="p-3.5 rounded-xl bg-neutral-50 dark:bg-neutral-900/40 border border-neutral-200/80 dark:border-neutral-800/80">
                      <span className="text-[11px] text-neutral-500 dark:text-neutral-400">Total Notes</span>
                      <p className="text-base font-semibold text-neutral-900 dark:text-neutral-100 mt-0.5">
                        {brainInfo?.document_count ?? 222}
                      </p>
                    </div>
                    <div className="p-3.5 rounded-xl bg-neutral-50 dark:bg-neutral-900/40 border border-neutral-200/80 dark:border-neutral-800/80">
                      <span className="text-[11px] text-neutral-500 dark:text-neutral-400">Format</span>
                      <p className="text-base font-semibold text-neutral-900 dark:text-neutral-100 mt-0.5">
                        pese-brain v1
                      </p>
                    </div>
                    <div className="p-3.5 rounded-xl bg-neutral-50 dark:bg-neutral-900/40 border border-neutral-200/80 dark:border-neutral-800/80 col-span-2 sm:col-span-1">
                      <span className="text-[11px] text-neutral-500 dark:text-neutral-400">Brain ID</span>
                      <p className="text-xs font-mono font-medium text-neutral-900 dark:text-neutral-100 mt-1 truncate">
                        {brainInfo?.brain_id || "6240cfe03892406092bc191d2acf7a27"}
                      </p>
                    </div>
                  </div>

                  {/* Native Windows Desktop Actions */}
                  <div className="pt-4 border-t border-neutral-200/80 dark:border-neutral-800/80 flex flex-wrap gap-2.5">
                    <button
                      type="button"
                      onClick={() => handleDesktopAction("locate_brain")}
                      className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium shadow-xs transition-colors flex items-center gap-2 cursor-pointer"
                    >
                      <FolderOpen className="w-3.5 h-3.5" />
                      <span>Locate Existing Brain</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDesktopAction("new_brain")}
                      className="px-4 py-2 rounded-xl bg-white dark:bg-neutral-900 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-800 dark:text-neutral-200 text-xs font-medium border border-neutral-300 dark:border-neutral-700 shadow-2xs transition-colors flex items-center gap-2 cursor-pointer"
                    >
                      <PlusCircle className="w-3.5 h-3.5 text-neutral-500" />
                      <span>Create New Brain</span>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ==================== PRIVACY TAB ==================== */}
            {activeTab === "privacy" && (
              <div className="space-y-6">
                <div className="p-6 rounded-2xl bg-surface border border-surface-border shadow-xs space-y-5">
                  <div>
                    <h3 className="text-base font-semibold text-neutral-900 dark:text-neutral-100">
                      Search History & Data Retention
                    </h3>
                    <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                      PESE is 100% offline. No query data or documents are ever transmitted across the internet.
                    </p>
                  </div>

                  <div className="flex items-center justify-between p-4 rounded-xl bg-neutral-50 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800/80">
                    <div>
                      <span className="text-xs font-medium text-neutral-900 dark:text-neutral-100">
                        Record Search Query History
                      </span>
                      <p className="text-[11px] text-neutral-500 mt-0.5">
                        Used locally for search suggestions and Search Sync learning.
                      </p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={saveQueries}
                        onChange={(e) => handleToggleHistory(e.target.checked)}
                        className="sr-only peer"
                      />
                      <div className="w-9 h-5 bg-neutral-300 peer-focus:outline-none rounded-full peer dark:bg-neutral-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-neutral-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600" />
                    </label>
                  </div>

                  <div className="flex items-center justify-between pt-2">
                    <button
                      type="button"
                      onClick={handleClearHistory}
                      className="px-4 py-2 rounded-xl bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/60 text-xs font-medium border border-red-200/50 dark:border-red-800/50 transition-colors flex items-center gap-2 cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Clear Search History</span>
                    </button>
                    {historyCleared && (
                      <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                        Search history cleared.
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* ==================== UPDATES TAB ==================== */}
            {activeTab === "updates" && (
              <div className="space-y-6">
                <div className="p-6 rounded-2xl bg-surface border border-surface-border shadow-xs space-y-6">
                  <div>
                    <h3 className="text-base font-semibold text-neutral-900 dark:text-neutral-100">
                      Release & Update Center
                    </h3>
                    <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                      PESE updates from official published releases. Git commits never overwrite installed software.
                    </p>
                  </div>

                  {/* Status Card */}
                  <div className="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800/80 space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-xs text-neutral-500 dark:text-neutral-400">Current Release</span>
                        <p className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mt-0.5">
                          PESE {updateInfo.currentVersion}
                        </p>
                      </div>
                      <span className="text-xs font-mono px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300">
                        Alpha Channel
                      </span>
                    </div>

                    <div className="pt-2 border-t border-neutral-200/60 dark:border-neutral-800/60 flex items-center justify-between text-xs">
                      <span className="text-neutral-500">Status</span>
                      <div className="flex items-center gap-1.5 font-medium">
                        {updateInfo.status === "up_to_date" && (
                          <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Up to date</span>
                          </span>
                        )}
                        {updateInfo.status === "checking" && (
                          <span className="text-blue-600 dark:text-blue-400 flex items-center gap-1">
                            <RotateCw className="w-3.5 h-3.5 animate-spin" />
                            <span>Checking for updates...</span>
                          </span>
                        )}
                        {updateInfo.status === "available" && (
                          <span className="text-blue-600 dark:text-blue-400 flex items-center gap-1">
                            <ArrowUpCircle className="w-3.5 h-3.5" />
                            <span>Update available: {updateInfo.targetVersion}</span>
                          </span>
                        )}
                        {updateInfo.status === "downloading" && (
                          <span className="text-blue-600 dark:text-blue-400 flex items-center gap-1">
                            <Download className="w-3.5 h-3.5 animate-bounce" />
                            <span>Downloading ({updateInfo.progress || 0}%)</span>
                          </span>
                        )}
                        {updateInfo.status === "ready" && (
                          <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Ready to install</span>
                          </span>
                        )}
                        {updateInfo.status === "failed" && (
                          <span className="text-red-600 dark:text-red-400 flex items-center gap-1">
                            <AlertCircle className="w-3.5 h-3.5" />
                            <span>Check failed</span>
                          </span>
                        )}
                        {updateInfo.status === "idle" && (
                          <span className="text-neutral-600 dark:text-neutral-400">Ready</span>
                        )}
                      </div>
                    </div>

                    {updateInfo.status === "downloading" && (
                      <div className="space-y-1.5 pt-2">
                        <div className="w-full h-2 rounded-full bg-neutral-200 dark:bg-neutral-800 overflow-hidden">
                          <div
                            className="h-full bg-blue-600 transition-all duration-300"
                            style={{ width: `${updateInfo.progress || 0}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {updateInfo.status === "failed" && (
                      <p className="text-xs text-red-500 dark:text-red-400 leading-relaxed">
                        {updateInfo.error || "Update feed could not be reached. Your current PESE installation and all Brain data remain intact."}
                      </p>
                    )}
                  </div>

                  {/* Update Actions */}
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      onClick={checkForUpdates}
                      disabled={updateInfo.status === "checking" || updateInfo.status === "downloading"}
                      className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium shadow-xs transition-colors flex items-center gap-2 cursor-pointer disabled:opacity-50"
                    >
                      <RotateCw className={`w-3.5 h-3.5 ${updateInfo.status === "checking" ? "animate-spin" : ""}`} />
                      <span>{updateInfo.status === "checking" ? "Checking..." : "Check for updates"}</span>
                    </button>

                    {updateInfo.status === "available" && (
                      <button
                        type="button"
                        onClick={downloadUpdate}
                        className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium shadow-xs transition-colors flex items-center gap-2 cursor-pointer"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>Download {updateInfo.targetVersion}</span>
                      </button>
                    )}

                    {updateInfo.status === "ready" && (
                      <button
                        type="button"
                        onClick={installAndRestart}
                        className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium shadow-xs transition-colors flex items-center gap-2 cursor-pointer"
                      >
                        <RotateCw className="w-3.5 h-3.5" />
                        <span>Restart PESE to Apply</span>
                      </button>
                    )}

                    {updateInfo.lastChecked && (
                      <span className="text-xs text-neutral-400">
                        Last checked: {updateInfo.lastChecked}
                      </span>
                    )}
                  </div>
                </div>

                <div className="p-6 rounded-2xl bg-surface border border-surface-border shadow-xs space-y-2">
                  <h4 className="text-xs font-semibold text-neutral-900 dark:text-neutral-100">
                    Brain Safety During Updates
                  </h4>
                  <p className="text-xs text-neutral-500 dark:text-neutral-400 leading-relaxed">
                    Updates replace application binaries only. Your selected Brain path, identity, documents, and Search Sync feedback database reside in user storage and are never touched during installation or rollback.
                  </p>
                </div>
              </div>
            )}

            {/* ==================== DEVELOPER TAB ==================== */}
            {activeTab === "developer" && (
              <div className="space-y-6">
                <div className="p-6 rounded-2xl bg-surface border border-surface-border shadow-xs space-y-5">
                  <div>
                    <h3 className="text-base font-semibold text-neutral-900 dark:text-neutral-100">
                      Developer & Engineering Tools
                    </h3>
                    <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                      Reveal experimental internal laboratories, ranking traces, and evaluation benchmarks.
                    </p>
                  </div>

                  <div className="flex items-center justify-between p-4 rounded-xl bg-neutral-50 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800/80">
                    <div>
                      <span className="text-xs font-medium text-neutral-900 dark:text-neutral-100">
                        Enable Developer Mode
                      </span>
                      <p className="text-[11px] text-neutral-500 mt-0.5">
                        Reveals Neural Lab, Evaluation Benchmarks, and detailed scoring traces on search results.
                      </p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={developerMode}
                        onChange={(e) => setDeveloperMode(e.target.checked)}
                        className="sr-only peer"
                      />
                      <div className="w-9 h-5 bg-neutral-300 peer-focus:outline-none rounded-full peer dark:bg-neutral-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-neutral-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-600" />
                    </label>
                  </div>

                  {developerMode && (
                    <div className="pt-2 border-t border-neutral-200/80 dark:border-neutral-800/80 space-y-3">
                      <span className="text-xs font-medium text-neutral-700 dark:text-neutral-300">
                        Experimental Laboratories
                      </span>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <Link
                          href="/admin/neural-lab"
                          className="flex items-center justify-between p-3.5 rounded-xl border border-neutral-200 dark:border-neutral-800 hover:border-purple-500/50 hover:bg-purple-50/20 dark:hover:bg-purple-950/20 transition-all text-xs font-medium text-neutral-800 dark:text-neutral-200"
                        >
                          <div className="flex items-center gap-2.5">
                            <Code2 className="w-4 h-4 text-purple-600" />
                            <span>Neural Laboratory</span>
                          </div>
                          <ExternalLink className="w-3.5 h-3.5 text-neutral-400" />
                        </Link>
                        <Link
                          href="/admin/eval"
                          className="flex items-center justify-between p-3.5 rounded-xl border border-neutral-200 dark:border-neutral-800 hover:border-purple-500/50 hover:bg-purple-50/20 dark:hover:bg-purple-950/20 transition-all text-xs font-medium text-neutral-800 dark:text-neutral-200"
                        >
                          <div className="flex items-center gap-2.5">
                            <BarChart2 className="w-4 h-4 text-purple-600" />
                            <span>Evaluation Benchmarks</span>
                          </div>
                          <ExternalLink className="w-3.5 h-3.5 text-neutral-400" />
                        </Link>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-neutral-500">Loading settings...</div>}>
      <SettingsContent />
    </Suspense>
  );
}
