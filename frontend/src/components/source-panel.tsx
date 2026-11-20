"use client";

import {
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  FileText,
  X,
} from "lucide-react";
import { useEffect } from "react";
import { COPY } from "@/lib/i18n";
import type { AssistantMessage, Citation, LanguageCode } from "@/lib/types";
import { cn } from "@/lib/utils";

export function SourcePanel({
  language,
  citations,
  activeCitation,
  onSelectCitation,
  open,
  onClose,
  mobile,
  messages,
}: {
  language: LanguageCode;
  citations: Citation[];
  activeCitation: number | null;
  onSelectCitation: (index: number) => void;
  open: boolean;
  onClose: () => void;
  mobile: boolean;
  messages: AssistantMessage[];
}) {
  const copy = COPY[language];
  const latestSources = citations.length ? citations : lastCitations(messages);

  useEffect(() => {
    if (!mobile || !open) return;
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = original;
    };
  }, [mobile, open]);

  useEffect(() => {
    if (!open || activeCitation === null) return;
    document.getElementById(`source-${activeCitation}`)?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }, [activeCitation, open]);

  return (
    <>
      {mobile && open && (
        <button
          type="button"
          aria-label={copy.close}
          onClick={onClose}
          className="fixed inset-0 z-50 bg-ink-950/30 backdrop-blur-[2px] lg:hidden"
        />
      )}
      <aside
        aria-label={copy.sources}
        className={cn(
          "z-50 flex flex-col border-ink-900/[0.08] bg-cream-100/55",
          mobile
            ? "fixed inset-y-0 right-0 w-[min(92vw,390px)] border-l bg-cream-50 shadow-lift transition-transform duration-300"
            : "sticky top-[68px] h-[calc(100vh-68px)] w-[360px] shrink-0 border-l xl:w-[390px]",
          mobile && !open && "translate-x-full",
        )}
      >
        <div className="flex items-start justify-between gap-3 border-b border-ink-900/[0.08] px-5 py-5">
          <div>
            <p className="mb-1 flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-[0.16em] text-jade-700">
              <BookOpen size={11} aria-hidden="true" />
              {copy.sourceDrawerKicker}
            </p>
            <h2 className="font-display text-[1.25rem] font-semibold tracking-[-0.02em] text-ink-950">
              {copy.sources}
            </h2>
            <p className="mt-1.5 max-w-[270px] text-[11px] leading-5 text-ink-500">
              {copy.sourceDrawerBody}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={copy.close}
            className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-ink-500 transition hover:bg-white hover:text-ink-900"
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>

        <div className="custom-scrollbar flex-1 overflow-y-auto px-3 py-3">
          {latestSources.length === 0 ? (
            <div className="mx-2 mt-3 rounded-2xl border border-dashed border-ink-900/15 bg-white/40 px-4 py-6 text-center">
              <FileText size={22} className="mx-auto mb-2 text-ink-500/40" aria-hidden="true" />
              <p className="text-[12px] text-ink-500">{copy.noSources}</p>
            </div>
          ) : (
            <div className="space-y-2">
              {latestSources.map((citation, index) => (
                <CitationCard
                  key={`${citation.id}-${index}`}
                  citation={citation}
                  index={index + 1}
                  language={language}
                  active={activeCitation === index + 1}
                  onClick={() => onSelectCitation(index + 1)}
                />
              ))}
            </div>
          )}
        </div>

        <div className="border-t border-ink-900/[0.08] p-4">
          <a
            href="/source-document"
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-between rounded-xl border border-ink-900/10 bg-white/80 px-3.5 py-3 transition hover:border-jade-700/30 hover:bg-white"
          >
            <span className="flex min-w-0 items-center gap-2.5">
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-red-50 text-red-600">
                <FileText size={15} aria-hidden="true" />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-[11.5px] font-bold text-ink-900">
                  {copy.productName}
                </span>
                <span className="block text-[10px] text-ink-500">PDF · 20 pages</span>
              </span>
            </span>
            <ArrowUpRight size={14} className="shrink-0 text-ink-500" aria-hidden="true" />
          </a>
        </div>
      </aside>
    </>
  );
}

function CitationCard({
  citation,
  index,
  language,
  active,
  onClick,
}: {
  citation: Citation;
  index: number;
  language: LanguageCode;
  active: boolean;
  onClick: () => void;
}) {
  const copy = COPY[language];
  return (
    <article
      id={`source-${index}`}
      className={cn(
        "scroll-mt-3 overflow-hidden rounded-2xl border bg-white/70 transition",
        active
          ? "border-jade-700/35 shadow-card ring-1 ring-jade-700/10"
          : "border-ink-900/[0.08] hover:border-ink-900/15 hover:bg-white",
      )}
    >
      <button
        type="button"
        onClick={onClick}
        aria-expanded={active}
        className="flex w-full items-center justify-between gap-2 px-3.5 py-3 text-left"
      >
        <span className="flex min-w-0 items-center gap-2.5">
          <span
            className={cn(
              "grid h-6 w-6 shrink-0 place-items-center rounded-md font-mono text-[10px] font-bold",
              active ? "bg-jade-700 text-white" : "bg-cream-100 text-ink-700",
            )}
          >
            {index}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-[11px] font-bold text-ink-900">
              {citation.section || citation.document}
            </span>
            <span className="block text-[9.5px] text-ink-500">
              {copy.page} {citation.page} · {citation.document}
            </span>
          </span>
        </span>
        <ChevronRight
          size={14}
          className={cn(
            "shrink-0 text-ink-500 transition-transform",
            active && "rotate-90 text-jade-700",
          )}
          aria-hidden="true"
        />
      </button>
      {active && (
        <div className="animate-fade-up border-t border-ink-900/[0.06] px-3.5 pb-3.5 pt-3">
          <p className="mb-1.5 text-[8.5px] font-bold uppercase tracking-[0.15em] text-ink-500">
            {copy.excerpt}
          </p>
          <div className="custom-scrollbar max-h-[235px] overflow-y-auto whitespace-pre-wrap rounded-lg bg-cream-50 px-3 py-2.5 text-[11.5px] leading-[1.7] text-ink-700">
            {citation.excerpt}
          </div>
        </div>
      )}
    </article>
  );
}

function lastCitations(messages: AssistantMessage[]): Citation[] {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].citations.length) return messages[index].citations;
  }
  return [];
}

