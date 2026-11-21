"use client";

import {
  AlertCircle,
  BookMarked,
  Check,
  Copy,
  Info,
  ShieldAlert,
} from "lucide-react";
import { useState } from "react";
import { COPY } from "@/lib/i18n";
import type { AssistantMessage, LanguageCode, UserMessage } from "@/lib/types";
import { cn } from "@/lib/utils";
import { AnswerMarkdown } from "./answer-markdown";

export function UserBubble({ message }: { message: UserMessage }) {
  return (
    <div className="user-message">
      <div className="user-message-body">
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
      </div>
    </div>
  );
}

export function AssistantBubble({
  message,
  language,
  activeCitation,
  onCitationClick,
}: {
  message: AssistantMessage;
  language: LanguageCode;
  activeCitation: number | null;
  onCitationClick: (index: number) => void;
}) {
  const copy = COPY[language];
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);

  async function copyAnswer() {
    setCopyFailed(false);
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
      setCopyFailed(true);
    }
  }

  if (message.pending) {
    return (
      <div className="assistant-message" role="status">
        <AssistantAvatar />
        <div className="flex min-h-[76px] items-center gap-3 rounded-[20px] rounded-tl-[7px] border border-ink-900/[0.08] bg-white/75 px-4 py-3 shadow-card">
          <span className="flex gap-1" aria-hidden="true">
            {[0, 1, 2].map((index) => (
              <span
                key={index}
                className="h-1.5 w-1.5 animate-soft-pulse rounded-full bg-jade-600"
                style={{ animationDelay: `${index * 180}ms` }}
              />
            ))}
          </span>
          <span className="text-[12px] font-medium text-ink-500">
            {copy.loading}
          </span>
        </div>
      </div>
    );
  }

  const status = statusFor(message.kind, language);

  return (
    <div className="assistant-message">
      <AssistantAvatar />
      <div className="assistant-body">
        {status && (
          <div
            className={cn(
              "mb-2 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.09em]",
              status.tone,
            )}
          >
            <status.icon size={11} aria-hidden="true" />
            {status.label}
          </div>
        )}
        <div className="answer-body">
          <AnswerMarkdown
            language={language}
            text={message.content}
            citations={message.citations}
            activeCitation={activeCitation}
            onCitationClick={onCitationClick}
          />

          {message.notices.length > 0 && (
            <div className="mt-3.5 border-t border-ink-900/[0.07] pt-3">
              <p className="flex items-start gap-1.5 text-[12px] leading-5 text-ink-500">
                <Info
                  size={12}
                  className="mt-0.5 shrink-0 text-jade-700"
                  aria-hidden="true"
                />
                <span>
                  {message.notices.map((notice) => (
                    <span className="block mb-2" key={notice}>
                      {notice}
                    </span>
                  ))}
                </span>
              </p>
            </div>
          )}

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-ink-900/[0.06] pt-2.5">
            <div className="flex flex-wrap items-center gap-1.5">
              {message.citations.length > 0 ? (
                <button
                  type="button"
                  onClick={() => onCitationClick(1)}
                  className="inline-flex items-center gap-1.5 rounded-full bg-cream-100 px-2.5 py-1 text-[12px] font-semibold text-ink-700 transition hover:bg-jade-50 hover:text-jade-800"
                >
                  <BookMarked size={11} aria-hidden="true" />
                  {message.citations.length} {copy.citations}
                </button>
              ) : (
                <span className="text-[10px] text-ink-500">
                  {copy.noSources}
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={copyAnswer}
              aria-label={copied ? copy.copied : copy.copy}
              className="inline-flex h-7 items-center gap-1.5 rounded-full px-2 text-[12px] font-semibold text-ink-500 transition hover:bg-cream-100 hover:text-ink-900"
            >
              {copied ? <Check size={11} /> : <Copy size={11} />}
              {copied ? copy.copied : copy.copy}
            </button>
          </div>
          {copyFailed && (
            <p role="status" className="mt-2 text-[12px] text-ink-700">
              {copy.copyFailed}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export function ErrorBubble({
  language,
  onRetry,
  canRetry = true,
  detail,
}: {
  detail?: string;
  language: LanguageCode;
  onRetry: () => void;
  canRetry?: boolean;
}) {
  const copy = COPY[language];
  return (
    <div className="assistant-message" role="alert">
      <AssistantAvatar />
      <div className="rounded-2xl rounded-tl-lg border border-red-200 bg-red-50/85 px-4 py-3.5">
        <div className="flex items-start gap-2.5">
          <AlertCircle
            size={17}
            className="mt-0.5 shrink-0 text-red-700"
            aria-hidden="true"
          />
          <div>
            <p className="text-[12px] font-bold text-red-900">
              {copy.errorTitle}
            </p>
            <p className="mt-0.5 text-[11px] leading-5 text-red-800/80">
              {detail ?? copy.errorBody}
            </p>
            {canRetry && <button
              type="button"
              onClick={onRetry}
              className="mt-2 rounded-full bg-red-900 px-3 py-1 text-[10px] font-bold text-white transition hover:bg-red-800"
            >
              {copy.retry}
            </button>}
          </div>
        </div>
      </div>
    </div>
  );
}

function AssistantAvatar() {
  return (
    <div className="assistant-avatar" aria-label="InsureTutor">
      <BookMarked size={17} aria-hidden="true" />
    </div>
  );
}

function statusFor(kind: AssistantMessage["kind"], language: LanguageCode) {
  const copy = COPY[language];
  if (kind === "insufficient") {
    return {
      label: copy.insufficientNote,
      icon: ShieldAlert,
      tone: "border-amber-600/20 bg-amber-50 text-amber-700",
    };
  }
  if (kind === "blocked" || kind === "scope") {
    return {
      label: copy.scopeNote,
      icon: ShieldAlert,
      tone: "border-ink-900/10 bg-cream-100 text-ink-700",
    };
  }
  if (kind === "advice") {
    return {
      label: copy.educationalBadge,
      icon: Info,
      tone: "border-jade-700/15 bg-jade-50 text-jade-800",
    };
  }
  return null;
}
