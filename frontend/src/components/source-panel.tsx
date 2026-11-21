"use client";
import { ArrowUpRight, BookOpen, ChevronDown, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { COPY } from "@/lib/i18n";
import type { Citation, LanguageCode } from "@/lib/types";
export function SourcePanel({
  language,
  citations,
  activeCitation,
  onSelectCitation,
  open,
  onClose,
  brochureId,
}: {
  language: LanguageCode;
  citations: Citation[];
  activeCitation: number | null;
  onSelectCitation: (index: number) => void;
  open: boolean;
  onClose: () => void;
  brochureId?: string;
}) {
  const c = COPY[language],
    ref = useRef<HTMLDialogElement>(null);
  const selectedDocument =
    citations[(activeCitation ?? 1) - 1]?.document ?? citations[0]?.document;
  const sourceHref = (document?: string) =>
    brochureId ? `/source-document?brochure_id=${brochureId}${document ? `&document=${encodeURIComponent(document)}` : ""}` : document
      ? `/source-document?document=${encodeURIComponent(document)}`
      : "/source-document";
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    else if (!open && d.open) d.close();
    const prior = document.body.style.overflow;
    if (open) document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prior;
    };
  }, [open]);
  useEffect(() => {
    if (open)
      ref.current
        ?.querySelector(`[data-source="${activeCitation}"]`)
        ?.scrollIntoView({ block: "nearest" });
  }, [open, activeCitation, citations]);
  return (
    <dialog
      ref={ref}
      className="source-dialog"
      aria-labelledby="sources-heading"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const controls = [
          ...event.currentTarget.querySelectorAll<HTMLElement>(
            'button:not([disabled]), a[href], select, textarea, [tabindex="0"]',
          ),
        ].filter((element) => element.getClientRects().length);
        const first = controls[0],
          last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      <div className="source-dialog-content">
        <header className="source-header">
          <div>
            <p className="eyebrow">{c.sourceDrawerKicker}</p>
            <h2 id="sources-heading">{c.sources}</h2>
          </div>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label={c.close}
            autoFocus
          >
            <X size={20} />
          </button>
        </header>
        <p className="source-intro">{c.sourceDrawerBody}</p>
        <div className="source-list custom-scrollbar">
          {citations.length === 0 ? (
            <div className="source-empty">
              <BookOpen size={28} />
              <p>{c.noSources}</p>
            </div>
          ) : (
            citations.map((citation, i) => (
              <article
                key={citation.id}
                data-source={i + 1}
                className={`source-card ${activeCitation === i + 1 ? "source-active" : ""}`}
              >
                <button
                  className="source-toggle"
                  onClick={() =>
                    onSelectCitation(activeCitation === i + 1 ? 0 : i + 1)
                  }
                  aria-expanded={activeCitation === i + 1}
                  aria-controls={`excerpt-${i}`}
                >
                  <span className="source-number">{i + 1}</span>
                  <span>
                    <strong>{citation.section || citation.document}</strong>
                    <small>
                      {c.page} {citation.page} · PDF
                    </small>
                  </span>
                  <ChevronDown size={16} />
                </button>
                {activeCitation === i + 1 && (
                  <div className="source-excerpt" id={`excerpt-${i}`}>
                    <p className="eyebrow">{c.excerpt}</p>
                    <blockquote>{citation.excerpt}</blockquote>
                    <a
                      href={`${sourceHref(citation.document)}#page=${citation.page}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {c.openPdf} · {c.page} {citation.page}
                      <ArrowUpRight size={15} />
                    </a>
                  </div>
                )}
              </article>
            ))
          )}
        </div>
        <footer>
          <a
            className="document-link"
            href={sourceHref(selectedDocument)}
            target="_blank"
            rel="noreferrer"
          >
            {c.viewSource}
            <ArrowUpRight size={17} />
          </a>
        </footer>
      </div>
    </dialog>
  );
}
