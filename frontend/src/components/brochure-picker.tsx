"use client";
import { useEffect, useRef, useState } from "react";
import { Upload } from "lucide-react";
import type { BrochureInfo, LanguageCode } from "@/lib/types";
import { BROCHURE_COPY } from "@/lib/brochure-copy";

export function BrochurePicker({ language, active, disabled, onUploaded }: {
  language: LanguageCode; active: boolean; disabled: boolean;
  onUploaded: (brochure: BrochureInfo) => void;
}) {
  const c = BROCHURE_COPY[language];
  const ref = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const abort = useRef<AbortController | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => () => abort.current?.abort(), []);
  function close() { abort.current?.abort(); ref.current?.close(); }
  async function upload() {
    if (!file || busy) return;
    if (file.size > 8 * 1024 * 1024) { setError(c.tooLarge); return; }
    const controller = new AbortController(); abort.current = controller;
    setBusy(true); setError("");
    const timer = setTimeout(() => controller.abort(), 180000);
    try {
      const response = await fetch("/api/brochures", {
        method: "POST", headers: { "Content-Type": "application/pdf", "X-File-Name": encodeURIComponent(file.name) },
        body: file, signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail.slice(0, 250) : "");
      if (!data || typeof data.id !== "string" || !/^[a-f0-9]{32}$/.test(data.id)
        || typeof data.filename !== "string" || !Number.isInteger(data.pages) || data.pages < 1
        || !Number.isInteger(data.chunks) || data.chunks < 1
        || !["hybrid", "lexical"].includes(data.retrieval_mode) || !Number.isFinite(data.expires_at)) throw new Error("");
      if (controller.signal.aborted) return;
      onUploaded(data as BrochureInfo); ref.current?.close(); setFile(null);
      setTimeout(() => document.getElementById("question")?.focus(), 0);
    } catch (e) {
      if (ref.current?.open) setError(c.error + (e instanceof Error && e.name !== "AbortError" && e.message ? " " + e.message : ""));
    } finally { clearTimeout(timer); abort.current = null; setBusy(false); }
  }
  return <>
    <button className="text-button brochure-upload-button" onClick={() => { setFile(null); if (input.current) input.current.value = ""; setError(""); ref.current?.showModal(); }} disabled={disabled} aria-label={active ? c.replace : c.upload} title={active ? c.replace : c.upload}>
      <Upload size={17} /><span>{active ? c.replace : c.upload}</span>
    </button>
    <dialog ref={ref} className="brochure-dialog" aria-labelledby="brochure-upload-title" onCancel={close} onClick={e => { if (e.target === ref.current) close(); }} onKeyDown={e => {
      if (e.key !== "Tab") return;
      const controls = [...e.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled])')].filter(n => n.getClientRects().length);
      const first = controls[0], last = controls.at(-1);
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
    }}>
      <form onSubmit={e => { e.preventDefault(); void upload(); }} aria-busy={busy}>
        <p className="eyebrow">{c.private}</p><h2 id="brochure-upload-title">{c.title}</h2>
        <p>{c.description}</p><p className="muted">{c.limits}</p>
        <label htmlFor="brochure-file">{c.choose}</label>
        <input ref={input} id="brochure-file" type="file" accept="application/pdf,.pdf" disabled={busy} onChange={e => { setFile(e.target.files?.[0] ?? null); setError(""); }} />
        <p className="muted">{c.privacy}</p>
        {busy && <p role="status">{c.indexing}</p>}
        {error && <p role="alert">{error}</p>}
        <div className="brochure-actions"><button type="button" className="text-button" onClick={close}>{c.cancel}</button><button type="submit" className="new-chat" disabled={!file || busy}>{c.start}</button></div>
      </form>
    </dialog>
  </>;
}
