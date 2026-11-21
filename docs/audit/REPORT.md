# InsureTutor submission audit — 21 November 2026

## Verdict

The submission is a functional **single-brochure demo**, with significant correctness and security defects repaired in this review. It is not established as a reliable insurance adviser or a hallucination-proof RAG system. Passing tests and resolving citations do not prove that a generated claim follows from its cited passage.

The original 61 tests passed before these changes. The expanded backend suite passes **95 tests**. The audit found real defects despite that green baseline. The UI was rendered before and after, substantially redesigned, and exercised in Chromium. No real model provider or downloaded multilingual embedding model was available; model quality, translation quality and hybrid retrieval quality remain unverified.

## Authority and scope

Read both pages of `TakeHomeTask-InsureTutor.pdf` and all 20 pages of `FLEXI-ULife Prime Saver.pdf`. The root brochure and `knowledge/` copy have identical SHA-256 `2043de40845267fdb1f657280438f3ded04edda6692791960415116a5668a475`. Visually inspected the high-risk rate and minimum-coverage tables in addition to extracting source text. Page numbers below are **PDF pages**, which differ from the brochure's printed page numbers.

The uploaded prior agent transcript was context, not a new instruction source or evidence of correctness. Repository implementation, tests, API behavior and the actual documents were checked independently. No email, publication or repository push was performed during the audit itself. Existing incremental commit history was inspected; the audit changes were prepared in the existing checkout.

### Assignment coverage

| Requirement | Evidence | Assessment |
| --- | --- | --- |
| Chat within a conversation | Real `/api/chat` requests; UI history, error/retry/cancel checks; bounded history tests | Implemented; semantic follow-up quality with a real model unverified |
| Document-grounded RAG with citations | 49 page-aware chunks; all chunks checked against claimed pages; live citation endpoint round trips; mapping regressions | Implemented, but citation presence is weaker than claim support |
| Safe, accurate, in-scope controls | Input policy, retrieval gates, output validation and repair tests; 20 adversarial cases | Layered heuristics, not a guarantee against misuse |
| English and Chinese, bonus Simplified/Traditional | Localized UI, persisted language selection, bilingual source retrieval, Chinese adversarial inputs | UI/offline paths checked; generated-language fluency unverified |
| Configurable OpenAI-compatible provider without provider embeddings | Transport tests verify configurable `/chat/completions` URL, model and request; local BM25 fallback | Contract tested using mocked transport, not a real provider |
| `.env`, placeholder example, no committed API keys | `.env.example`, Git ignore rules, no provider key configured; Docker ignore improved | Supported; no claim of a full historical secret scan |
| Dockerfile and Compose run | Built image, started non-root user, health/API/UI/PDF checks, Compose configuration/startup | Verified with the cloud's CA mounted during the build; ordinary cloud build needs that trust adjustment |
| README architecture, decisions, examples | Existing documentation inspected and updated with audit links/caveats | Present; examples are illustrative, not live-provider benchmark results |
| Incremental meaningful commits/public repository | Existing incremental history inspected | Public access and submission-email delivery not verified |

## Confirmed defects fixed

| Severity | Defect and reproduction | Fix / verification |
| --- | --- | --- |
| High | Static export route accepted encoded `../` paths; `../../backend/requirements.txt` could escape the export directory. This could expose runtime files reachable by the application user. | Resolve the path and require containment; encoded traversal and symlink escape regression tests; live container returns 404. Unknown API paths also return proper 404. |
| High | `[S1] … [S2] … [S1]` mapped to `[1] … [2] … [2]`, attributing the last claim to the wrong source. | Map by the source's existing display position; regression tests for reordered/repeated IDs and invalid markers. |
| High | Numeric validation accepted `5%` from evidence containing `2.5%`, and `US$400` from `US$400,000`. `4%` bypassed evidence validation entirely. | Compare complete normalized percentage/currency amounts; reject unsupported values. This still does not establish that an amount belongs to the claimed benefit. |
| High | Output checks accepted direct purchase recommendations and some automatically included supplementary-benefit claims; nearby negation could obscure a contradictory guaranteed-rate claim. | Added targeted recommendation, optional-rider and false annual-guarantee checks, plus repair/refusal regressions. These are bounded pattern checks. |
| High | Container built successfully but exited: copied backend files retained owner-only permissions and were unreadable by the non-root `app` user. | Explicit read/traverse permissions on shipped code, brochure and export; data directory owned by `app`. Confirmed actual container runs as UID/GID 999 and becomes healthy. |
| Medium | System prompt requested display `[1]` citations while parser expected evidence `[S1]`. It also conflated 0.25% retrospective interest with Extra Bonus. | Consistent `[S#]` instructions; correct rate terminology; configurable history bound wired through prompts. |
| Medium | Provider error bodies could enter exception/log text. | Retain status/error category without logging remote response bodies; controlled transport/error tests. |
| Medium | `EMBEDDING_ENABLED` was documented but ignored; a query-time vector failure could break chat rather than fall back. | Respect both embedding switches; tested lexical fallback on runtime vector failure with fake backends. Actual ONNX model quality remains untested. |
| Medium | Chinese regex alternatives could block ordinary questions merely containing 假裝 or 關閉. Some made-up-benefit/advice variants were missed. | Grouped alternatives and narrow intent regressions, including Simplified/Traditional inputs. Novel paraphrases can still evade regex policy. |
| Medium | Mobile composer overlaid the page; hidden source controls remained reachable; drawer focus/Escape were incomplete. | Fixed-height workspace with an independently scrolling conversation and separate composer; native modal source dialog, focus return, keyboard wrap and Escape. Tested at 320–1440 CSS pixels. |
| Medium | New conversation could race an old request; retry duplicated the question; stopping an answer could overwrite a newer draft. | Controller identity guard, completed-pair history, retry in place, preserve newer draft on Stop and prevent a Stop click from becoming a form submission; delayed-response browser regressions. |
| Medium | Citation rendering only transformed direct paragraph/list strings, missing nested emphasis/table text. | Markdown text-node transform with stable component identities, preserving focus across selection. Nested emphasis/table citation checks. Model-supplied remote images are suppressed and arbitrary model links are rendered as text. |
| Low | Only the first notice was shown; user-facing offline notices exposed raw configuration names and English-only helper text. Timestamps changed whenever messages rerendered. | Show all notices; localized ordinary-language fallback and composer hints; removed fabricated render-time timestamps. Native language selector replaces incomplete custom listbox. Added polite conversation log semantics. |
| Low | `.env` was excluded by Git but not the Docker build context. | Exclude environment files from build context; retain `.env.example`. |

The suspected synthesized Extra Bonus excerpt was investigated: an inactive helper exists, but **none of the supplied 49 chunks used its generated sentence**. It is not reported as an observed fabricated quote. Before expanding to other brochures, that helper and corpus-specific reconstruction rules deserve review.

## Source findings that matter

- **PDF p8/p16:** the 4%/4.0% base rate is assumed, not guaranteed; 0.25% is retrospective additional interest, not the Extra Bonus. The quoted rates reference January 2022 in the source and must not be presented as a fresh market quote.
- **PDF p8/p16:** 2.5% is an accumulated Account Value guarantee for a policy in force at least 15 years, including credited interest/Extra Bonus. It is not a guaranteed annual cash payout or a simple return on every premium paid.
- **PDF p9/p16:** Extra Bonus examples use 2.75% and 5.5%, with timing/assumptions. These are distinct from retrospective interest.
- **PDF p10/p12/p18:** withdrawals can reduce Cash Value and cause lapse; automatic periodic withdrawals require at least ten policy years and have minimum amounts/durations. The ordinary withdrawal charge and the periodic-option waiver must not be conflated.
- **PDF p11/p12/p14:** critical illness is an optional supplementary benefit; terminal illness is a different benefit, with definition, exclusions and termination consequences. Naming a rider does not supply its waiting period or full claims conditions.
- **PDF p17:** the increase/decrease minimum row conflicts: Chinese has HK$40,000 / MOP400,000, while English has HK$400,000 / MOP40,000 (US$5,000 agrees). Visually confirmed in the PDF. The prompt now requires explicit disclosure of source conflicts and insurer confirmation; this is not a deterministic conflict resolver.
- **PDF p19:** the brochure expressly is not the policy and does not contain all terms/exclusions. The tutor cannot adjudicate a person's coverage or claim from this material.

Provenance testing checks every excerpt line on its claimed page after control-character/whitespace normalization. Two formula diagrams require layout-normalized extraction because PDF text order differs from visual order. This verifies source presence, not the association of every table cell or the entailment of an answer.

## Adversarial results and their limits

`scripts/audit_rag.py` runs 20 questions against an offline runtime or a running HTTP server. Saved results include the complete returned messages. Coverage includes false guarantees, annualized 2.5%, free withdrawals, early surrender, suicide exclusion, fabricated benefits, administrator/system-prompt injection, exact personalized calculations, advice, Chinese and mixed insurance terminology, unsupported property coverage, critical illness waiting periods, cooking, cooling-off and insurer insolvency.

There are **8 explicit expected response-class assertions**; the rest are exploratory probes. All 20 cases had valid marker ranges and resolving source ID/page/excerpt round trips; no mechanical failures occurred. That is **not 20 factuality passes**. Both offline-runtime and actual container HTTP results are saved, with `semantic_claim_support_verified: false` deliberately retained.

A known residual false positive is “Does this policy cover earthquake damage to my house?” It retrieves life-policy excerpts. Offline mode makes its excerpt limitation explicit; a real generator must refuse unsupported coverage rather than infer from incidental overlap. I did not add a question-specific earthquake blacklist and pretend the general retrieval problem was solved.

Provider request-shape/error tests use `httpx.MockTransport`. Orchestrator tests use controlled fake model answers to exercise unsafe output, citation repair and provider failures. These establish implementation behavior for those fixtures, not the behavior of the evaluator's chosen model.

## UI overhaul and rendered verification

The new direction is a restrained document-reading workspace: muted paper canvas, dark ink, one green action color, larger type and flatter question rows. A persistent desktop document reference replaces tiny unreferenced plan-fact cards. The mobile layout dedicates space to the composer instead of overlaying it. Source inspection uses a modal with readable full excerpts and PDF-page links. Offline status is visible rather than implying a model is connected. UI facts no longer label the entire brochure as a January 2022 edition: the source has later publication material as well as 2022 rate assumptions.

Screenshots: [before desktop](before-desktop.png), [before mobile](before-mobile.png), [after desktop](after-desktop.png), [after mobile](after-mobile.png), [conversation](after-chat.png), [source inspection](after-sources.png), [mobile sources](after-mobile-sources.png).

`scripts/browser-audit.cjs` exercises the built client using system Chromium/Playwright. It checks real API retrieval and citations, source/PDF links, Escape/focus return, keyboard containment, all three language selections across reload, nested Markdown citations, all notices, clipboard copy, error/retry without duplicate user messages, preserving a newer draft on Stop, and stale-request cancellation after New conversation. Mocked responses are used only for controlled UI states. Reflow checks use 320, 390, 768, 1024 and 1440px widths, a 720px effective viewport corresponding to 1440px at 200%, and a short 390×420 viewport. The effective-viewport check is not a full browser zoom or real mobile-keyboard test.

All **12 browser check groups passed against the final Compose image**. Axe WCAG A/AA scans of the home screen and open source dialog found zero violations. This is not a screen-reader certification. The polite conversation log is implemented; actual assistive-technology announcements, real iOS/Android keyboards, Safari and Firefox were not tested.

## Remaining engineering risks

1. **Semantic grounding remains the main risk.** Numeric membership, a matching source ID and one citation somewhere in an answer cannot prove each sentence is supported or cited correctly. Same-number/different-benefit errors and unsupported nonnumeric claims can pass. A real-provider claim-level evaluation with held-out questions is needed before claiming accuracy.
2. **Regex policy is necessarily incomplete.** New injections, obfuscation, unsupported languages and benign phrases can cause false negatives/positives. The prompt is a defense layer, not an isolation boundary.
3. **Public cost/availability abuse is unaddressed.** Chat is intentionally unauthenticated, with no rate/concurrency/quota controls. Per-field request bounds do not replace a transport body limit or deployment gateway. Do not expose a funded provider key behind an unrestricted public endpoint without those controls.
4. **Synchronous retrieval runs in the async request path.** Fine for the measured 49-chunk lexical demo; real query embedding, concurrent generation and event-loop responsiveness need profiling before scale claims. No load test was run.
5. **Corpus-specific processing is fragile.** Heading/formula reconstruction and handcrafted synonym/intent gates are tuned to this brochure. Adding a document requires evaluation, not merely appending its filename. PDF page numbers differ from printed numbers.
6. **Hybrid mode is not proven here.** Dependency installation and simulated fallback work; no model download, actual vector relevance or hybrid latency was verified.
7. **Deployment hygiene is incomplete.** Python direct versions are pinned but transitive dependencies are not fully locked; Docker base tags are mutable. npm audit reports zero known advisories at audit time, not immunity to supply-chain risk. No exhaustive Python/CVE/image vulnerability scan was run.
8. **No persistent conversation or authentication.** Reload starts fresh and history travels in the request. Appropriate for this demo, not a member service. Model-provider data handling/retention was not evaluated.

## Verification and reproduction

From repository root:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/audit_rag.py
.venv/bin/python scripts/audit_rag.py --base-url http://127.0.0.1:8013 --output docs/audit/adversarial-http-results.json
cd frontend
npm run typecheck
NEXT_TELEMETRY_DISABLED=1 npm run build
npm audit --cache /workspace/.npm-cache
```

Browser checks require Playwright available to Node and Chromium (`CHROMIUM_PATH` can select it). Optional axe scanning requires `AXE_PATH` pointing to `axe-core/axe.min.js`. These audit tools were available/installed outside the project dependency graph; no app dependency was added for the review.

```bash
BASE_URL=http://127.0.0.1:8013 \
AXE_PATH=/tmp/insuretutor-audit-tools/node_modules/axe-core/axe.min.js \
node scripts/browser-audit.cjs
```

Docker: the ordinary build first failed TLS verification at PyPI because this managed environment intercepts HTTPS. Verification was never disabled. A temporary copy of the Dockerfile mounted `/etc/ssl/certs/ca-certificates.crt` as a BuildKit secret for npm (`NODE_EXTRA_CA_CERTS`) and pip (`PIP_CERT`). No CA or credentials were copied into image layers. The product Dockerfile itself contains the permission fix and keeps normal trust behavior. The resulting image was started and checked; Compose used that prebuilt image with `--no-build`, a fresh named data volume, and a nondefault host port. An unmodified build on an ordinary external network was not tested.

Evidence artifacts: [backend suite](backend-test-results.txt), [offline adversarial](adversarial-results.json), [HTTP adversarial](adversarial-http-results.json), [browser assertions](browser-results.json), [axe home](axe-home.json), [axe sources](axe-sources.json). Build/type-check and dependency audit commands completed successfully; npm reported zero known vulnerabilities. One pre-existing Starlette/httpx deprecation warning remains.

## Interview questions I would ask

- How would you detect a perfectly valid citation attached to the wrong benefit, without tuning another regex to the test question?
- Why does an unrelated property-coverage question get a high retrieval score, and what is that score actually calibrated against?
- What exactly is guaranteed by the 2.5% wording, and how do charges, credited bonuses and the fifteen-year condition affect your explanation?
- How do you preserve conflicting source facts, such as the page-17 bilingual amounts, rather than choosing an apparent typo?
- What fails when the provider is slow, returns malformed content or follows an injection? Which of those paths did you test with the actual provider?
- How would you protect provider spend and users' conversation data if this demo became publicly accessible?

### Exact cloud build trust adjustment

The temporary Dockerfile used for the verified build was generated from the final tracked Dockerfile with these replacements (working directory: repository root):

```python
from pathlib import Path
text = Path("Dockerfile").read_text()
text = text.replace("RUN npm ci", "RUN --mount=type=secret,id=proxy_ca,required=true NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca npm ci")
text = text.replace("RUN pip install", "RUN --mount=type=secret,id=proxy_ca,required=true PIP_CERT=/run/secrets/proxy_ca pip install")
Path("/tmp/InsureTutor.audit.Dockerfile").write_text("# syntax=docker/dockerfile:1\n" + text)
```

```bash
docker build -f /tmp/InsureTutor.audit.Dockerfile \
  --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt \
  -t insuretutor:audit .
docker tag insuretutor:audit insuretutor-audit-insuretutor
APP_PORT=8013 docker compose -p insuretutor-audit up --no-build -d
```
