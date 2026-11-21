"use client";
import { ArrowUpRight } from "lucide-react";
import { COPY } from "@/lib/i18n";
import type { LanguageCode } from "@/lib/types";
export function WelcomePanel({
  language,
  onSelectPrompt,
}: {
  language: LanguageCode;
  onSelectPrompt: (prompt: string) => void;
}) {
  const copy = COPY[language];
  return (
    <section className="welcome">
      <p className="eyebrow">{copy.welcomeKicker}</p>
      <h1>{copy.welcomeTitle}</h1>
      <p className="welcome-body">{copy.welcomeBody}</p>
      <div className="suggestions">
        <h2 className="eyebrow">{copy.suggestionsLabel}</h2>
        <div className="suggestion-grid">
          {copy.suggestions.map((s, i) => (
            <button key={s.title} onClick={() => onSelectPrompt(s.prompt)}>
              <span className="suggestion-number">0{i + 1}</span>
              <span>
                <strong>{s.title}</strong>
                <span className="suggestion-prompt">{s.prompt}</span>
              </span>
              <ArrowUpRight size={17} aria-hidden="true" />
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
