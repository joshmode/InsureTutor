# Applied-environment verification — 21 November 2026

Later results: [live-provider verification](LIVE-PROVIDER.md) confirms applied
revision 7, working native/container authentication and additional output fixes.
The authentication blocker below records the earlier revision-4 state.

This follows [the open-item ledger](OPEN-ITEMS.md), using its `bb8e927` baseline.
The newly applied unrestricted network policy allowed the previously blocked
embedding, cross-browser and hosted-CI checks to run. They exposed three real
hybrid-retrieval false refusals, which are now fixed. Live language-model
verification remains blocked by authentication; configured variables alone are
not evidence that generation works. Earlier reports retain their original results.

## Additional fixes

| Severity | Reproduced problem | Implemented change |
| --- | --- | --- |
| Medium | With the actual multilingual embedding model, both Chinese cooling-off questions and “Under this policy, will I pay a withdrawal charge?” refused despite relevant source passages. All three worked in lexical mode. | Strong literal evidence in a selected passage can survive an omitted vector candidate. Grammatical `under` no longer requires an unrelated passage to establish applicability. Four backend regressions cover these causes; the unchanged real-model replay retains all negative controls. |
| Medium | CI exercised lexical mode without downloading the actual embedding model. | A separate CI step downloads an exact official revision, requires `retrieval_mode=hybrid`, checks the three reported queries and runs both existing HTTP evaluation matrices. It cannot silently count lexical fallback as hybrid success. |
| Low | Firefox could assert viewport geometry before resize layout settled; screenshot capture could preserve a transient clipped composer. The old hosted run failed this assertion. | Wait for fonts and matching shell/viewport dimensions, and require the textarea and composer dock to fit before checking or capturing. Existing geometry and overflow assertions remain; no product CSS workaround or skipped browser was used. |
| Low | The local-model setup smoke did not disable ONNX inference telemetry as the application already did. | Disable telemetry before setup inference. Cached model smoke and model-integrity/fallback tests pass. ONNX import can still emit its device-discovery/cache warning; warning-free startup is not claimed. |
| Low | Load-report scope always said “lexical,” including actual hybrid runs. | Report the retrieval mode read from the target's health response. The new hybrid load artifact records the correct scope. |

The literal-evidence rule is a relevance heuristic, not semantic entailment.
Some retrieved contexts still include adjacent passages. Subject applicability,
source-conflict handling, citation checks and generated-claim review remain
necessary; these tests do not prove universal hallucination or injection resistance.

## Verified results

| Check | Measured result and evidence |
| --- | --- |
| Backend | [227 passed](post-config/backend-tests.txt), with one existing Starlette/httpx TestClient deprecation warning. No tests were removed or skipped. Hosted Python 3.13 also reports 227 passing tests. |
| Official embedding model | Downloaded revision `faf4aa4225822f3bc6376869cb1164e8e3feedd0` from the FastEmbed-supported Qdrant repository. A real **384-dimension** inference passed. The weights' SHA-256 matches the official revision's published LFS hash: [provenance](post-config/model-provenance.json), [complete manifest](post-config/model-manifest.json). Weights are cached outside Git. |
| Fresh 20-question replay | [Before](post-config/hybrid-before.json): three of six supported controls failed only in hybrid mode. [After](post-config/hybrid-replay.json): all six supported controls answer with citations; seven unsupported, six injection and one fake-citation control refuse or block. Every returned citation's ID, document, page and excerpt matches the source API. All responses have `model_generated=false`. |
| Existing HTTP matrices, actual hybrid mode | [20/20 adversarial](post-config/hybrid-adversarial.json) and [10/10 held-out](post-config/hybrid-held-out.json) mechanical checks. These measure source availability, identity and abstention; they award no generated-answer factuality score. |
| Three browser engines | Chromium: [13 original](post-config/chromium/browser-risk-results.json) + [7 regression groups](post-config/chromium-regressions/ui-regressions.json); Firefox: [13](post-config/firefox/browser-risk-results.json) + [7](post-config/firefox-regressions/ui-regressions.json); WebKit: [13](post-config/webkit/browser-risk-results.json) + [7](post-config/webkit-regressions/ui-regressions.json). **60 groups total**. Screenshots were rendered and inspected. Tests distinguish real API requests from controlled UI fixtures. Checked home/source-dialog states have zero axe A/AA violations, and no unexpected JavaScript/console errors were observed. |
| Actual hybrid responsiveness | [24 requests, client concurrency 8](post-config/hybrid-load.json): 10 HTTP200 and 14 HTTP429, nine successful health samples, health p95 **19.52 ms**, chat p95 **184.18 ms**. Isolated model-free server with 120/minute and 2000/day allowances. This is a bounded local responsiveness smoke, not production or funded-provider capacity. |
| Hardened Docker with real embeddings | [Exact image/runtime](post-config/docker-hybrid.json): non-root `app`, read-only root and model mount, all capabilities dropped, no-new-privileges, PID/memory/CPU bounds. Health reports hybrid mode and 52 chunks; all three reported query regressions pass. The same container passes [20 adversarial](post-config/docker-hybrid-adversarial.json) and [10 held-out](post-config/docker-hybrid-held-out.json) checks. No language-model calls were made. |
| Public repository and hosted CI | Unauthenticated GitHub API confirms the repository is public. [Run 44900825053](https://github.com/joshmode/InsureTutor/actions/runs/44900825053) succeeds at code commit `97839f0`, including hash-lock checks, dependency audits, backend tests, TypeScript/static export, all three browsers, and the real pinned-model step. [API metadata](post-config/hosted-ci.json) and [bounded log extract](post-config/hosted-ci-extract.txt). The subsequent screenshot-only synchronization refinement also passes all three local browser suites. |

The brochure remains unchanged, SHA-256
`2043de40845267fdb1f657280438f3ded04edda6692791960415116a5668a475`.
The assignment/source mapping and PDF page-17 discrepancy remain documented in
[the second-pass audit](SECOND-PASS.md).

## Environment and reproducibility

Observed running configuration revision 4 has unrestricted networking enforced;
the URL/model variables and key requirement report ready. Actual GitHub,
official model-host and Playwright downloads now succeed. This closes the
earlier network-blocked checks without establishing that every configured
credential is valid.

The local machine has no privileged package helper. Missing Firefox/WebKit
libraries were downloaded from signed official Debian repositories into an
isolated workspace APT state and extracted under the workspace; system sources
and packages were not modified. WebKit's bundle has symlinks only for missing
libraries. Its host preflight was bypassed locally after independently loading
those libraries; the actual engine and full application checks ran. Firefox ran
outside the command filesystem sandbox with its own browser sandbox enabled,
because that filesystem sandbox prevents Firefox creating its user namespace.
The hosted run uses Playwright's standard `install --with-deps` for all engines
without either local workaround.

Reproduce the real-model checks with the locked dependencies and a writable
cache (set `LLM_API_KEY=` for model-free evaluation):

```bash
export EMBEDDING_CACHE_DIR=/tmp/insuretutor-model
export EMBEDDING_LOCAL_MODEL_DIR=/tmp/insuretutor-model/pinned
python -m backend.app.scripts.download_embedding_model --revision faf4aa4225822f3bc6376869cb1164e8e3feedd0
LLM_API_KEY= DATA_DIR=/tmp/insuretutor-hybrid uvicorn backend.app.main:app --host 0.0.0.0 --port 8018 --no-proxy-headers
# In another shell, verify health says hybrid, then:
python scripts/audit_rag.py --base-url http://127.0.0.1:8018
python scripts/evaluate_provider.py --base-url http://127.0.0.1:8018
```

Do not set either embeddings enable flag to false for this run. Browser commands
and the separate `--require-model` live evaluator are in the README; CI records
the complete supported-runner setup.

## Still open, with explicit boundaries

- **Live provider authentication:** one bounded call through the actual
  OpenAI-compatible client returned **HTTP401**. The configured provider host
  differs from the key requirement's allowed destination. After the owner's
  “done” reply, both the running configuration and bound draft still report
  `api.openai.com` for that requirement. The configuration tool refuses to alter
  an existing binding and directs this edit to environment settings; no duplicate
  key requirement or replacement draft was saved. Owner settings must bind a
  key issued by the selected provider to its matching hostname, then apply the
  change to this environment. The mismatch is observed; HTTP401 alone does not
  prove which authentication component rejected the request. Provider URL,
  model and credentials are omitted from public evidence. Live drafting,
  repair/review, Chinese fluency and claim-by-claim semantic accuracy therefore
  remain **unverified**, with no fallback counted as live success.
- **Vendor OS advisories:** the existing scan/triage retains **47 HIGH,
  109 MEDIUM, 67 LOW and 9 UNKNOWN** entries, zero CRITICAL, and no published
  fixed versions in the measured Debian data. This pass changes no runtime
  dependencies/base and does not claim a new OS scan or accepted risk. The
  [complete all-severity ledger and tested alternative-base results](OPEN-ITEMS.md#os-findings-investigated-still-open)
  remain applicable; no advisory was suppressed to close the report.
- **Conflicting insurer source:** the page-17 bilingual minimum-increase
  figures still conflict. Existing localized disclosure remains; the
  [clarification request](INSURER-CLARIFICATION.md) is prepared and **unsent**.
  Only an authoritative source can settle the amounts.
- **Real devices and operating context:** physical devices and actual assistive
  technology, production traffic, distributed-replica budgets, provider
  retention/jurisdiction and vendor billing after cancellation remain outside
  these measured local checks. Automated accessibility and sandbox tests do not
  certify those conditions.

No claim is made that all engineering risks have been eliminated. The remaining
items have measured evidence or a named external dependency; passing unit tests,
ready configuration metadata and matching citation IDs do not close them.
