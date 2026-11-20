"use client";

import { FileText, Menu, MessageSquarePlus, ShieldCheck } from "lucide-react";
import { COPY } from "@/lib/i18n";
import type { LanguageCode } from "@/lib/types";
import { LanguagePicker } from "./language-picker";
import { Logo } from "./logo";

export function AppHeader({
  language,
  onLanguageChange,
  onNewChat,
  onOpenSources,
  conversationsStarted,
}: {
  language: LanguageCode;
  onLanguageChange: (language: LanguageCode) => void;
  onNewChat: () => void;
  onOpenSources: () => void;
  conversationsStarted: boolean;
}) {
  const copy = COPY[language];
  return (
    <header className="sticky top-0 z-[70] border-b border-ink-900/[0.08] bg-cream-50/90 backdrop-blur-xl">
      <div className="mx-auto flex h-[68px] max-w-[1440px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-4">
          <Logo />
          <span className="hidden h-7 w-px bg-ink-900/10 sm:block" aria-hidden="true" />
          <div className="hidden min-w-0 sm:block">
            <p className="truncate text-[13px] font-bold text-ink-900">{copy.productName}</p>
            <p className="truncate text-[11px] text-ink-500">{copy.productEyebrow}</p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2">
          <button
            type="button"
            onClick={onOpenSources}
            className="hidden h-10 items-center gap-2 rounded-full px-3.5 text-[12px] font-semibold text-ink-700 transition hover:bg-white/70 hover:text-jade-800 lg:flex"
          >
            <FileText size={15} aria-hidden="true" />
            {copy.sourceTitle}
            <span className="ml-0.5 flex h-5 items-center rounded-full bg-jade-100 px-1.5 text-[10px] font-bold text-jade-800">
              20
            </span>
          </button>
          <div className="hidden items-center gap-1.5 rounded-full border border-amber-600/15 bg-amber-50 px-3 py-2 text-[10px] font-bold uppercase tracking-[0.08em] text-amber-600 xl:flex">
            <ShieldCheck size={13} aria-hidden="true" />
            {copy.educationalBadge}
          </div>
          <LanguagePicker value={language} onChange={onLanguageChange} />
          <button
            type="button"
            onClick={onNewChat}
            disabled={!conversationsStarted}
            className="flex h-10 items-center gap-2 rounded-full bg-ink-950 px-3.5 text-[12px] font-semibold text-cream-50 transition hover:bg-jade-900 disabled:cursor-not-allowed disabled:opacity-35"
          >
            <MessageSquarePlus size={15} aria-hidden="true" />
            <span className="hidden md:inline">{copy.newChat}</span>
            <Menu size={15} className="md:hidden" aria-hidden="true" />
          </button>
        </div>
      </div>
    </header>
  );
}

