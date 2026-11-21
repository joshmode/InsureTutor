"use client";
import { ArrowUpRight, BookOpen } from "lucide-react";
import { COPY } from "@/lib/i18n";
import type { BrochureInfo, LanguageCode } from "@/lib/types";
import { BROCHURE_COPY } from "@/lib/brochure-copy";
export function PlanCard({ language, brochure }: { language: LanguageCode; brochure?: BrochureInfo | null }) {
  const c = COPY[language];
  const u = BROCHURE_COPY[language];
  const pageCount = brochure ? `${brochure.pages} ${brochure.pages === 1 && language === "en" ? "page" : u.pages}` : "";
  if (brochure) return <section className="reference-card">
    <p className="eyebrow">{u.private}</p>
    <a className="document-cover uploaded-cover" href={`/source-document?brochure_id=${brochure.id}`} target="_blank" rel="noreferrer" aria-label={c.viewSource}>
      <span className="cover-top">PDF <BookOpen size={20} /></span><span className="cover-title">{brochure.filename}</span>
      <span className="cover-subtitle">{pageCount}</span><span className="cover-bottom">{c.openPdf}<ArrowUpRight size={18} /></span>
    </a>
    <h2>{brochure.filename}</h2><p>{pageCount}</p>
    <div className="reference-note"><BookOpen size={18}/><p>{u.body}</p></div>
    {brochure.retrieval_mode !== "hybrid" && <p role="status">{u.lexical}</p>}
    <p className="reference-footer">{u.privacy}</p>
  </section>;
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
