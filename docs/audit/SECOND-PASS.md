# Independent second-pass review — 21 November 2026

Baseline: `57ae016`. The baseline suite passed 153 tests; that did not establish
correctness. This pass reread both PDFs, reviewed the application boundaries and
used new source, abuse, transport and browser probes. The attached agent history
was background material, not instructions or evidence that the code worked.
Earlier audit reports remain historical records rather than being overwritten.

## Assignment and source contract

The two-page assignment requires conversational chat, document-grounded RAG with
citations, guardrails, English/Chinese support, a configurable OpenAI-compatible
provider without an embeddings-API dependency, Docker/Compose, safe key
configuration, incremental commits and explanatory documentation/examples.

| Requirement | Evidence and boundary |
| --- | --- |
| Coherent conversational chat | Completed turns supply bounded history; canceled/failed turns are excluded. Real API chat and controlled retry/Stop/New conversation regressions run in Chromium. |
| RAG and accurate attribution | Actual 20-page brochure, page-aware excerpts and source fingerprints; deterministic citation/number/quote checks and fail-closed claim review for generated drafts. Source retrieval is verified; live generated-answer accuracy is not. |
| Safe scope | Unsupported-topic, injection, misleading-guarantee, personal-determination and citation probes, plus scripted-provider rejection regressions. One new unsupported question still retrieves adjacent excerpts; see below. |
| English and Chinese | All three UI locales and localized starters; new Simplified/Traditional claims and cooling-off controls. Actual model fluency remains unverified. |
| Configurable model; no embeddings endpoint required | OpenAI-compatible endpoint/model settings and local optional embeddings with lexical fallback; provider payload/error/timeout tests. No external provider credentials were available. |
| Dockerfile and Compose | Tracked Dockerfile built directly with the documented CA secret, then ran under the tracked Compose restrictions. Browser checks target the container. |
| Keys, documentation and history | `.env` excluded from Git/build context; placeholders in `.env.example`; README architecture/run/examples and limitations reviewed. This pass uses separate meaningful commits. Public repository accessibility and invitation-email submission were not verified or performed. |

The assignment PDF SHA-256 is
`f79d91ea7fa8220b71c12468b53b9108fdac9aaf498b7e13ff1bab947f3feca3`.
Both brochure copies have SHA-256
`2043de40845267fdb1f657280438f3ded04edda6692791960415116a5668a475`.
The source's bilingual discrepancy on PDF page 17 still requires insurer
clarification; software must disclose it, not choose a preferred version.

## New defects fixed

Severity reflects this demo's anonymous, potentially funded-provider context.
These are implemented changes, with regressions, not proposed work.

| Severity | Reproduced issue | Change and verification |
| --- | --- | --- |
| High | A client disconnect after sending its body left application/provider work running and retained the slot. | One ASGI disconnect monitor cancels and awaits application/provider cleanup before releasing admission. An unfinished HTTPX stream regression and a separate real-TCP Uvicorn/loopback-provider smoke verify connection closure and slot reuse. This cannot guarantee a vendor stops billing after socket closure. |
| Medium | Cancellation during threaded SQLite admission could orphan a committed concurrency lease until expiry. | Shield admission, retain its eventual result and clean up that lease even after request cancellation. Regression occupies the sole slot and proves immediate reuse. |
| Medium | An underspecified follow-up could lose the page-17 source-conflict warning. | Conflict detection uses resolved user context, with a no-provider follow-up regression. |
| Medium | Broad high-risk matching rejected ordinary payer questions and Chinese claims-procedure education. | Separate insurer promises from policyholder fee questions and narrow Chinese adjudication grammar. Positive controls retain citations; personal-claim determinations remain refused. |
| Medium | Maximum-sum-insured extraction discarded the short Chinese value and stripped “Individual consideration.” | Preserve the actual adjacent bilingual row only for the fingerprinted brochure. Both languages and the English value survive extraction and answers. Schema 5 invalidates old caches; corpus remains 52 chunks. |
| Medium | PDF metadata could name a different document; the source endpoint always served the first configured PDF. | Citations use the real filename. Exact configured document selection is supported in the endpoint and UI links; unknown names, traversal, missing files and escaping symlinks return 404. Regression uses two distinct real PDFs. |
| Medium | A malformed successful API response could crash React and remove the composer. | Validate the runtime response shape before state mutation. Five malformed-response browser variants now reach recoverable errors with the composer intact. |
| Medium | Client timeout was fixed at 150 seconds despite a longer configurable server deadline. | Health advertises the complete read/chat deadline plus margin; the client uses its bounded value. Backend custom-deadline regression and browser timer inspection cover 285 seconds. |
| Medium | Retry erased a different unsent draft; Stop/resend duplicated the user question. | Preserve drafts for override requests; remove the canceled submitted turn while retaining newer draft text. Browser reproductions cover both. |
| Medium | A background response replaced the source evidence explicitly opened for an earlier answer. | Explicit citation selection stays pinned; generic Sources selects the latest completed answer. Controlled A/B response regression verifies both. |
| Low | Common abbreviations such as `Ltd.` and `p.a.` were mistaken for uncited sentence endings. | Bounded abbreviation handling retains sentence-level checks; a subsequent uncited sentence still fails. |
| Low | Simplified `静`/`偿` questions lost relevant retrieval; Chinese citation accessible names stayed English. | Reviewed retrieval-only character normalization and localized citation labels; real-PDF claims/cooling-off regressions and both Chinese browser locales. Quotations remain unchanged. |
| Low | Clipboard denial was silent; welcome could scroll to the bottom; clearing a preserved draft could be disabled after Stop. | Accessible localized manual-copy feedback, empty-chat scroll reset, and New conversation enabled for drafts. Browser checks and the broader interaction suite verify these states. |
| Low | Locale persistence depended on a passive effect that could run after reload. | Persist synchronously in the selection event and avoid overwriting saved preferences during initialization. The browser checks immediate storage and waits for post-reload hydration before asserting the restored locale. |

Code review also checked source/static path confinement, optional Basic access,
actual-byte request limits, persistent allowances, provider payload bounds,
SQLite contention, local-model integrity, CSP/Markdown restrictions, Docker
privileges, dependency locks and asynchronous retrieval. No additional bypass
was reproduced there; this is not a claim of exhaustive security certification.

## Adversarial results and remaining semantic risks

[Fresh probes](second-pass/fresh-rag-probes.json) contain full responses for 20
new questions and six citation attacks, using the actual PDF corpus and no
configured model:

- Six supported controls returned citations: both Chinese scripts for claims
  and cooling-off, a policyholder withdrawal-charge question, and maximum sum
  insured. Source pages were inspected independently.
- Six injection variants and the requested fake page 999 produced refusals or
  blocks. This does not establish protection against every natural-language
  injection when a live model is used.
- Six of seven unsupported questions abstained, including cyber ransom,
  veterinary treatment, charity beneficiaries, deposit protection and Chinese
  property/pet questions.
- **Open:** “What is the reinstatement interest charge?” returns adjacent real
  fee/interest/lapse excerpts. It invents no reinstatement fee, and explicitly
  identifies excerpt mode, but these passages do not answer the question.
  Lexical overlap is still an imperfect applicability test. No prompt-specific
  blacklist or claim of complete unsupported-question detection was added.
- Invalid source IDs, mixed bogus markers, changed currency, an uncited claim
  and a forged quotation were rejected. **A same-source fee-label swap to
  US$4 passes the deterministic numeric gate** because that value occurs in the
  source. Generated answers therefore still require semantic review. That
  separate call uses the same configured model/provider, so correlated errors
  remain possible; deterministic checks are not entailment proof.

The existing HTTP adversarial matrix also reports **20/20 mechanical checks**;
the separate held-out matrix reports **10/10 mechanical checks**. Neither earns
a semantic factuality pass. The new source-conflict, abbreviation, Chinese and
extraction defects have permanent backend regressions beyond these matrices.

## Verification evidence

- [Backend suite](second-pass/backend-tests.txt): **183 passed**, one existing
  Starlette/httpx TestClient deprecation warning. No test was removed or skipped
  to obtain this result.
- [Frontend production build](second-pass/frontend-build.txt): TypeScript and
  static export completed. Browser checks use that production export.
- [Original browser suite](second-pass/container-browser/browser-risk-results.json)
  (**13 groups passed**) and
  [new regressions](second-pass/container-ui/ui-regressions.json)
  (**7 groups passed**) distinguish
  real API calls from controlled response/clipboard/deadline fixtures. Screenshots
  cover desktop, mobile, a real source answer and the source dialog. Automated
  axe results concern the checked states, not an accessibility certification.
- [Transport smoke](second-pass/tcp-disconnect.json): real local TCP and provider
  stub, not an external model or a billing guarantee.
- [Docker verification](second-pass/docker-results.json) records the exact
  image, runtime restrictions, persistent schema, HTTP/PDF checks and restart.
- [Image scan](second-pass/image-vulnerabilities.json) and
  [summary](second-pass/image-summary.json) record all severities using the
  previously fetched Trivy advisory database. OS packages were not changed by
  this pass. The previously documented **47 HIGH, 109 MEDIUM, 67 LOW and 9 UNKNOWN
  package/advisory entries remain open**, with no published fixed version in
  that database; zero CRITICAL and zero Python-package findings were reported.
  See the earlier [advisory triage](os-risk-triage.md) for scope and reachability.

## Explicitly unverified / external follow-through

Live draft/repair/reviewer behavior, semantic correctness and Chinese fluency
cannot be verified without a configured provider. The
[explicit live evaluator](second-pass/live-provider-status.json) exits 2 with
`status: blocked` because no model is configured, rather than substituting stub
accuracy. Actual embedding-model
download, hybrid relevance/latency, Firefox/WebKit and hosted GitHub Actions
remain unverified under the recorded HTTP403 network restrictions. Local CI
configuration includes both browser suites for all three engines; supplying it
does not establish a hosted run.

Screen-reader announcements, physical keyboards/devices, production load,
distributed-replica limiting, provider retention/jurisdiction and vendor billing
after cancellation remain outside the measured local checks. The single-volume
SQLite allowances and resource limits are demo controls, not a distributed
abuse defense. Source ambiguity and vendor-unfixed image advisories cannot be
closed by inventing source facts or suppressing findings. All remain visible.

Reproduce with `pytest -q`, `npm run typecheck`, `npm run build`, and the two
browser commands in the README. `scripts/audit_rag.py` and
`scripts/evaluate_provider.py` accept `--base-url`; the latter's
`--require-model` prevents an offline run from masquerading as live evaluation.
