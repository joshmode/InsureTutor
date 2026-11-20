"use client";

import { ArrowUpRight, CheckCircle2, Info, ShieldCheck } from "lucide-react";
import { COPY } from "@/lib/i18n";
import type { LanguageCode } from "@/lib/types";

export function PlanCard({ language }: { language: LanguageCode }) {
  const copy = COPY[language];
  return (
    <section className="mb-3 rounded-2xl border border-ink-900/[0.08] bg-white/55 p-3.5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="mb-1 text-[8.5px] font-bold uppercase tracking-[0.15em] text-jade-700">
            {copy.sourceTitle}
          </p>
          <h3 className="font-display text-[15px] font-semibold leading-tight text-ink-950">
            {copy.companionTitle}
          </h3>
        </div>
        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-jade-50 text-jade-700">
          <ShieldCheck size={14} aria-hidden="true" />
        </span>
      </div>
      <p className="mt-2 text-[10.5px] leading-[1.65] text-ink-500">{copy.companionBody}</p>
      <div className="mt-3 space-y-1.5">
        {copy.planFacts.map((fact) => (
          <div
            key={fact.label}
            className="flex items-center justify-between gap-3 border-t border-ink-900/[0.05] pt-1.5 text-[9.5px]"
          >
            <span className="flex items-center gap-1.5 text-ink-500">
              <CheckCircle2 size={10} className="text-jade-600" aria-hidden="true" />
              {fact.label}
            </span>
            <span className="text-right font-semibold text-ink-700">{fact.value}</span>
          </div>
        ))}
      </div>
      <a
        href="/source-document"
        target="_blank"
        rel="noreferrer"
        className="mt-3 flex items-center justify-between rounded-lg bg-cream-100 px-2.5 py-2 text-[9.5px] font-semibold text-ink-700 transition hover:bg-jade-50 hover:text-jade-800"
      >
        <span className="flex items-center gap-1.5">
          <Info size={10} aria-hidden="true" />
          {copy.viewSource}
        </span>
        <ArrowUpRight size={11} aria-hidden="true" />
      </a>
    </section>
  );
}

