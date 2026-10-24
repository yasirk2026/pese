"use client";

import React from "react";

interface PeseLogoProps {
  size?: number | "xs" | "sm" | "md" | "lg" | "xl";
  className?: string;
  showWordmark?: boolean;
  subtitle?: string;
  badge?: string;
}

export const PeseLogoMark: React.FC<{ size?: number; className?: string }> = ({
  size = 28,
  className = "",
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 transition-transform duration-200 ${className}`}
      aria-label="PESE Logo Mark"
    >
      <defs>
        {/* Top facet gradient */}
        <linearGradient id="pese-top-grad" x1="16" y1="3" x2="16" y2="15" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#60a5fa" />
          <stop offset="100%" stopColor="#3b82f6" />
        </linearGradient>

        {/* Left facet gradient */}
        <linearGradient id="pese-left-grad" x1="4" y1="10" x2="16" y2="29" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#2563eb" />
          <stop offset="100%" stopColor="#1e3a8a" />
        </linearGradient>

        {/* Right facet gradient */}
        <linearGradient id="pese-right-grad" x1="28" y1="10" x2="16" y2="29" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#1d4ed8" />
          <stop offset="100%" stopColor="#0f172a" />
        </linearGradient>

        {/* Core focal emitter glow */}
        <radialGradient id="pese-core-glow" cx="16" cy="15" r="5" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#93c5fd" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Hexagonal Prism Base Silhouette */}
      {/* Top Facet */}
      <polygon
        points="16,3 27,9.5 16,16 5,9.5"
        fill="url(#pese-top-grad)"
        stroke="#93c5fd"
        strokeWidth="0.75"
        strokeLinejoin="round"
      />

      {/* Left Facet */}
      <polygon
        points="5,9.5 16,16 16,29 5,22.5"
        fill="url(#pese-left-grad)"
        stroke="#60a5fa"
        strokeWidth="0.75"
        strokeLinejoin="round"
      />

      {/* Right Facet */}
      <polygon
        points="16,16 27,9.5 27,22.5 16,29"
        fill="url(#pese-right-grad)"
        stroke="#3b82f6"
        strokeWidth="0.75"
        strokeLinejoin="round"
      />

      {/* Central Core Inset & Aperture */}
      <circle cx="16" cy="15.8" r="4.2" fill="url(#pese-core-glow)" />
      <circle
        cx="16"
        cy="15.8"
        r="2"
        fill="#ffffff"
        stroke="#60a5fa"
        strokeWidth="0.75"
      />
    </svg>
  );
};

export const PeseLogo: React.FC<PeseLogoProps> = ({
  size = "md",
  className = "",
  showWordmark = true,
  subtitle,
  badge,
}) => {
  const pixelSize =
    typeof size === "number"
      ? size
      : size === "xs"
      ? 18
      : size === "sm"
      ? 22
      : size === "md"
      ? 28
      : size === "lg"
      ? 36
      : 48;

  return (
    <div className={`flex items-center gap-3 select-none ${className}`}>
      <PeseLogoMark size={pixelSize} />
      {showWordmark && (
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className="font-bold tracking-tight text-neutral-900 dark:text-neutral-50 text-base leading-none">
              PESE
            </span>
            {badge && (
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-neutral-200/80 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 font-medium">
                {badge}
              </span>
            )}
          </div>
          {subtitle && (
            <span className="text-[11px] font-medium text-neutral-500 dark:text-neutral-400 leading-tight mt-0.5">
              {subtitle}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
