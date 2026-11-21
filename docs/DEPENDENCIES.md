# Reproducible dependencies and build trust

The supported and exercised container target is Linux x86-64 / CPython 3.13. Development was additionally verified on Linux x86-64 / CPython 3.12. ARM, Windows and macOS native Python environments have not been verified by this lock validation.

## Python

`backend/requirements.in` and `backend/requirements-dev.in` are the reviewed direct declarations. Their `.txt` counterparts are **complete transitive locks**, with every distribution pinned to an exact version and SHA-256 allowlist. Runtime has 50 locked packages; development has 55. The live-provider follow-up adds only `opencc-python-reimplemented==0.1.7` for consistent Chinese scripts; existing versions remain pinned. Conversion runs before claim validation and review, preserves literal quotes/URLs, and never changes citation excerpts. The earlier audit measurements below cover the initial 49/54-package locks; the later complete audit is in `docs/audit/live-model/python-dependency-audit.json`.

Existing install commands remain compatible. Install with integrity enforcement:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r backend/requirements-dev.txt
.venv/bin/python -m pip check
```

Wheels are required so an unexpected source build cannot introduce unpinned build dependencies. A missing compatible wheel is an explicit platform/toolchain limitation, not a reason to turn off integrity checks.

Lock generation uses **uv 0.13.9**. Provision that reviewed version using the environment's trusted toolchain; generation is not required to install the application. The script checks the tool version and supports:

```bash
scripts/lock-dependencies.sh --check    # Default: prove regenerated locks are identical
scripts/lock-dependencies.sh --write    # Regenerate while retaining existing version constraints
scripts/lock-dependencies.sh --upgrade  # Intentionally re-resolve transitive versions; review the diff
```

The script targets CPython 3.13 on Linux x86-64, uses system TLS trust, and never writes credentials or package-index authentication into a lock. It compiles into a temporary directory and compares before changing files. If a direct version change conflicts with the old lock, use `--upgrade` intentionally, review changed dependencies and release notes, rerun relevant tests, and re-audit. Hashes constrain artifacts; they do not establish that a maintainer or registry is uncompromised.

## Frontend and container bases

Frontend installs use the committed `frontend/package-lock.json` with `npm ci`. No frontend dependency was added by this hardening change.

The Dockerfile pins the Node and Python **multi-platform image index digests**, resolved from the official registry on 21 November 2026. A moving tag no longer silently changes those images. The human-readable tags remain as hints. The resulting application image still changes when source or locks change; the digest pins the inputs, not an everlasting security verdict. Review base-image updates periodically and rebuild after a security update.

## Secure builds behind an HTTPS proxy

Ordinary builds retain the image's normal certificate trust:

```bash
docker compose up --build
```

Some managed environments intercept HTTPS using an organizational CA. Both npm and pip can receive a trusted PEM bundle through the optional **BuildKit secret** `build_ca`:

```bash
docker build \
  --secret id=build_ca,src=/etc/ssl/certs/ca-certificates.crt \
  -t insuretutor:local .
```

Or use the additive Compose override:

```bash
BUILD_CA_FILE=/etc/ssl/certs/ca-certificates.crt \
  docker compose -f docker-compose.yml -f docker-compose.build-ca.yml up --build
```

`BUILD_CA_FILE` is the path to a trusted CA bundle, not an API key. The bundle is mounted only in dependency and signed OS-package download build steps and is not copied into image layers. `npm --strict-ssl=true`, pip TLS verification and package hashes stay enabled. Do not use `--trusted-host`, `strict-ssl=false` or disable certificate verification. Runtime provider HTTPS behind a proxy may separately need the platform's supported trust configuration; build trust does not configure a running provider connection.

## Audit evidence and scope

On 21 November 2026:

- `scripts/lock-dependencies.sh --check` reproduced both files byte-for-byte.
- A fresh Python 3.12 development virtual environment installed all 54 packages with `uv pip install --require-hashes --only-binary=:all:`; `uv pip check` passed.
- The tracked Dockerfile built directly with `build_ca`, installing all 49 runtime packages using `pip --require-hashes --only-binary=:all:` on Python 3.13. No temporary Dockerfile or disabled verification was used.
- `pip-audit 2.10.1 --disable-pip --require-hashes -r backend/requirements-dev.txt` audited all 54 locked packages through PyPI: **zero known vulnerabilities and zero skipped packages**. The audit tool was installed outside the application virtual environment.
- `npm audit --json` against the existing frontend lock reported **zero known vulnerabilities**.

Results are saved in `docs/audit/python-dependency-audit.json`, `docs/audit/npm-audit-current.json`, and `docs/audit/locked-docker-build.txt`. Advisory databases change. These results are not an OS-image vulnerability scan, a historical secret scan, or a guarantee against unknown supply-chain compromise.

## Runtime operating-system findings and installer removal

The later native image scan is recorded separately in `docs/audit/os-image-scan.json` and `docs/audit/os-risk-triage.md`; the earlier Python package audit does not cover operating-system packages or pip's bundled installer dependencies.

The Dockerfile now installs the exact published Debian `zlib1g` security update `1:1.3.dfsg+really1.3.1-1+deb13u1`, using signed Debian indexes over HTTPS. It removes the pip installer and ensurepip's bundled installer after the hash-verified application install. Runtime dependency changes require a reviewed image rebuild; the running service intentionally cannot install packages. This removes unused installer code, not merely scanner metadata. Build-time imports verify FastAPI, Uvicorn, PyMuPDF, FastEmbed, NumPy and SQLite remain available. The optional CA mount is read-only and world-readable only inside the apt build step so Debian's privilege-dropped `_apt` downloader can read the **public CA bundle**; no private key belongs in that bundle.

`--require-hashes` still controls application packages. The OS security update is explicitly version-pinned; if that exact Debian package is no longer served, the build fails and the pin must be intentionally reviewed. Updating every OS package to a moving latest version is not performed. Published-fixed advisories are remediated; vendor-unfixed advisories remain openly triaged and are not ignored by scanner flags.
