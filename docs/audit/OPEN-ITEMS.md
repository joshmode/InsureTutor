# Open-item remediation — 21 November 2026

Baseline: `bb1c210`. This is the current disposition of the open items from
[the second pass](SECOND-PASS.md) and [the earlier risk ledger](RISK-CLOSURE.md).
Those reports and their evidence remain historical. Remaining external risks
are neither patched nor accepted merely because local checks pass.

## Implemented and verified

| Item | Result |
| --- | --- |
| Unsupported reinstatement-interest question returned adjacent excerpts | The unchanged question now abstains. English subject words must occur in the selected evidence; an occurrence in an unrelated exclusion cannot establish a fee. Functional question wording is excluded from subject matching. No unsupported-topic blacklist was introduced. |
| Same-source monetary-value swap | Explicit monetary labels and currency amounts are checked together. The reported withdrawal charge of US$4 is rejected, including “current” padding, `fee`/`charge`, actual page-18 footnotes, three currencies, and the actual page-17/page-18 two-citation combination. Correct figures remain accepted. |
| Overrestriction and PDF parsing risks in the new checks | Regressions preserve frequency, partial withdrawal, cooling-off refunds, issue age, surrender duration, option changes, payment timing, English claims and missed-premium questions, plus all 12 localized starters. Footnote digits and spaced percentages do not become fabricated fee values. An independent reviewer reproduced counterexamples; the required fixes and combined cases pass. |
| Evaluation clients could abort before a configured server deadline | Adversarial, held-out and load clients share bounded deadline parsing from health. Transport tests verify a 285-second configuration; health monitoring retains its own short deadline. |
| “Require model” could pass excerpt fallback when credentials were configured | The API now exposes `model_generated`, set only on the successful generation/review path. Fixed responses and fallback excerpts remain false. Live evaluation rejects fallback answers even with `llm_configured=true`. Transport fixtures test rejection and acceptance; scripted-provider regressions test the server flag. The browser validates this additive field when present. |

These checks reduce specific failure modes. Word overlap still does not prove
that passages answer a question. Monetary parsing is limited to recognizable
English labels with explicit currencies; reordered, implicit or multilingual
claims still require semantic review. That review uses a separate call to the
configured model and can share its errors. No general entailment or injection
immunity claim is made, and no live semantic score is awarded by these tests.

## Measured verification

- [Backend](open-items/backend-tests.txt): **223 passed**, one existing
  Starlette/httpx TestClient deprecation warning. The focused evaluator rerun
  also passed all [three transport tests](open-items/evaluation-client-tests.txt).
- [TypeScript/static export](open-items/frontend-build.txt) and the tracked
  [Dockerfile build](open-items/docker-build.txt) succeeded. No dependency lock
  or production allowance was relaxed.
- Container Chromium: [13 original groups](open-items/container-browser/browser-risk-results.json)
  and [7 regression groups](open-items/container-ui/ui-regressions.json) passed.
  The latter includes six malformed-response variants. Real API calls and
  controlled UI fixtures are identified in the scripts. No unexpected browser
  errors or axe A/AA violations occurred in checked home/source-dialog states.
- [Unchanged 20-question replay](open-items/fresh-rag-replay.json): **20/20**
  source-identity/abstention checks; all seven unsupported questions abstain and
  all six supported controls retain citations. Every response records
  `model_generated=false` in this model-free run.
- [Existing adversarial matrix](open-items/adversarial-http.json): **20/20**
  mechanical checks. [Held-out matrix](open-items/held-out.json): **10/10**.
  These 50 combined checks are not a live-model accuracy benchmark.
- [Load smoke](open-items/load.json): 24 requests at client concurrency 8,
  18 HTTP200 and 6 HTTP429 outcomes; 19 health samples, health p95 **14.37 ms**,
  chat p95 **425.51 ms**. The isolated lexical server used 120 requests/minute
  and 2000/day to exercise the concurrency allowance. This does not establish
  production or embedding-model capacity.
- [Container/restart checks](open-items/docker-results.json): non-root user,
  read-only root, dropped capabilities, no-new-privileges and resource limits;
  preserved schema-5/52-chunk volume; source-PDF fingerprint; current backend
  bytes; expected abstention; false model-generation flag; absent installers.

## OS findings: investigated, still open

The final image's [complete scan](open-items/image-vulnerabilities.json),
[summary](open-items/image-summary.json) and
[all-severity index](open-items/all-severity-triage.csv) retain every finding.
The update-enabled scan used official Trivy advisory data dated 21 November
2026; exact database timestamps and image identity are saved. There are zero
published fixed-version entries in this measured Debian data. Zero CRITICAL
and zero Python-package findings were reported for the application image;
**47 HIGH, 109 MEDIUM, 67 LOW and 9 UNKNOWN OS entries remain open**.

Two official alternative bases were pulled and scanned using the same database:

| OS scan target | Critical | High | Medium | Low | Unknown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current pinned application runtime | 0 | 47 | 109 | 67 | 9 |
| Official Python 3.13 Bookworm base | 2 | 43 | 118 | 94 | 12 |
| Official distroless Python Debian 13 base | 0 | 89 | 150 | 60 | 26 |

The [comparison](open-items/base-comparison.json) records exact identities;
full [Bookworm](open-items/bookworm-base-scan.json) and
[distroless](open-items/distroless-base-scan.json) reports are retained. These
are base-image experiments, not alternative application builds. Counts depend
on distribution metadata and scanner coverage, not just exploitability.
Bookworm adds CRITICAL zlib findings; distroless adds reported Python/SSL and
Kerberos exposure. Neither established a safer drop-in replacement, so the
verified pinned runtime was retained. No scanner suppression, metadata removal
or unreviewed source-built system library was used to manufacture a clean scan.

The existing [high-severity reachability review](os-risk-triage.md) and Compose
restrictions still apply. Lower-severity exploitability has not been exhaustively
certified. Those package findings cannot honestly be closed without a reviewed
fixed package/platform or further authoritative evidence.

## Disposition of the remaining external items

| Item | Action taken / remaining dependency |
| --- | --- |
| Live model quality, attribution and Chinese fluency | [Explicit live evaluation](open-items/live-provider-status.json) exits 2, blocked: no model key is configured. Added the generation-origin check so later provider failure cannot masquerade as live success. No real-provider factuality result exists. |
| Embedding download and hybrid relevance/latency | Retried official Hugging Face metadata: proxy CONNECT403. Existing revision/hash verification remains enforced. A real pinned model download and hybrid evaluation require an applied network grant. |
| Firefox and WebKit | Retried the official Playwright CDN: CONNECT403. Both browser scripts support these engines; only Chromium ran. No engine substitution is counted as verification. |
| Hosted CI and public repository visibility | GitHub API retry remains CONNECT403. CI configuration exists and push triggers it; its hosted result and unauthenticated public access are not verified here. |
| Environment setup publication | Refreshed and successfully saved the draft; the running policy remains revision 1 with no custom hosts or ready secrets. The available configuration tool saves drafts and cannot apply/publish them. Owner review/save/publication and a subsequent observed-readiness check are required. |
| Conflicting page-17 currency figures | Existing localized source-conflict refusal remains. Prepared an [unsent clarification request](INSURER-CLARIFICATION.md) with both versions, page and source fingerprint. Only authoritative insurer/source clarification can resolve it; the original PDF was not altered. |
| Actual screen reader, physical keyboard/device and production behavior | Current browser/reflow/axe checks are recorded. No actual assistive-technology or physical-device test, public deployment or production capacity assessment was performed. |
| Shared budgets across replicas, remote billing and provider privacy | Single-volume SQLite coordination, conservative reservations, local disconnect cleanup and in-page privacy notices remain implemented/tested. Separate-volume replicas need deployment-level shared controls. Vendor cancellation/billing, retention and jurisdiction depend on the chosen provider and operator; no unknown contract was certified. |

[Fresh prerequisite evidence](open-items/external-prerequisites.json) records
the denials without credentials. The saved draft retains the Hugging Face and
Playwright domains and adds **api.github.com** and **api.openai.com**. It prepares
the app's existing default OpenAI URL/model plus a user-provided `LLM_API_KEY`
requirement; no secret value was supplied. Another provider needs its matching
URL, model and allowed secret destination before publication. The app itself
still supports model-free operation.

To finish the blocked checks, the environment owner must review/save/publish
the prepared configuration and supply the provider key securely in settings,
then confirm current runtime enforcement before retrying. Do not paste keys
into chat. A saved draft does not establish that network access, credentials
or a new snapshot are active. The browser/model download and live-evaluation
commands are documented in the README and existing setup instructions.
