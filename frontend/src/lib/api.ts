import type { ChatResponse, Citation } from "./types";

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function optionalNumber(value: unknown) {
  return value == null || (typeof value === "number" && Number.isFinite(value));
}

function citation(value: unknown): value is Citation {
  return (
    record(value) &&
    typeof value.id === "string" &&
    typeof value.document === "string" &&
    typeof value.excerpt === "string" &&
    typeof value.page === "number" &&
    Number.isInteger(value.page) &&
    value.page > 0 &&
    (value.section == null || typeof value.section === "string") &&
    optionalNumber(value.score)
  );
}

function response(value: unknown): value is ChatResponse {
  return (
    record(value) &&
    typeof value.message === "string" &&
    value.message.trim().length > 0 &&
    typeof value.language === "string" &&
    ["en", "zh-Hans", "zh-Hant"].includes(value.language) &&
    typeof value.kind === "string" &&
    ["answer", "scope", "insufficient", "blocked", "advice"].includes(
      value.kind,
    ) &&
    typeof value.used_retrieval === "boolean" &&
    Array.isArray(value.citations) &&
    value.citations.every(citation) &&
    Array.isArray(value.notices) &&
    value.notices.every((item) => typeof item === "string") &&
    (value.retrieval_mode == null ||
      typeof value.retrieval_mode === "string") &&
    optionalNumber(value.confidence)
  );
}

export function parseChatResponse(value: unknown): ChatResponse {
  if (!response(value)) throw new Error("Invalid chat response");
  return value;
}

export function chatTimeoutMs(serverTimeout: unknown): number {
  return typeof serverTimeout === "number" &&
    Number.isFinite(serverTimeout) &&
    serverTimeout >= 1 &&
    serverTimeout <= 640
    ? serverTimeout * 1000
    : 195000;
}
