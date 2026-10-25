"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { getUserProfile, UserProfileData, updateUserProfile as apiUpdateProfile } from "@/lib/api";

export type Theme = "dark" | "light" | "system";
export type ResolvedTheme = "dark" | "light";

export type UpdateStatus =
  | "idle"
  | "checking"
  | "available"
  | "downloading"
  | "ready"
  | "installing"
  | "restarting"
  | "failed"
  | "up_to_date";

export interface UpdateInfo {
  status: UpdateStatus;
  currentVersion: string;
  targetVersion?: string;
  progress?: number;
  error?: string;
  lastChecked?: string;
  releaseNotes?: string;
}

interface AppContextType {
  theme: Theme;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: Theme) => void;
  developerMode: boolean;
  setDeveloperMode: (enabled: boolean) => void;
  profile: UserProfileData | null;
  profileAvatarUrl: string | null;
  reloadProfile: () => Promise<void>;
  updateProfile: (displayName: string, about: string) => Promise<void>;
  updateInfo: UpdateInfo;
  checkForUpdates: () => void;
  downloadUpdate: () => void;
  installAndRestart: () => void;
  dismissUpdateNotification: () => void;
  showUpdateModal: boolean;
  setShowUpdateModal: (show: boolean) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

const THEME_STORAGE_KEY = "pese_theme";
const DEV_MODE_STORAGE_KEY = "pese_developer_mode";
const APP_VERSION = "0.1.0-alpha.4";

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setThemeState] = useState<Theme>("dark");
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>("dark");
  const [developerMode, setDeveloperModeState] = useState<boolean>(false);
  const [mounted, setMounted] = useState<boolean>(false);
  const [profile, setProfile] = useState<UserProfileData | null>(null);
  const [avatarTimestamp, setAvatarTimestamp] = useState<number>(Date.now());
  const [showUpdateModal, setShowUpdateModal] = useState<boolean>(false);
  const [updateDismissed, setUpdateDismissed] = useState<boolean>(false);

  const [updateInfo, setUpdateInfo] = useState<UpdateInfo>({
    status: "idle",
    currentVersion: APP_VERSION,
  });

  // Initialize theme, dev mode, profile
  useEffect(() => {
    try {
      const searchParams = new URLSearchParams(window.location.search);
      const urlTheme = searchParams.get("theme") as Theme | null;
      if (urlTheme && ["dark", "light", "system"].includes(urlTheme)) {
        setThemeState(urlTheme);
        try { localStorage.setItem(THEME_STORAGE_KEY, urlTheme); } catch {}
      } else {
        const savedTheme = localStorage.getItem(THEME_STORAGE_KEY) as Theme | null;
        if (savedTheme && ["dark", "light", "system"].includes(savedTheme)) {
          setThemeState(savedTheme);
        }
      }

      const urlDev = searchParams.get("dev");
      if (urlDev !== null) {
        const devVal = urlDev === "true" || urlDev === "1";
        setDeveloperModeState(devVal);
        try { localStorage.setItem(DEV_MODE_STORAGE_KEY, String(devVal)); } catch {}
      } else {
        const savedDevMode = localStorage.getItem(DEV_MODE_STORAGE_KEY);
        if (savedDevMode !== null) {
          setDeveloperModeState(savedDevMode === "true");
        }
      }
    } catch {}

    // Load initial profile
    getUserProfile()
      .then((p) => {
        setProfile(p);
      })
      .catch(() => {
        // Fallback default
        setProfile({
          schema_version: 1,
          display_name: "Local User",
          about: "",
          avatar: null,
          updated_at: new Date().toISOString(),
        });
      });

    setMounted(true);
  }, []);

  // Listen to WebView2 native messages from WPF host
  useEffect(() => {
    const handleHostMessage = (event: MessageEvent) => {
      try {
        const raw = event.data;
        const data = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (data?.type === "update_status") {
          setUpdateInfo((prev) => {
            const nextStatus = (data.status as UpdateStatus) || prev.status;
            // Pop modal only when available and not dismissed
            if (nextStatus === "available" && !updateDismissed) {
              setShowUpdateModal(true);
            }
            return {
              ...prev,
              status: nextStatus,
              currentVersion: data.currentVersion || prev.currentVersion,
              targetVersion: data.targetVersion || prev.targetVersion,
              progress: typeof data.progress === "number" ? data.progress : prev.progress,
              error: data.error,
              lastChecked: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
              releaseNotes: data.releaseNotes || prev.releaseNotes,
            };
          });
        }
      } catch {}
    };

    const nav = window as unknown as { chrome?: { webview?: { addEventListener: (t: string, cb: (e: MessageEvent) => void) => void; removeEventListener: (t: string, cb: (e: MessageEvent) => void) => void } } };
    if (nav.chrome?.webview) {
      nav.chrome.webview.addEventListener("message", handleHostMessage);
      return () => nav.chrome?.webview?.removeEventListener("message", handleHostMessage);
    }
  }, [updateDismissed]);

  // Compute resolved theme & apply to document element
  useEffect(() => {
    if (!mounted) return;

    let target: ResolvedTheme = "dark";
    if (theme === "system") {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      target = prefersDark ? "dark" : "light";
    } else {
      target = theme;
    }

    setResolvedTheme(target);

    const root = document.documentElement;
    if (target === "dark") {
      root.classList.add("dark");
      root.classList.remove("light");
      root.setAttribute("data-theme", "dark");
    } else {
      root.classList.remove("dark");
      root.classList.add("light");
      root.setAttribute("data-theme", "light");
    }

    if (theme === "system") {
      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      const handler = (e: MediaQueryListEvent) => {
        const newTheme: ResolvedTheme = e.matches ? "dark" : "light";
        setResolvedTheme(newTheme);
        if (newTheme === "dark") {
          root.classList.add("dark");
          root.classList.remove("light");
          root.setAttribute("data-theme", "dark");
        } else {
          root.classList.remove("dark");
          root.classList.add("light");
          root.setAttribute("data-theme", "light");
        }
      };
      mediaQuery.addEventListener("change", handler);
      return () => mediaQuery.removeEventListener("change", handler);
    }
  }, [theme, mounted]);

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, newTheme);
    } catch {}
  };

  const setDeveloperMode = (enabled: boolean) => {
    setDeveloperModeState(enabled);
    try {
      localStorage.setItem(DEV_MODE_STORAGE_KEY, enabled ? "true" : "false");
    } catch {}
  };

  const reloadProfile = useCallback(async () => {
    try {
      const p = await getUserProfile();
      setProfile(p);
      setAvatarTimestamp(Date.now());
    } catch (e) {
      console.error("Failed to reload profile", e);
    }
  }, []);

  const updateProfile = useCallback(async (displayName: string, about: string) => {
    const updated = await apiUpdateProfile(displayName, about);
    setProfile(updated);
  }, []);

  const profileAvatarUrl = profile?.avatar?.relative_path
    ? `/api/profile/avatar?t=${avatarTimestamp}`
    : null;

  const checkForUpdates = useCallback(() => {
    setUpdateInfo((prev) => ({
      ...prev,
      status: "checking",
      error: undefined,
    }));

    const nav = window as unknown as { chrome?: { webview?: { postMessage: (msg: string) => void } } };
    if (nav.chrome?.webview) {
      nav.chrome.webview.postMessage("check_updates");
    } else {
      // Browser / dev simulated check
      setTimeout(() => {
        setUpdateInfo((prev) => ({
          ...prev,
          status: "up_to_date",
          currentVersion: APP_VERSION,
          lastChecked: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        }));
      }, 700);
    }
  }, []);

  const downloadUpdate = useCallback(() => {
    setUpdateInfo((prev) => ({ ...prev, status: "downloading", progress: 0 }));
    const nav = window as unknown as { chrome?: { webview?: { postMessage: (msg: string) => void } } };
    if (nav.chrome?.webview) {
      nav.chrome.webview.postMessage("download_update");
    } else {
      // Dev simulated download
      let p = 0;
      const interval = setInterval(() => {
        p += 25;
        if (p >= 100) {
          clearInterval(interval);
          setUpdateInfo((prev) => ({ ...prev, status: "ready", progress: 100 }));
        } else {
          setUpdateInfo((prev) => ({ ...prev, progress: p }));
        }
      }, 300);
    }
  }, []);

  const installAndRestart = useCallback(() => {
    setUpdateInfo((prev) => ({ ...prev, status: "installing" }));
    const nav = window as unknown as { chrome?: { webview?: { postMessage: (msg: string) => void } } };
    if (nav.chrome?.webview) {
      nav.chrome.webview.postMessage("install_update");
    }
  }, []);

  const dismissUpdateNotification = () => {
    setShowUpdateModal(false);
    setUpdateDismissed(true);
  };

  return (
    <AppContext.Provider
      value={{
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
        dismissUpdateNotification,
        showUpdateModal,
        setShowUpdateModal,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export function useApp(): AppContextType {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within an AppProvider");
  }
  return context;
}
