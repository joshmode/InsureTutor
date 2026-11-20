"use client";

import { Check, ChevronDown, Languages } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { COPY, LANGUAGES } from "@/lib/i18n";
import type { LanguageCode } from "@/lib/types";
import { cn } from "@/lib/utils";

export function LanguagePicker({
  value,
  onChange,
}: {
  value: LanguageCode;
  onChange: (value: LanguageCode) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const active = LANGUAGES.find((item) => item.code === value) ?? LANGUAGES[0];

  useEffect(() => {
    function handleOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  return (
    <div ref={ref} className="relative z-[80]">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`${COPY[value].language}: ${active.native}`}
        onClick={() => setOpen((current) => !current)}
        className="flex h-10 items-center gap-2 rounded-full border border-ink-900/10 bg-white/70 px-3 text-[13px] font-semibold text-ink-900 transition hover:border-jade-700/30 hover:bg-white"
      >
        <Languages size={16} className="text-jade-700" aria-hidden="true" />
        <span>{active.short}</span>
        <span className="hidden text-ink-500 sm:inline">{active.native}</span>
        <ChevronDown
          size={14}
          className={cn("text-ink-500 transition-transform", open && "rotate-180")}
          aria-hidden="true"
        />
      </button>
      {open && (
        <div
          role="listbox"
          aria-label={COPY[value].language}
          className="absolute right-0 top-12 z-[80] w-56 rounded-2xl border border-ink-900/10 bg-white p-1.5 shadow-lift"
        >
          <p className="px-3 pb-1.5 pt-2 text-[10px] font-bold uppercase tracking-[0.15em] text-ink-500">
            {COPY[value].language}
          </p>
          {LANGUAGES.map((language) => (
            <button
              key={language.code}
              type="button"
              role="option"
              aria-selected={language.code === value}
              onClick={() => {
                onChange(language.code);
                setOpen(false);
              }}
              className={cn(
                "flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left transition",
                language.code === value
                  ? "bg-jade-50 text-jade-900"
                  : "text-ink-700 hover:bg-cream-100",
              )}
            >
              <span>
                <span className="block text-[13px] font-semibold">{language.native}</span>
                <span className="block text-[11px] text-ink-500">{language.english}</span>
              </span>
              {language.code === value && (
                <Check size={15} className="text-jade-700" aria-hidden="true" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

