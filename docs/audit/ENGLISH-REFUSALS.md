# English refusals and automatic embedding preparation

Follow-up to [live-provider verification](LIVE-PROVIDER.md), 21 November 2026.

The running application already reported **hybrid** retrieval with 52 chunks.
Missing embeddings did not explain the reproduced refusals. Basic English
benefit-term and cooling-off questions generated answers, while “What currencies
are available?” was rejected before any model call.

## Changes

- Remove request scaffolding such as “available” and “in simple English” from
  subject checks, and match payment methods to payment modes. Preserve unknown
  substantive modifiers such as veterinary, earthquake and cryptocurrency.
- Normalize exclusion/exclusions and give exclusions their own search vocabulary;
  expanding them into all surrender, inflation and cooling-off risks drowned out
  the relevant clause. Recover English exclusion passages from scored candidates.
- Recognize explicit printed paragraph headings, like form labels, as direct
  evidence for a single-topic question even when the vector candidate is absent.
  Relevance thresholds and claim review still apply.
- Distinguish rejected generated explanations from missing source evidence in
  localized response text. Use the neutral UI heading “Unable to answer reliably”.
  A repair/review provider outage returns only original excerpts with an outage
  notice and `model_generated=false`; rejected claims remain withheld.
- Automatically prepare the pinned local ONNX model during Docker builds. A
  revision-specific BuildKit cache is verified and reused; the image includes the
  model at `/app/models/pinned`, outside the writable data volume. Startup loads
  it and computes the document vectors locally.
- Add `scripts/build.sh` for native model preparation followed by the frontend
  build. Verified existing caches skip download entirely. Missing caches download
  into a resumable staging directory and are published only after verification.
  Corrupt or mismatched published caches fail clearly. Standard HTTPS transfer
  honors configured CA/proxy trust; TLS verification stays enabled.

## Verification scope

- [285 backend tests passed](english-refusals/backend-tests.txt), with one
  existing Starlette/httpx deprecation warning.
- [Build verification](english-refusals/build-verification.json): the first
  Docker model step downloaded and verified the pinned artifacts in 132.9 s.
  A second build reexecuted preparation using the verified cache in 17.8 s,
  without download progress. An interrupted earlier transfer was retained in
  its old isolated build cache; it was not counted as a successful build.
- [Fresh-volume offline container](english-refusals/offline-container.json):
  `--network none`, non-root user, read-only root, no external model mount,
  hybrid-ready with 52 chunks. All 36 backend Python files match the checkout.
- [Before](english-refusals/before.jsonl) and
  [supported live calls](english-refusals/supported-live.jsonl) preserve both
  failures and passes. On the final restarted port 8000,
  [exclusions and currencies](english-refusals/current-live.jsonl) generated
  cited English answers in 41.13 s and 7.68 s respectively.
- [Seven browser groups](english-refusals/browser-regressions.json) passed.
  The [rendered refusal](english-refusals/browser-refusal.png) and
  [runtime result](english-refusals/browser-refusal.json) confirm that an
  unsupported veterinary question still refuses and uses the revised heading.

The added tests cover ordinary English wording against both isolated excerpts
and the actual brochure, unknown modifiers, provider outages, a missing vector
candidate, and existing/missing/interrupted model caches. Live English calls
returned generated answers for currencies, payment methods and risks; the risk
answer took 81.71 seconds, so provider latency remains material.

Native `HF_HUB_OFFLINE=1 ./scripts/build.sh` reused the verified 384-dimension model
and built the frontend. TypeScript checks passed. All seven browser interaction
regression groups passed after rebuilding and restarting the server; attempts
while the static export/server was being rebuilt timed out and were not counted
as passes. These checks do not establish universal answerability or factuality.

The original [external risks](LIVE-PROVIDER.md#profile-comparison-and-remaining-limits)
remain open. This follow-up does not rescan OS advisories or claim production,
physical-device or assistive-technology certification.
