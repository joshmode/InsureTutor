"use client";
import { ArrowUpRight, BookOpen } from "lucide-react";
import { COPY } from "@/lib/i18n";
import type { LanguageCode } from "@/lib/types";
export function PlanCard({ language }: { language: LanguageCode }) {
  const c = COPY[language];
  return (
    <section className="reference-card">
      <p className="eyebrow">{c.sourceLabel}</p>
      <a
        className="document-cover"
        href="/source-document"
        target="_blank"
        rel="noreferrer"
        aria-label={c.viewSource}
      >
        <span className="cover-top">
          YF LIFE <BookOpen size={20} />
        </span>
        <span className="cover-title">
          FLEXI-ULife
          <br />
          Prime Saver
        </span>
        <span className="cover-subtitle">首選靈活萬用壽險計劃</span>
        <span className="cover-bottom">
          {c.openPdf}
          <ArrowUpRight size={18} />
        </span>
      </a>
      <h2>{c.productName}</h2>
      <p>{c.productEyebrow}</p>
      <a
        className="document-link"
        href="/source-document"
        target="_blank"
        rel="noreferrer"
      >
        {c.viewSource}
        <ArrowUpRight size={15} />
      </a>
      <div className="reference-note">
        <BookOpen size={18} />
        <p>{c.sourceBody}</p>
      </div>
      <p className="reference-footer">{c.readFirst}</p>
    </section>
  );
}
