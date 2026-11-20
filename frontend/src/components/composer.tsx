"use client";

import { ArrowUp, CornerDownLeft, LoaderCircle } from "lucide-react";
import { useEffect, useRef } from "react";
import { COPY } from "@/lib/i18n";
import type { LanguageCode } from "@/lib/types";

export function Composer({
  language,
  value,
  onChange,
  onSubmit,
  loading,
  onStop,
}: {
  language: LanguageCode;
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
  onStop: () => void;
}) {
  const copy = COPY[language];
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const textarea = ref.current;
    if (!textarea) return;
    textarea.style.height = "0px";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 168)}px`;
  }, [value]);

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (!loading && value.trim()) onSubmit();
    }
  }

  return (
    <div className="relative rounded-[22px] border border-ink-900/[0.13] bg-white shadow-lift ring-1 ring-transparent transition focus-within:border-jade-700/30 focus-within:ring-jade-700/[0.05]">
      <textarea
        ref={ref}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        rows={1}
        maxLength={4000}
        aria-label={copy.composerPlaceholder}
        placeholder={copy.composerPlaceholder}
        disabled={loading}
        className="custom-scrollbar block max-h-[168px] min-h-[58px] w-full resize-none bg-transparent px-4 pb-2 pt-4 text-[14px] leading-6 text-ink-900 outline-none placeholder:text-ink-500/80 disabled:opacity-60 sm:px-5"
      />
      <div className="flex items-center justify-between gap-3 px-3 pb-2.5 pl-4 sm:pl-5">
        <p className="flex items-center gap-1.5 text-[9.5px] font-medium text-ink-500/80">
          <CornerDownLeft size={10} aria-hidden="true" />
          Enter to send · Shift + Enter for a new line
        </p>
        {loading ? (
          <button
            type="button"
            onClick={onStop}
            className="flex h-9 items-center gap-1.5 rounded-full bg-cream-200 px-3 text-[11px] font-bold text-ink-700 transition hover:bg-cream-100"
          >
            <LoaderCircle size={13} className="animate-spin" aria-hidden="true" />
            {copy.stop}
          </button>
        ) : (
          <button
            type="button"
            onClick={onSubmit}
            disabled={!value.trim()}
            aria-label={copy.send}
            className="grid h-9 w-9 place-items-center rounded-full bg-jade-900 text-white shadow-sm transition hover:bg-jade-700 disabled:cursor-not-allowed disabled:bg-cream-200 disabled:text-ink-500/50"
          >
            <ArrowUp size={17} strokeWidth={2.4} aria-hidden="true" />
          </button>
        )}
      </div>
    </div>
  );
}

