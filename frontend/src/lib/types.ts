export type LanguageCode = "en" | "zh-Hans" | "zh-Hant";

export type ResponseKind =
  | "answer"
  | "scope"
  | "insufficient"
  | "blocked"
  | "advice";

export interface Citation {
  id: string;
  document: string;
  page: number;
  section?: string | null;
  excerpt: string;
  score?: number | null;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  message: string;
  citations: Citation[];
  language: LanguageCode;
  kind: ResponseKind;
  used_retrieval: boolean;
  retrieval_mode?: string | null;
  confidence?: number | null;
  notices: string[];
}

export interface AssistantMessage {
  id: string;
  role: "assistant";
  content: string;
  citations: Citation[];
  kind: ResponseKind;
  notices: string[];
  retrievalMode?: string | null;
  confidence?: number | null;
  pending?: boolean;
}

export interface UserMessage {
  id: string;
  role: "user";
  content: string;
}

export type Message = UserMessage | AssistantMessage;

