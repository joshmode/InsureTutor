"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Citation } from "@/lib/types";
import { CitationChip } from "./citation-chip";

export function AnswerMarkdown({
  text,
  citations,
  activeCitation,
  onCitationClick,
}: {
  text: string;
  citations: Citation[];
  activeCitation: number | null;
  onCitationClick: (index: number) => void;
}) {
  const withChips = text.split(/(\[\d{1,2}\])/g).map((part, index) => {
    const match = part.match(/^\[(\d{1,2})\]$/);
    if (!match) return part;
    const citationIndex = Number(match[1]);
    const citation = citations[citationIndex - 1];
    if (!citation) return "";
    return `[[[C${citationIndex}]]]`;
  }).join("");

  return (
    <div className="markdown text-[14.5px] leading-[1.72] text-ink-700">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => {
            const content = renderCitationPlaceholders(
              children,
              citations,
              activeCitation,
              onCitationClick,
            );
            return <p>{content}</p>;
          },
          li: ({ children }) => {
            const content = renderCitationPlaceholders(
              children,
              citations,
              activeCitation,
              onCitationClick,
            );
            return <li>{content}</li>;
          },
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {withChips}
      </ReactMarkdown>
    </div>
  );
}

function renderCitationPlaceholders(
  children: React.ReactNode,
  citations: Citation[],
  activeCitation: number | null,
  onCitationClick: (index: number) => void,
): React.ReactNode {
  return Array.isArray(children)
    ? children.flatMap((child, index) =>
        typeof child === "string"
          ? splitCitationText(
              child,
              `k${index}`,
              citations,
              activeCitation,
              onCitationClick,
            )
          : child,
      )
    : typeof children === "string"
      ? splitCitationText(
          children,
          "single",
          citations,
          activeCitation,
          onCitationClick,
        )
      : children;
}

function splitCitationText(
  text: string,
  key: string,
  citations: Citation[],
  activeCitation: number | null,
  onCitationClick: (index: number) => void,
): React.ReactNode[] {
  return text.split(/(\[\[\[C\d{1,2}\]\]\])/g).map((part, index) => {
    const match = part.match(/^\[\[\[C(\d{1,2})\]\]\]$/);
    if (!match) return <span key={`${key}-${index}`}>{part}</span>;
    const citationIndex = Number(match[1]);
    const citation = citations[citationIndex - 1];
    if (!citation) return null;
    return (
      <span key={`${key}-c-${citationIndex}-${index}`} className="mx-0.5 inline-block">
        <CitationChip
          index={citationIndex}
          citation={citation}
          active={activeCitation === citationIndex}
          onClick={() => onCitationClick(citationIndex)}
        />
      </span>
    );
  });
}

