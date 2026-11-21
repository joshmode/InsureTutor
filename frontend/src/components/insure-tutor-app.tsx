"use client";
import { useEffect, useRef, useState } from "react";
import { BookOpen, Circle, FileText } from "lucide-react";
import { COPY } from "@/lib/i18n";
import type {
  AssistantMessage,
  ChatResponse,
  ChatTurn,
  LanguageCode,
  Message,
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
  const [sourceMessage, setSourceMessage] = useState<string | null>(null);
  const [sourceOpen, setSourceOpen] = useState(false);
  const [health, setHealth] = useState<{ llm_configured: boolean } | null>(
    null,
  );
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const copy = COPY[language];
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "en" || saved === "zh-Hans" || saved === "zh-Hant")
        setLanguage(saved);
    } catch {}
    const controller = new AbortController();
    fetch("/api/health", { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((h) => {
        if (h?.status === "ok") setHealth(h);
      })
      .catch(() => {});
    return () => {
      controller.abort();
      abortRef.current?.abort();
    };
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, language);
    } catch {}
    document.documentElement.lang = language;
  }, [language]);
  useEffect(() => {
    // Scroll only the conversation, never the whole document or the composer.
    const region = scrollRef.current;
    if (region)
      region.scrollTo({
        top: region.scrollHeight,
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
      });
  }, [messages, error]);
  const assistants = messages.filter(
    (m): m is AssistantMessage => m.role === "assistant" && !m.pending,
  );
  const selected =
    assistants.find((m) => m.id === sourceMessage) ?? assistants.at(-1);
  function historyForRequest(): ChatTurn[] {
    // Failed and canceled user turns have no answer and must not poison retries.
    const completed: ChatTurn[] = [];
    for (let i = 0; i < messages.length - 1; i++) {
      const u = messages[i],
        a = messages[i + 1];
      if (u.role === "user" && a.role === "assistant" && !a.pending) {
        completed.push(
          { role: "user", content: u.content.slice(0, 8000) },
          { role: "assistant", content: a.content.slice(0, 8000) },
        );
        i++;
      }
    }
    return completed.slice(-12);
  }
  async function sendMessage(override?: string, retry = false) {
    const question = (override ?? draft).trim();
    if (!question || abortRef.current) return;
    const controller = new AbortController();
    abortRef.current = controller;
    const pendingId = uid("a"),
      userId = uid("u");
    const history = historyForRequest();
    setDraft("");
    setError(false);
    setLastQuestion(question);
    setLoading(true);
    setMessages((current) => [
      ...current,
      ...(retry
        ? []
        : [{ id: userId, role: "user" as const, content: question }]),
      {
        id: pendingId,
        role: "assistant",
        content: "",
        citations: [],
        kind: "answer",
        notices: [],
        pending: true,
      },
    ]);
    const timeout = setTimeout(() => controller.abort("timeout"), 150000);
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: question, language, history }),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result: ChatResponse = await response.json();
      if (abortRef.current !== controller) return;
      setMessages((current) =>
        current.map((m) =>
          m.id === pendingId
            ? {
                id: pendingId,
                role: "assistant",
                content: result.message,
                citations: result.citations,
                kind: result.kind,
                notices: result.notices,
                retrievalMode: result.retrieval_mode,
                confidence: result.confidence,
              }
            : m,
        ),
      );
      setSourceMessage(pendingId);
      setActiveCitation(result.citations.length ? 1 : null);
    } catch {
      if (abortRef.current !== controller) return;
      setMessages((current) => current.filter((m) => m.id !== pendingId));
      if (!controller.signal.aborted || controller.signal.reason === "timeout")
        setError(true);
      else setDraft((current) => current || question);
    } finally {
      clearTimeout(timeout);
      if (abortRef.current === controller) {
        abortRef.current = null;
        setLoading(false);
      }
    }
  }
  function newConversation() {
    const previous = abortRef.current;
    abortRef.current = null;
    previous?.abort();
    setLoading(false);
    setMessages([]);
    setDraft("");
    setError(false);
    setLastQuestion("");
    setSourceMessage(null);
    setActiveCitation(null);
    setSourceOpen(false);
    document.getElementById("question")?.focus();
  }
  function showCitation(index: number, messageId: string) {
    setActiveCitation(index);
    setSourceMessage(messageId);
    setSourceOpen(true);
  }
  return (
    <div className="app-shell">
      <AppHeader
        language={language}
        onLanguageChange={setLanguage}
        onNewChat={newConversation}
        onOpenSources={() => setSourceOpen(true)}
        conversationsStarted={messages.length > 0}
      />
      <div className="workspace">
        <aside className="reference-rail">
          <PlanCard language={language} />
          <p className="rail-disclaimer">{copy.disclaimer}</p>
        </aside>
        <main className="conversation-workspace">
          <div className="workspace-bar">
            <span>
              <BookOpen size={16} />
              {copy.productName}
            </span>
            <button className="text-button" onClick={() => setSourceOpen(true)}>
              <FileText size={15} />
              {copy.mobileSources}
            </button>
          </div>
          <div className="conversation-scroll custom-scrollbar" ref={scrollRef}>
            <div className="reading-column">
              {messages.length === 0 ? (
                <WelcomePanel
                  language={language}
                  onSelectPrompt={(p) => sendMessage(p)}
                />
              ) : (
                <section
                  className="conversation"
                  role="log"
                  aria-live="polite"
                  aria-relevant="additions text"
                  aria-label={copy.welcomeKicker}
                  aria-busy={loading}
                >
                  {messages.map((m) =>
                    m.role === "user" ? (
                      <UserBubble key={m.id} message={m} />
                    ) : (
                      <AssistantBubble
                        key={m.id}
                        message={m}
                        language={language}
                        activeCitation={
                          m.id === sourceMessage ? activeCitation : null
                        }
                        onCitationClick={(i) => showCitation(i, m.id)}
                      />
                    ),
                  )}
                  {error && (
                    <ErrorBubble
                      language={language}
                      onRetry={() => sendMessage(lastQuestion, true)}
                    />
                  )}
                  <div ref={endRef} />
                </section>
              )}
            </div>
          </div>
          <div className="composer-dock">
            <div className="reading-column">
              {health && (
                <p className="connection-status">
                  <Circle size={7} fill="currentColor" aria-hidden="true" />
                  {health.llm_configured
                    ? copy.connectedMode
                    : copy.excerptMode}
                </p>
              )}
              <Composer
                language={language}
                value={draft}
                onChange={setDraft}
                onSubmit={() => sendMessage()}
                loading={loading}
                onStop={() => abortRef.current?.abort()}
              />
              <p className="composer-disclaimer">{copy.disclaimer}</p>
            </div>
          </div>
        </main>
        <SourcePanel
          language={language}
          citations={selected?.citations ?? []}
          activeCitation={activeCitation}
          onSelectCitation={setActiveCitation}
          open={sourceOpen}
          onClose={() => setSourceOpen(false)}
        />
      </div>
    </div>
  );
}
