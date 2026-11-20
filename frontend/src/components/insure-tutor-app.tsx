"use client";

import {
  Check,
  FileText,
  PanelRight,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { COPY } from "@/lib/i18n";
import type {
  AssistantMessage,
  ChatResponse,
  ChatTurn,
  Citation,
  LanguageCode,
  Message,
  UserMessage,
} from "@/lib/types";
import { uid } from "@/lib/utils";
import { AppHeader } from "./app-header";
import { AssistantBubble, ErrorBubble, UserBubble } from "./message-bubble";
import { Composer } from "./composer";
import { PlanCard } from "./plan-card";
import { SourcePanel } from "./source-panel";
import { WelcomePanel } from "./welcome-panel";

const STORAGE_KEY = "insuretutor-language";

export function InsureTutorApp() {
  const [language, setLanguage] = useState<LanguageCode>("en");
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [lastQuestion, setLastQuestion] = useState("");
  const [activeCitation, setActiveCitation] = useState<number | null>(null);
  const [activeCitationMessage, setActiveCitationMessage] = useState<string | null>(null);
  const [sourceOpen, setSourceOpen] = useState(false);
  const [mobileSources, setMobileSources] = useState(false);
  const [hasStarted, setHasStarted] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY) as LanguageCode | null;
    if (saved === "en" || saved === "zh-Hans" || saved === "zh-Hant") {
      setLanguage(saved);
      document.documentElement.lang =
        saved === "en" ? "en" : saved === "zh-Hans" ? "zh-CN" : "zh-HK";
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, language);
    document.documentElement.lang =
      language === "en" ? "en" : language === "zh-Hans" ? "zh-CN" : "zh-HK";
  }, [language]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading, error]);

  const copy = COPY[language];
  const activeAssistant = [...messages]
    .reverse()
    .find((message): message is AssistantMessage => message.role === "assistant");
  const currentCitations = activeAssistant?.citations ?? [];
  const selectedAssistant = messages.find(
    (message): message is AssistantMessage =>
      message.role === "assistant" && message.id === activeCitationMessage,
  );
  const selectedCitations = selectedAssistant?.citations ?? currentCitations;
  const sourceCitations =
    activeCitationMessage !== null ? selectedCitations : currentCitations;
  const started = hasStarted || messages.length > 0;

  function historyForRequest(): ChatTurn[] {
    return messages
      .filter(
        (message): message is UserMessage | AssistantMessage =>
          !("pending" in message && message.pending),
      )
      .slice(-12)
      .map((message) => ({
        role: message.role,
        content: message.content,
      }));
  }

  const sendMessage = useCallback(
    async (questionOverride?: string) => {
      const question = (questionOverride ?? draft).trim();
      if (!question || loading) return;
      setDraft("");
      setError(false);
      setHasStarted(true);
      setLastQuestion(question);
      setActiveCitation(null);
      setActiveCitationMessage(null);
      setMessages((current) => [
        ...current,
        { id: uid("u"), role: "user", content: question },
        {
          id: uid("a"),
          role: "assistant",
          content: "",
          citations: [],
          kind: "answer",
          notices: [],
          pending: true,
        },
      ]);
      setLoading(true);
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: question,
            language,
            history: historyForRequest(),
          }),
          signal: controller.signal,
        });
        if (!response.ok) {
          let detail = "";
          try {
            const body = await response.json();
            detail = body.detail ?? "";
          } catch {
            detail = "";
          }
          throw new Error(detail || `Request failed (${response.status})`);
        }
        const result = (await response.json()) as ChatResponse;
        const assistantId = uid("a");
        setMessages((current) => {
          const next = [...current];
          const pendingIndex = next.findIndex(
            (message) => message.role === "assistant" && "pending" in message && message.pending,
          );
          const assistant: AssistantMessage = {
            id: assistantId,
            role: "assistant",
            content: result.message,
            citations: result.citations,
            kind: result.kind,
            notices: result.notices,
            retrievalMode: result.retrieval_mode,
            confidence: result.confidence,
          };
          if (pendingIndex >= 0) next[pendingIndex] = assistant;
          else next.push(assistant);
          return next;
        });
        if (result.citations.length > 0) {
          setActiveCitation(1);
          setActiveCitationMessage(assistantId);
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          setMessages((current) =>
            current.filter(
              (message) => !("pending" in message && message.pending),
            ),
          );
        } else {
          setMessages((current) =>
            current.filter(
              (message) => !("pending" in message && message.pending),
            ),
          );
          setError(true);
        }
      } finally {
        setLoading(false);
        abortRef.current = null;
      }
    },
    [draft, language, loading, messages],
  );

  function handleCitation(index: number, messageId: string) {
    setActiveCitation(index);
    setActiveCitationMessage(messageId);
    if (window.innerWidth < 1024) setMobileSources(true);
    else setSourceOpen(true);
    window.setTimeout(() => {
      document.getElementById(`source-${index}`)?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }, 80);
  }

  function newConversation() {
    abortRef.current?.abort();
    setMessages([]);
    setDraft("");
    setError(false);
    setActiveCitation(null);
    setHasStarted(false);
    setSourceOpen(false);
  }

  const sidebarOpen = sourceOpen;

  return (
    <div className="paper-grain min-h-screen text-ink-900">
      <AppHeader
        language={language}
        onLanguageChange={setLanguage}
        onNewChat={newConversation}
        onOpenSources={() => {
          if (window.innerWidth < 1024) setMobileSources(true);
          else setSourceOpen((current) => !current);
        }}
        conversationsStarted={started}
      />

      <div className="mx-auto flex max-w-[1440px]">
        <main className="flex min-h-[calc(100vh-68px)] min-w-0 flex-1 flex-col">
          <div className="custom-scrollbar flex-1 overflow-y-auto px-4 pb-2 sm:px-6 lg:px-10">
            {messages.length === 0 && !error ? (
              <WelcomePanel language={language} onSelectPrompt={(prompt) => sendMessage(prompt)} />
            ) : (
              <div className="mx-auto w-full max-w-[800px] space-y-6 py-6 sm:py-8">
                <div className="flex items-center justify-between gap-3 border-b border-ink-900/[0.07] pb-4">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white text-jade-700 shadow-sm ring-1 ring-ink-900/[0.06]">
                      <FileText size={14} aria-hidden="true" />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-[12px] font-bold text-ink-900">{copy.productName}</p>
                      <p className="sr-only">{copy.productSubtitle}</p>
                      <p className="truncate text-[10px] text-ink-500">
                        {copy.sourceBody}
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setMobileSources(true)}
                    className="flex shrink-0 items-center gap-1.5 rounded-full border border-ink-900/10 bg-white/70 px-2.5 py-1.5 text-[10px] font-bold text-ink-700 transition hover:bg-white lg:hidden"
                  >
                    <PanelRight size={12} aria-hidden="true" />
                    {copy.mobileSources}
                  </button>
                </div>
                {messages.map((message) =>
                  message.role === "user" ? (
                    <UserBubble key={message.id} message={message} />
                  ) : (
                    <AssistantBubble
                      key={message.id}
                      message={message}
                      language={language}
                      activeCitation={activeCitation}
                      onCitationClick={(index) => handleCitation(index, message.id)}
                      onRetry={() =>
                        sendMessage(message.content || lastQuestion)
                      }
                    />
                  ),
                )}
                {error && (
                  <ErrorBubble language={language} onRetry={() => sendMessage(lastQuestion)} />
                )}
                <div ref={chatEndRef} />
              </div>
            )}
          </div>

          <div className="sticky bottom-0 z-30 bg-gradient-to-t from-cream-50 via-cream-50/95 to-transparent px-4 pb-3 pt-4 sm:px-6 sm:pb-4 lg:px-10">
            <div className="mx-auto w-full max-w-[800px]">
              <Composer
                language={language}
                value={draft}
                onChange={setDraft}
                onSubmit={() => sendMessage()}
                loading={loading}
                onStop={() => abortRef.current?.abort()}
              />
              <div className="mt-2 flex items-start justify-center gap-1.5 px-2 text-center">
                <ShieldCheck
                  size={10}
                  className="mt-[2px] shrink-0 text-jade-700/70"
                  aria-hidden="true"
                />
                <p className="max-w-[650px] text-[9px] leading-4 text-ink-500/80">
                  {copy.disclaimer}
                </p>
              </div>
            </div>
          </div>
        </main>

        {/* Desktop evidence rail */}
        {sidebarOpen && (
          <div className="hidden lg:block">
            <SourcePanel
              language={language}
              citations={sourceCitations}
              activeCitation={activeCitation}
              onSelectCitation={(index) => setActiveCitation(index)}
              open
              onClose={() => setSourceOpen(false)}
              mobile={false}
              messages={messages.filter(
                (message): message is AssistantMessage => message.role === "assistant",
              )}
            />
          </div>
        )}

        {/* Compact plan context lives in the right rail when open; on wide
            screens the rail is explicitly a source drawer, not a dashboard. */}
        {!sidebarOpen && (
          <aside className="hidden w-[250px] shrink-0 border-l border-ink-900/[0.06] px-4 py-5 lg:block xl:w-[270px]">
            <PlanCard language={language} />
            <div className="rounded-2xl bg-jade-900 px-4 py-4 text-cream-50">
              <div className="mb-2 flex items-center gap-2">
                <span className="grid h-7 w-7 place-items-center rounded-full bg-white/10">
                  <Sparkles size={13} aria-hidden="true" />
                </span>
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-cream-50/70">
                  {copy.sources}
                </p>
              </div>
              <p className="text-[12px] font-semibold leading-[1.55]">
                {sourceCitations.length
                  ? `${sourceCitations.length} ${copy.citations}`
                  : copy.structuredNotice}
              </p>
              {sourceCitations.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSourceOpen(true)}
                  className="mt-3 flex items-center gap-1.5 rounded-full bg-cream-50 px-3 py-1.5 text-[10px] font-bold text-jade-900 transition hover:bg-white"
                >
                  <Check size={11} aria-hidden="true" />
                  {copy.viewSource}
                </button>
              )}
            </div>
          </aside>
        )}
      </div>

      <SourcePanel
        language={language}
        citations={sourceCitations}
        activeCitation={activeCitation}
        onSelectCitation={(index) => setActiveCitation(index)}
        open={mobileSources}
        onClose={() => setMobileSources(false)}
        mobile
        messages={messages.filter(
          (message): message is AssistantMessage => message.role === "assistant",
        )}
      />
    </div>
  );
}

