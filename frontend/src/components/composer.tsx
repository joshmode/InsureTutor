"use client";
import { ArrowUp, Square } from "lucide-react";
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
  const c = COPY[language],
    ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = "auto";
      ref.current.style.height = `${Math.min(ref.current.scrollHeight, 160)}px`;
    }
  }, [value]);
  return (
    <form
      className="composer"
      onSubmit={(e) => {
        e.preventDefault();
        if (value.trim() && !loading) onSubmit();
      }}
    >
      <label className="sr-only" htmlFor="question">
        {c.composerPlaceholder}
      </label>
      <textarea
        id="question"
        ref={ref}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={c.composerPlaceholder}
        rows={2}
        maxLength={4000}
        onKeyDown={(e) => {
          if (
            e.key === "Enter" &&
            !e.shiftKey &&
            !e.nativeEvent.isComposing &&
            e.keyCode !== 229
          ) {
            e.preventDefault();
            if (value.trim() && !loading) onSubmit();
          }
        }}
      />
      <div className="composer-tools">
        <span>{c.enterHint}</span>
        <span className="composer-count" aria-live="off">
          {value.length > 3500 ? `${value.length}/4000` : ""}
        </span>
        {loading ? (
          <button
            type="button"
            className="send-button"
            onClick={(event) => {
              // Stopping can synchronously replace this node with the submit
              // button. Prevent that click's default action from sending a draft.
              event.preventDefault();
              onStop();
            }}
            aria-label={c.stop}
          >
            <Square size={16} />
          </button>
        ) : (
          <button
            className="send-button"
            type="submit"
            disabled={!value.trim()}
            aria-label={c.send}
          >
            <ArrowUp size={20} />
          </button>
        )}
      </div>
    </form>
  );
}
