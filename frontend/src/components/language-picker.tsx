"use client";
import { Languages } from "lucide-react";
import { COPY, LANGUAGES } from "@/lib/i18n";
import type { LanguageCode } from "@/lib/types";
export function LanguagePicker({
  value,
  onChange,
}: {
  value: LanguageCode;
  onChange: (value: LanguageCode) => void;
}) {
  return (
    <label className="language-picker">
      <Languages size={17} aria-hidden="true" />
      <span className="sr-only">{COPY[value].language}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as LanguageCode)}
      >
        {LANGUAGES.map((l) => (
          <option key={l.code} value={l.code}>
            {l.native}
          </option>
        ))}
      </select>
    </label>
  );
}
