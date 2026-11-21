#!/usr/bin/env bash
# Compile reproducible Linux/CPython 3.13 locks; keep existing pins unless requested.
set -euo pipefail
cd "$(dirname "$0")/.."
mode="${1:---check}"
case "$mode" in --check|--write|--upgrade) ;; *) echo 'Usage: scripts/lock-dependencies.sh [--check|--write|--upgrade]' >&2; exit 2 ;; esac
if [[ "$(uv --version)" != uv\ 0.13.9* ]]; then
  echo 'Lock generation requires uv 0.13.9; use the version documented in docs/DEPENDENCIES.md.' >&2
  exit 2
fi
lock_tmp_dir=$(mktemp -d /tmp/insuretutor-locks.XXXXXX)
trap 'rm -rf "$lock_tmp_dir"' EXIT
args=(--python-version 3.13 --python-platform x86_64-unknown-linux-gnu --generate-hashes --no-annotate --no-header --system-certs --cache-dir "${UV_CACHE_DIR:-/tmp/insuretutor-uv-cache}")
runtime_constraints=()
dev_constraints=()
if [[ "$mode" != --upgrade ]]; then
  runtime_constraints=(--constraint backend/requirements.txt)
  dev_constraints=(--constraint backend/requirements-dev.txt)
fi
uv pip compile backend/requirements.in "${runtime_constraints[@]}" "${args[@]}" --output-file "$lock_tmp_dir/requirements.txt" >/dev/null
uv pip compile backend/requirements-dev.in --constraint "$lock_tmp_dir/requirements.txt" "${dev_constraints[@]}" "${args[@]}" --output-file "$lock_tmp_dir/requirements-dev.txt" >/dev/null
for lock_name in requirements.txt requirements-dev.txt; do
  if [[ "$mode" == --check ]]; then
    diff -u "backend/$lock_name" "$lock_tmp_dir/$lock_name"
  else
    cp "$lock_tmp_dir/$lock_name" "backend/$lock_name"
  fi
done
echo "Dependency locks ${mode#--}: complete"
