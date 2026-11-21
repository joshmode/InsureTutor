# Runtime image vulnerability triage

Observed 21 November 2026. This is a package-level scanner result and reachability review, not a proof of exploitability or absence of vulnerabilities. Advisory data can change; the exact image and database metadata are recorded in `os-image-scan.json`.

## Scan integrity and initial findings

Trivy 0.76.2 was obtained from the official `aquasecurity/trivy` GitHub release. The 52,714,130-byte Linux x86-64 archive matched the release's published SHA-256 `bc0fc726e017b8927a62b2d3531d7a84ee01769daf5c99ed866dced54089fdbf` before execution. TLS was never disabled. The default `mirror.gcr.io` database endpoint was forbidden by the environment, so the supported official repository `ghcr.io/aquasecurity/trivy-db:2` supplied the database successfully. No unofficial substitute database was used.

The initial image scan found **53 HIGH package/advisory entries, zero CRITICAL**: 48 Debian entries and five Python entries. These are package/advisory pairs, not 53 independent CVEs. We did **not** use `--ignore-unfixed`, ignore IDs, delete scanner metadata to hide code, or manufacture a zero-finding outcome.

### Published-fixed findings remediated

- **CVE-2026-85091 / zlib1g:** upgraded exactly from `1:1.3.dfsg+really1.3.1-1+b1` to the published fixed Debian version `1:1.3.dfsg+really1.3.1-1+deb13u1`. The Dockerfile pins that version and uses HTTPS plus Debian's signed package indexes.
- **Five Python entries:** CVE-2026-114613 and GHSA-6v7p-g79w-8964 (`msgpack` 1.1.2), CVE-2025-47273 (`setuptools` 70.3.0), and CVE-2026-97687 / CVE-2026-97689 (`urllib3` 2.7.0) were identified in installer SBOMs shipped by the image, rather than the application's dependency lock. The application already installed `urllib3` 2.8.0 and does not require msgpack or setuptools. The runtime **physically removes pip and ensurepip with their vendored code** after the hash-verified application installation. It does not remove only SBOM files. A build assertion imports FastAPI, Uvicorn, PyMuPDF, FastEmbed, NumPy and SQLite and checks that neither installer remains. Runtime changes now require a reviewed image rebuild.

**Measured rescan:** 47 HIGH Debian entries remain (11 advisory IDs), with zero CRITICAL and zero HIGH Python entries. Every remaining entry has no published fixed Debian version in the downloaded database. The scan correctly still exits 1. See `os-image-scan.json` and `os-image-vulnerabilities.json`; the initial scan is retained in the corresponding `-before.json` files. A passing package audit on the application virtual environment alone would have missed the image's installer bundle.

## Vendor-unfixed Debian findings retained openly

The downloaded Debian advisory data supplies **no fixed Debian package version** for the following 11 advisory IDs (47 package/advisory entries). This does not establish that no upstream patch exists anywhere; it means this scan cannot identify a published fixed package for the pinned Debian 13 runtime. They remain **unpatched**, not "resolved" or ignored.

| Advisory | Packages reported | Reachability review and mitigation boundary |
| --- | --- | --- |
| CVE-2026-76642 | `bsdutils`, `libblkid1`, `liblastlog2-2`, `libmount1`, `libsmartcols1`, `libuuid1`, `login`, `mount`, `util-linux` | Failed privileged mount helper and post-hook path. The service does not invoke mount helpers or expose a shell/command API. Non-root execution, dropped capabilities and no-new-privileges reduce the relevant privilege preconditions; they do not patch util-linux. |
| CVE-2026-78408 | Same util-linux family above | `nsenter --join-cgroup` authority leakage. The app does not launch `nsenter`, manage namespaces, or join cgroups. Do not grant CAP_SYS_ADMIN, privileged mode, host PID namespace or a Docker socket mount. |
| CVE-2026-78409 | Same util-linux family above | Detached mount-tree/subdirectory symlink resolution. No mount/subdirectory option comes from an HTTP request. Runtime cannot perform privileged mounts. Local code execution or a materially different deployment could change reachability. |
| CVE-2026-78410 | Same util-linux family above | Restricted bind-mount source and owner/group/mode redirection. The app does not create bind mounts or use X-mount options. Read-only root filesystem and capability dropping constrain this path. |
| CVE-2026-54369 | `libacl1` | Symlink traversal through ACL operations. No ACL administration API or command exists in this service. User text is not used as a filesystem path; code/knowledge are read-only and the limited data volume is controlled by the service. Library presence still remains a package finding. |
| CVE-2025-69720 | `libncursesw6`, `libtinfo6`, `ncurses-base`, `ncurses-bin` | Terminal parser/buffer overflow. Uvicorn is a noninteractive service; no curses UI, terminal input, or shell session is provided through the app. Do not expose an interactive terminal as part of this service. |
| CVE-2026-119373 | `libsqlite3-0` | FTS5 heap-buffer issue. Usage accounting uses fixed SQL statements and ordinary tables, not FTS5, SQL submitted by clients, or imported database files. Parameterized values cannot select an FTS5 SQL execution path. Database files remain trusted local state. |
| CVE-2026-119374 | `libsqlite3-0` | Corrupted FTS5 index. The app does not create/query FTS5 tables or accept database uploads. An attacker who can replace the local usage database has crossed a filesystem trust boundary beyond the HTTP data contract. Protect the data volume and its backups. |
| CVE-2026-119379 | `libsqlite3-0` | Crafted session changesets. The app does not accept or apply SQLite changesets, attach arbitrary databases or load client-supplied extensions. Plain bound counter values are the supported input. This is not a patched SQLite library. |
| CVE-2026-16742 | `libsystemd0`, `libudev1` | `systemd-homed` home-record signature handling. The container starts Uvicorn directly and runs no homed daemon or user/home provisioning service. Presence of shared libraries triggers package-level coverage; no homed endpoint is exposed by the application. |
| CVE-2026-9538 | `perl-base` | Archive::Tar memory/entry-size denial of service; Debian status `fix_deferred`. The service does not invoke Perl or process user-supplied archives. No upload/extract route exists. |

The service's ordinary endpoints accept bounded chat JSON and serve the reviewed brochure/static client. These reachability observations are based on that architecture and inspected code; they must be revisited when adding uploads, command execution, database import, terminal functionality, privileged container options or shared writable mounts.

## Deployment boundary and follow-up

Use the hardened Compose runtime settings: non-root application user, read-only root filesystem, all capabilities dropped, no-new-privileges, bounded PIDs/memory and a small writable temporary filesystem. Only the existing data volume needs persistent writes. Those restrictions reduce available attack paths but cannot convert an unpatched library into a fixed library. Do not run this service privileged or mount the Docker socket.

Monitor Debian security advisories and rebuild with a reviewed fixed package or updated pinned base image when one is published. The reproducible image pin is intentionally not floated silently. If organizational policy forbids **any** vendor-unfixed HIGH package, this Debian-based image does not satisfy that policy yet; a reviewed platform change or upstream package update is required. Removing essential OS libraries blindly or suppressing their findings would not satisfy it either.

The scan command keeps findings visible and exits nonzero when HIGH/CRITICAL entries remain:

```bash
/tmp/insuretutor-trivy/trivy image --image-src docker \
  --db-repository ghcr.io/aquasecurity/trivy-db:2 \
  --scanners vuln --severity HIGH,CRITICAL --exit-code 1 \
  --cache-dir /workspace/.cache/trivy --timeout 3m \
  --format json --output /tmp/insuretutor-os-image-vulnerabilities.json \
  insuretutor:hardened-os-audit
```

This scans the runtime image only. The Node builder is not shipped as a runtime service. npm and Python package advisory scans are separately recorded. Lower-severity advisories are outside this HIGH/CRITICAL-filtered result, and future advisories require fresh scans.

The exact final application image was also scanned without a severity filter. See `risk-final-all-severities.json` and `risk-all-severity-triage.csv` for all medium/low/unknown entries. None has a published fixed version in the fetched database; none was suppressed or declared patched.
