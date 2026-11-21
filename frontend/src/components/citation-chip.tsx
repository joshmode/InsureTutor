"use client";

import { FileText } from "lucide-react";
import type { Citation } from "@/lib/types";
import { cn } from "@/lib/utils";

export function CitationChip({
  index,
  citation,
  active,
  onClick,
}: {
  index: number;
  citation: Citation;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Citation ${index}: ${citation.document}, page ${citation.page}`}
      className={cn(
        "group inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 align-middle text-[11px] font-bold transition",
        active
          ? "border-jade-700 bg-jade-700 text-white shadow-sm"
          : "border-jade-700/20 bg-jade-50 text-jade-800 hover:border-jade-700/50 hover:bg-jade-100",
      )}
    >
      <FileText size={12} strokeWidth={2.2} aria-hidden="true" />
      {index}
      <span className="hidden font-medium opacity-80 sm:inline">
        p.{citation.page}
      </span>
    </button>
  );
}
