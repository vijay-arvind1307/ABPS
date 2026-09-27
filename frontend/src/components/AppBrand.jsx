import React, { useState } from 'react';

/**
 * Reusable AppBrand component for the official Automatic Block Planning System (ABPS).
 * Implements official logo asset handling, aspect-ratio preservation,
 * consistent typography hierarchy, and a graceful layout-safe fallback.
 */
export default function AppBrand({
  variant = 'header', // 'header' | 'login' | 'compact' | 'sidebar' | 'control-room'
  logoHeight,
  showSubtitle = true,
  className = '',
  logoClassName = '',
  onClick
}) {
  const [logoFailed, setLogoFailed] = useState(false);

  // Variant-specific styling presets
  const isHeader = variant === 'header';
  const isLogin = variant === 'login';
  const isCompact = variant === 'compact' || variant === 'sidebar';

  // Scaled logo heights for high visual prominence
  const defaultHeight = isLogin
    ? '96px'
    : isHeader
    ? '68px'
    : isCompact
    ? '52px'
    : '68px';

  const resolvedHeight = logoHeight || defaultHeight;

  return (
    <div
      onClick={onClick}
      className={`inline-flex items-center gap-3.5 select-none ${
        onClick ? 'cursor-pointer' : ''
      } ${isLogin ? 'flex-col justify-center text-center' : ''} ${className}`}
    >
      {/* ── Official Project Logo with Graceful Fallback ── */}
      <div className="shrink-0 flex items-center justify-center">
        {!logoFailed ? (
          <img
            src="/logo.png?v=2"
            alt="ABPS — Automatic Block Planning System"
            onError={() => setLogoFailed(true)}
            style={{
              height: resolvedHeight,
              width: resolvedHeight,
              maxHeight: resolvedHeight,
              maxWidth: resolvedHeight,
              objectFit: 'contain'
            }}
            className={`transition-opacity duration-200 block rounded-full ring-2 ring-white/40 shadow-md ${logoClassName}`}
            loading="eager"
          />
        ) : (
          /* Graceful Fallback: Preserves layout without collapsing */
          <div
            style={{ height: resolvedHeight, minWidth: resolvedHeight }}
            className="bg-[#0B2545] border-2 border-[#FFB703] text-[#FFB703] font-black text-xs font-mono flex items-center justify-center px-2 shadow-xs"
            title="ABPS — Automatic Block Planning System"
          >
            ABPS
          </div>
        )}
      </div>

      {/* ── Typography Hierarchy ── */}
      <div
        className={`flex flex-col justify-center ${
          isLogin ? 'items-center mt-2' : ''
        }`}
      >
        {/* Primary Identifier */}
        <span
          className={`font-black tracking-wider leading-none uppercase font-sans ${
            isLogin
              ? 'text-2xl text-white tracking-widest'
              : isHeader
              ? 'text-lg font-black text-white'
              : isCompact
              ? 'text-xs font-bold text-white'
              : 'text-sm text-[#0B2545]'
          }`}
        >
          ABPS
        </span>

        {/* Full Application Name */}
        {showSubtitle && (
          <span
            className={`tracking-normal leading-tight font-sans mt-0.5 ${
              isLogin
                ? 'text-xs text-slate-200 font-medium'
                : isHeader
                ? 'text-xs text-slate-300 font-medium'
                : isCompact
                ? 'text-[9.5px] text-slate-300 font-normal'
                : 'text-xs text-slate-600 font-medium'
            }`}
          >
            Automatic Block Planning System
          </span>
        )}
      </div>
    </div>
  );
}
