"use client";
import ReactMarkdown, { type Components } from "react-markdown";
import { createContext, useContext } from "react";
import remarkGfm from "remark-gfm";
import type { Citation, LanguageCode } from "@/lib/types";
import { CitationChip } from "./citation-chip";

type MarkdownNode = {
  type: string;
  value?: string;
  url?: string;
  children?: MarkdownNode[];
};
// Transform text nodes, so citations work inside emphasis, lists and tables.
// Skip links and code: model-supplied URLs never become evidence controls.
function citationLinks() {
  return (tree: MarkdownNode) => {
    function visit(node: MarkdownNode) {
      if (!node.children || ["link", "code", "inlineCode"].includes(node.type))
        return;
      node.children = node.children.flatMap((child) => {
        if (child.type !== "text") {
          visit(child);
          return [child];
        }
        return (child.value ?? "")
          .split(/(\[\d{1,2}\])/g)
          .filter(Boolean)
          .map((part) => {
            const match = part.match(/^\[(\d{1,2})\]$/);
            return match
              ? {
                  type: "link",
                  url: `#citation-${match[1]}`,
                  children: [{ type: "text", value: part }],
                }
              : { type: "text", value: part };
          });
      });
    }
    visit(tree);
  };
}
type CitationContextValue = {
  language: LanguageCode;
  citations: Citation[];
  activeCitation: number | null;
  onCitationClick: (index: number) => void;
};
const CitationContext = createContext<CitationContextValue>({
  language: "en",
  citations: [],
  activeCitation: null,
  onCitationClick: () => {},
});
// Stable component identities preserve citation focus across answer selection.
const markdownComponents: Components = {
  a: function EvidenceLink({ href, children }) {
    const { citations, activeCitation, onCitationClick, language } =
      useContext(CitationContext);
    const match = href?.match(/^#citation-(\d+)$/);
    const index = match ? Number(match[1]) : 0;
    const citation = citations[index - 1];
    return citation ? (
      <CitationChip
        index={index}
        citation={citation}
        active={activeCitation === index}
        onClick={() => onCitationClick(index)}
        language={language}
      />
    ) : (
      <>{children}</>
    );
  },
  table: function EvidenceTable({ children }) {
    return (
      <div className="table-scroll" tabIndex={0}>
        <table>{children}</table>
      </div>
    );
  },
};
export function AnswerMarkdown({
  text,
  ...context
}: CitationContextValue & { text: string }) {
  return (
    <CitationContext.Provider value={context}>
      <div className="markdown">
        <ReactMarkdown
          disallowedElements={["img"]}
          remarkPlugins={[remarkGfm, citationLinks]}
          components={markdownComponents}
        >
          {text}
        </ReactMarkdown>
      </div>
    </CitationContext.Provider>
  );
}
