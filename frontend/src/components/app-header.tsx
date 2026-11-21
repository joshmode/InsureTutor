"use client";
import { FileText, MessageSquarePlus } from "lucide-react";
import { COPY } from "@/lib/i18n";
import type { LanguageCode } from "@/lib/types";
import { LanguagePicker } from "./language-picker";
import { Logo } from "./logo";

export function AppHeader({
  language,
  onLanguageChange,
  onNewChat,
  onOpenSources,
  conversationsStarted,
}: {
  language: LanguageCode;
  onLanguageChange: (language: LanguageCode) => void;
  onNewChat: () => void;
  onOpenSources: () => void;
  conversationsStarted: boolean;
}) {
  const copy = COPY[language];
  return (
    <header className="app-header">
      <Logo />
      <div className="header-actions">
        <button
          className="text-button header-sources"
          onClick={onOpenSources}
          aria-label={copy.sources}
        >
          <FileText size={17} />
          <span>{copy.sources}</span>
        </button>
        <LanguagePicker value={language} onChange={onLanguageChange} />
        <button
          className="new-chat"
          onClick={onNewChat}
          disabled={!conversationsStarted}
          aria-label={copy.newChat}
          title={copy.newChat}
        >
          <MessageSquarePlus size={17} />
          <span>{copy.newChat}</span>
        </button>
      </div>
    </header>
  );
}
