# Live-provider follow-up — 21 November 2026

Authentication now works. Running environment revision **7** has the intended
secret destination applied; real native and hardened-container requests generate
cited answers. This follows [the applied-environment audit](CONFIG-VERIFICATION.md)
at baseline `faa753a` and implements additional problems exposed by actual model
output. The selected `low` reasoning profile passes **20/20** in the unchanged
extended replay and **10/10** in the strict live held-out set. The faster `none`
profile scored **18/20** in that replay; its failures remain recorded.

## Implemented fixes

| Issue | Change and verification |
| --- | --- |
| Reasoning consumed the entire output allowance | A captured withdrawal request used all 1,200 output tokens on internal reasoning and returned no answer text. The configurable default cap is now 3,000, with the same daily reservation limit. Added optional `LLM_REASONING_EFFORT`, omitted when unset/blank, with validated standard values. The selected provider accepts `none`: the same short connection probe fell from 10.84 s to 0.70 s and reported zero reasoning tokens. Other models may require the field to remain unset. |
| Truncated text could be treated as a completed response | Reject `finish_reason=length` in both completion and streaming clients, including a nonempty partial answer. Four regressions first failed and now pass. |
| A model-approved surrender summary omitted a material start event | The brochure's first-14-year period also starts from each increase in Basic Sum Insured. Added a source-conditioned duration check, explicit writer/reviewer instructions and repair feedback. Tests reject an unanchored period in all three languages, retain per-layer wording, accept adjacent qualifications citing the same supporting source, and reject qualifications borrowed from another source or benefit. |
| One repair only received the first of several failures | Collect bounded feedback on independent claims for the existing single repair attempt. A regression combines an uncited introduction and missing clock qualification; both must be communicated for the repaired answer to pass. The maximum remains draft + one repair + review. |
| Sentence-ending numbers escaped bare-number validation | The numeric tokenizer excluded a number immediately before a full stop. Unsupported `101.` and `101.5.` could therefore pass against source value `100.`. Both regressions now reject; valid decimal and cross-script values remain accepted. |
| Equivalent currency formatting caused false refusals | Normalize explicit `MOP$`/`MOP`, `USD`/`US$` and `HKD`/`HK$` labels. Regressions retain rejection of a different currency/amount and ambiguous bare dollars. |
| Simplified requests could return Traditional prose despite reviewer approval | Normalize generated Chinese prose before claim validation and review, including repaired drafts. Simplified and Hong Kong Traditional forms use a hash-locked OpenCC dictionary package. Literal quotes, URLs, numbers, citation markers and original citation excerpts retain their source characters. Conversion runs off the event loop and skips oversized drafts for the existing validator to reject. |
| Quote repair repeated the rejected quotation | Generation requests paraphrases; the repair explicitly addresses non-verbatim quotations, uncited introductions and surrender-period conditions. Exact-source quote validation remains enforced. |
| Ordinary rights/fee wording was rejected | Canonicalize `rights` to `right` and fee-related `free` to the charge subject. Unknown substantive topics still have to occur in selected evidence; an unrelated veterinary modifier remains rejected. |
| Compose ignored provider values exported by the caller | Forward key, base URL, model and optional reasoning setting, retaining dotenv configuration and optional model-free operation. A running container probe verifies fake host values, and configuration checks verify dotenv values and literal dollar preservation. No real credential is printed or written into the image. |
| Hosted CI used actions with a deprecated Node 20 runtime | The successful evidence-commit run emitted a runtime deprecation warning. Pin checkout and both setup actions to official Node 24 releases, retaining read-only permissions and disabled checkout credentials. [Release/runtime evidence](live-model/ci-action-runtimes.json) records immutable commits and official release URLs. The application Node version remains 22. |

A separate review call to the same configured model previously approved an
incomplete surrender summary. Its approval is therefore not an entailment certificate. The additional
checks address the observed failures; they do not implement general natural-language
proof or establish universal injection resistance.

## Measured results

| Check | Result and evidence |
| --- | --- |
| Applied credentials | [Authenticated SDK smoke](live-model/authentication.json) returns exactly `OK`. [Verified profile](live-model/verified-profile.json) records destination agreement, active hybrid retrieval and ready application health without publishing the provider identity or credentials. |
| Backend | [266 passed](live-model/backend-tests.txt), one existing Starlette/httpx TestClient deprecation warning. New failures were reproduced before their fixes. |
| Hosted CI | [Run 44910556317](https://github.com/joshmode/InsureTutor/actions/runs/44910556317) passes at commit `3d55669`, including backend tests, complete dependency audit, client build, all three browser engines and the real pinned embedding model. [Recorded metadata](live-model/hosted-ci.json). CI uses no funded language-model key. Compose forwarding is separately verified below. |
| Strict live held-out set | [10/10 on the selected profile](live-model/profile-low/held-out.json), with **five actual generated answers**. Supported answers must have `model_generated=true`; excerpt fallback cannot earn a live-model pass. |
| Unchanged extended replay | [20/20 on the selected profile](live-model/profile-low/fresh.json). All 14 unsupported/injection/fake-citation controls refuse or block; all six original positive controls return generated answers. The [faster profile's 18/20](live-model/final/fresh.json) remains visible. |
| Existing adversarial matrix, live provider configured | [20/20 mechanical checks on the selected profile](live-model/profile-low/adversarial.json), including misleading guarantees and personal determinations. Many questions deliberately abstain, and some have no expected answer kind. This score is not an accuracy score. |
| Source identity | [Citation metadata check](live-model/source-review.json) compares returned IDs, documents, pages and excerpts across HTTP, UI and Docker artifacts. Matching metadata is checked separately from support in the original PDF. |
| Live UI | [Three actual generated responses on the fast profile](live-model/browser/results.json), without response fixtures or unexpected runtime errors: English interest starter, English benefit term and Simplified cooling-off. Checked exact modal excerpt and PDF page link, New conversation, language selection and a 390×844 viewport with the composer visible. [Desktop](live-model/browser/after-live-chat.png), [original source](live-model/browser/after-live-source.png), [mobile](live-model/browser/after-live-mobile.png). The selected profile also passes [live mobile/source checks](live-model/browser-low/results.json), with [its rendered answer](live-model/browser-low/mobile.png). |
| Hardened Docker and actual provider | [Live container evidence](live-model/docker-live.json): a generated benefit-term answer and an unsupported-property refusal, real local embeddings, 52 chunks, current backend bytes and matching source-PDF hash. Non-root `app`, read-only root/model/CA mounts, all capabilities dropped, no-new-privileges, PID 128, memory 2 GiB and CPU 2. The Chinese dictionaries load under those restrictions. Runtime uses the supplied platform proxy/CA with TLS verification enabled; credential values are passed by environment name. |
| Compose configuration | [Host/dotenv/runtime checks](live-model/compose-configuration.json) confirm provider forwarding and preservation of a fake key containing a dollar sign. The probe creates no provider requests. |
| Dependencies | [All 55 locked development packages](live-model/python-dependency-audit.json): zero known vulnerabilities, zero skipped packages. Runtime has 50 packages; only `opencc-python-reimplemented==0.1.7` was added and existing pins were retained. [Both locks reproduce](live-model/lock-check.txt), and the tracked Dockerfile builds on Python 3.13. This is not an OS-image scan. |

The original PDF was read alongside the generated facts: benefit term on pages
14/18; Hong Kong currencies and payment modes on page 16; two insurability-option
uses on pages 12/16; the 365-day redundancy option and Basic Plan restriction on
pages 11/12; cooling-off timing/refunds and claims-information references on page
15; maximum sum insured on page 17; withdrawal fees and surrender clocks on pages
12/18. The live interest answer's assumed-rate wording, 15-year Account Value
floor and rate-setting discussion were checked against pages 5, 8, 13 and 16.
This is a bounded source review of returned examples, not a human-domain-expert
validation or a universal semantic score. Automated artifacts retain their
explicitly unverified semantic-factuality fields.

## Profile comparison and remaining limits

The [single-run comparison](live-model/profile-comparison.json) keeps the same
model, questions, output/time limits and validation/review gates:

| Reasoning effort | Extended replay | Strict held-out | Six positive controls: median / maximum time |
| --- | --- | --- | --- |
| `none` | 18/20; four generated controls | 10/10; five generated | 5.83 s / 10.84 s, including the two refusals |
| `low` — selected | 20/20; six generated controls | 10/10; five generated | 24.99 s / 36.09 s |

These small, single-client samples measure a quality/latency tradeoff, not
production capacity or statistical reliability. The current app uses `low`.

The fast-profile replay returned `insufficient` for **“我想了解索偿程序。”**
and **“冷静期有多长？”** instead of the original expected generated answers.
The brochure only directs claims readers to the insurer's websites; it does not
give the full claims procedure. Cooling-off duration is explicitly available,
so its refusal is an unnecessary abstention. The same Simplified cooling-off
question succeeds in the live UI run and both succeed in the selected-profile
replay. An earlier run also refused the English
interest starter, which later produced a cited answer under the same final code.
These observations show model/validation variability. The original scores and
failed responses are preserved; a passing selected-profile sample does not
certify consistent answerability for arbitrary questions.

The remaining [vendor OS findings](OPEN-ITEMS.md#os-findings-investigated-still-open)
are not closed: the earlier measured scan retains 47 HIGH, 109 MEDIUM, 67 LOW and
9 UNKNOWN entries without published fixes in that Debian data. The final image
keeps the same OS inputs; this follow-up does not claim a fresh OS advisory scan.
The page-17 bilingual minimum-increase conflict still needs insurer clarification;
the [prepared request](INSURER-CLARIFICATION.md) remains unsent. Actual assistive
technology/devices, production traffic, shared limits across separate-volume
replicas and provider billing/retention/jurisdiction remain outside these checks.

## Failed runs, budgets and reproduction

The [1,200-token baseline](live-model/fresh-baseline-1200.json),
[captured truncation](live-model/output-limit-before.json),
[larger-cap trace](live-model/output-limit-after.json),
[format failures](live-model/format-before.json) and
[multi-error repair before](live-model/combined-repair-before.json)/
[after](live-model/combined-repair-after.json) remain available. The larger-cap
trace also exposed the missing clock qualification and must not be read as a
semantic success. Intermediate and interrupted files are named explicitly.

Repeated staged testing eventually [exhausted the isolated server's reservation
allowance](live-model/exhausted-test-budget.json): 135 reserved calls and 358,200
reserved output tokens left insufficient room for another 3,000-token call under
the 360,000 limit. The resulting HTTP429 cases remain in
`live-model/reasoning-disabled-budget-exhausted/`. That database was retained;
production counters were not reset. The final matrices use a new isolated test
fixture with the same daily token reservation limit. Separate fixtures are not a
distributed budget.

For the selected provider, the current ignored local `.env` sets
`LLM_REASONING_EFFORT=low`; it contains no provider key or URL. The setting is
optional and should be cleared or changed when the selected model does not
support it. The default per-call timeout remains 60 seconds and chat deadline
180 seconds. Daily accounting conservatively reserves the maximum output cap,
not the much smaller actual text length. The verified embedding cache is outside
Git and reachable through the ignored default cache location.

With credentials supplied securely and the documented pinned model cache ready,
reproduce the strict live check against a running app with:

```bash
python scripts/evaluate_provider.py --base-url http://127.0.0.1:8000 --require-model
```

Use the saved questions to replay the other matrices once, retaining all outputs.
Model results vary; repeated attempts until a green score would not establish
reliable behavior. The browser suite's fixtures, CI's model-free checks and these
actual provider calls are distinct evidence.
