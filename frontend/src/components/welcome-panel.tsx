"use client";

import {
  ArrowRight,
  BadgeDollarSign,
  BookOpenText,
  Landmark,
  Sparkles,
  WalletCards,
} from "lucide-react";
import { COPY } from "@/lib/i18n";
import type { LanguageCode } from "@/lib/types";

const ICONS = [BookOpenText, BadgeDollarSign, WalletCards, Landmark];

export function WelcomePanel({
  language,
  onSelectPrompt,
}: {
  language: LanguageCode;
  onSelectPrompt: (prompt: string) => void;
}) {
  const copy = COPY[language];
  return (
    <div className="mx-auto flex w-full max-w-[790px] animate-fade-up flex-col justify-center px-1 pb-6 pt-8 sm:pt-10">
      <div className="mb-7">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-jade-700/15 bg-jade-50 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-jade-800">
          <Sparkles size={13} aria-hidden="true" />
          {copy.welcomeKicker}
        </div>
        <h1 className="max-w-[650px] font-display text-[2.25rem] font-medium leading-[1.08] tracking-[-0.04em] text-ink-950 sm:text-[3.1rem]">
          {copy.welcomeTitle}
        </h1>
        <p className="mt-4 max-w-[610px] text-[14px] leading-7 text-ink-700 sm:text-[15px]">
          {copy.welcomeBody}
        </p>
      </div>

      <div>
        <p className="mb-3 text-[10px] font-bold uppercase tracking-[0.16em] text-ink-500">
          {copy.suggestionsLabel}
        </p>
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          {copy.suggestions.map((suggestion, index) => {
            const Icon = ICONS[index];
            return (
              <button
                type="button"
                key={suggestion.title}
                onClick={() => onSelectPrompt(suggestion.prompt)}
                className="group relative min-h-[110px] overflow-hidden rounded-2xl border border-ink-900/[0.09] bg-white/75 p-4 text-left shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-jade-700/30 hover:bg-white hover:shadow-lift focus-visible:outline-none"
                style={{ animationDelay: `${index * 55}ms` }}
              >
                <span className="mb-4 flex items-center justify-between">
                  <span className="grid h-8 w-8 place-items-center rounded-lg bg-cream-100 text-jade-800 transition group-hover:bg-jade-50">
                    <Icon size={16} strokeWidth={1.8} aria-hidden="true" />
                  </span>
                  <ArrowRight
                    size={15}
                    className="text-ink-500/40 transition group-hover:translate-x-0.5 group-hover:text-jade-700"
                    aria-hidden="true"
                  />
                </span>
                <span className="block text-[13px] font-bold text-ink-900">
                  {suggestion.title}
                </span>
                <span className="mt-1 line-clamp-2 block text-[12px] leading-5 text-ink-500">
                  {suggestion.prompt}
                </span>
              </button>
            );
          })}
        </div>
      </div>
      <p className="mt-5 flex items-start gap-2 text-[11px] leading-5 text-ink-500">
        <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-jade-500" />
        {copy.chatEmptyPrompt}
      </p>
    </div>
  );
}

