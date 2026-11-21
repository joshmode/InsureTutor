# Private brochures and beginner explanations — 22 November 2026

The user selected **private to the current conversation**, rather than replacing
the reference for everyone. This follows [the English-refusal fixes](ENGLISH-REFUSALS.md).
Upstream changes `0fdfbd0` and `978ea61` were incorporated before this work; their
currency normalization and 8,000-token default were preserved.

## Implemented behavior

- Upload a text PDF through the localized header dialog. The new brochure's
  text index and embedding vectors are built before switching the conversation.
  Upload failure leaves the previous chat and document intact. Success clears
  old history/evidence and shows the active filename, page count and PDF links.
- Contexts are isolated by a random document ID **and** an HttpOnly SameSite
  owner cookie. Knowing another ID is insufficient. Chat, chunks, PDF access and
  deletion enforce ownership. Invalid contexts never silently use the default
  PDF. Unknown chat fields are rejected to catch document-selector typos.
- The default brochure is unchanged. New conversation resets to it and requests
  upload deletion. Browser refresh resets UI state; files remain bounded by the
  expiry policy. Expired contexts show upload/reset guidance rather than a futile
  Retry button.
- Each document gets separate chunks and vectors. One verified embedding model
  is shared across contexts. Reloading a persisted context rebuilds its vectors
  from its own chunks; replacing a brochure does not reuse another PDF's index.
- PDF processing is limited to 8 MiB, 100 pages, 1,000 chunks and 2,097,152
  content characters. A child parser has 15 CPU seconds, 25 seconds wall time,
  768 MiB address space and an 8 MiB output-file limit. Parsers are serialized
  across workers to bound simultaneous native-parser memory. The child receives
  no provider keys or proxy credentials. Encrypted, malformed and scan-only PDFs
  fail with recovery guidance; OCR is not implemented.
- Uploads share existing admission, concurrency and request-deadline controls.
  The default maximum is 16 active documents. Files expire within 24 hours and
  are pruned every minute while running and on startup. New corpus metadata is
  published atomically. A canceled upload cleans up its eventual result.
- System prompts, branding and starter questions follow the active brochure.
  The original brochure's rate/rider checks apply only to its reviewed file
  fingerprint. Other products use their actual source evidence and separate
  claim review; legitimate guarantees in another product are not classified
  using FLEXI's rates. Small-corpus retrieval accounts for IDF score bounds.

## Beginner-answer failure

The reported fallback did **not** establish missing embeddings: native health
reported hybrid retrieval with 52 chunks. The running process was also older
than the latest upstream fixes. The exact question was reproduced in several
bounded attempts, with materially different outcomes.

The initial retrieval emphasized investment strategy, company ownership and
age/term fields. The new overview path balances product introduction, policy
value, costs and risk. A short, four-sentence introduction avoids unnecessary
rates and payout formulas. One actual attempt failed during repair/review after
the 60-second provider timeout; the response now identifies a timeout, output
limit or authentication failure rather than always claiming the model is
unavailable. The per-call default is 90 seconds, retaining the overall
180-second chat deadline and the existing daily allowance.

Earlier generated answers also contained an incorrect non-linked-investment
explanation, a broad death-benefit formula and a withdrawal-fee omission. These
are **failed semantic examples**, even where the model reviewer approved them.
Added regressions reject the observed investment and payout misstatements;
writing instructions preserve fee exceptions. This is not general entailment
proof or injection immunity.

The final exact-question run returned a generated, four-sentence cited answer
in **80.60 seconds**. The [recorded result](private-brochures/beginner-final.json)
is a bounded example, not an accuracy or availability guarantee. Provider
latency and false abstentions remain possible.

## Verification

- [Full local suite](private-brochures/backend-tests.txt): **312 passed**, with one
  existing Starlette/httpx deprecation warning. Two additional lifecycle cases
  were then added; the complete [17-case private-document suite](private-brochures/lifecycle-tests.txt)
  passes, including cancellation cleanup and parser serialization across stores.
- [Chromium](private-brochures/upload-chromium.json),
  [Firefox](private-brochures/upload-firefox.json) and
  [WebKit](private-brochures/upload-webkit.json): five private-document groups
  each pass. The committed `scripts/private-brochures-ui.cjs` runs these in CI,
  plus a run requiring the real pinned embedding model. It does not require or
  claim funded model generation unless `REQUIRE_MODEL=1` is explicitly set.
- Existing [13 browser groups](private-brochures/browser-regressions.json) and
  [7 interaction groups](private-brochures/ui-regressions.json) pass. The
  [upload dialog axe check](private-brochures/dialog-accessibility.json) reports
  zero detected A/AA violations; manual layout/focus checks supplement it.

- Full backend suite and targeted document-boundary tests are recorded alongside
  the evidence. Coverage includes two owners, two distinct PDFs, index reload,
  private PDF/chunk access, deletion, expiry, capacity, encrypted/scanned/invalid/
  oversized documents, parser timeout and an incorrect context-field name.
- [Live UI run](private-brochures/browser-live.json): two **fictitious verification
  brochures**, Cedar and Maple, produced genuinely generated answers with their
  respective US$12 and US$34 administrative charges and correct citations. These
  fixtures test isolation/re-indexing; they are not real policy terms.
- Replacement clears old messages and source selection. An invalid replacement
  preserves the active document. Another browser owner receives 404. New
  conversation removes the active private document and resets the default.
- [Narrow-screen and recovery checks](private-brochures/browser-recovery.json)
  cover 320 px overflow, private source URLs, expired-document guidance, reset
  and keyboard focus in the Traditional Chinese upload dialog. An initial focus
  test failed and led to an explicit focus trap; reopening also resets the file
  control so the same filename can be uploaded again.
- TypeScript and static production build pass. Existing browser checks use a
  **model-free** server; funded-provider runs above are separate evidence.
  Browser selectors were updated for multiple dialogs, retaining the assertions
  that all dialogs initially close and source focus stays inside its dialog.
- [Hardened offline container](private-brochures/container.json): real bundled
  embeddings, fresh data volume, read-only root, non-root user, dropped
  capabilities, no-new-privileges, PID/memory/CPU bounds and `--network none`.
  Both PDFs upload and index locally, return their own exact source fee, serve
  matching PDF bytes, and reject a different owner. Its answers are explicitly
  model-free; offline indexing is not proof of hosted model quality.

Initial browser-harness attempts during static rebuilds, ambiguous single-dialog
selectors, Chromium inspector response-body eviction and a live-provider wait
longer than the harness's 30-second timeout were not counted as passes. The
upload-flow test captures a clone of the actual fetch response without changing
its data. Existing interaction tests run in their intended model-free mode.

## Deployment and limits

Pull changes and rebuild/restart the backend; refreshing a browser alone does
not load new Python code. Existing `.env` overrides remain effective. The tested
reasoning profile uses 8,000 output tokens, a 90-second per-call timeout and
`low` reasoning effort. Clear unsupported reasoning settings for other models.

Private documents require the owner cookie and a shared persistent data directory
across workers; their embedding model is shared only within each process. Use
HTTPS for remote access. This is temporary browser-owned storage, not an account
system or a multi-node document service. Restarts rehydrate authorized contexts;
scans still need external OCR. The previous OS advisories, insurer source conflict,
provider data-handling questions, production load and actual assistive-device
verification remain open; this work does not rescan or certify those areas.

The native upload worker uses POSIX process/file limits; Docker/Linux is the
supported deployment path. Resource limits are not a separate OS account or a
hermetic filesystem/network sandbox. Public multi-tenant deployment needs
dedicated parser isolation and large-document/concurrent-indexing load testing.
Upload validation establishes readability and bounds, not insurer authenticity
or the real-world truth of a brochure's claims. Local Firefox/WebKit runs used
the existing workspace browser-library/cache setup; CI installs system browser
dependencies normally. None of these qualifications disable application tests.
