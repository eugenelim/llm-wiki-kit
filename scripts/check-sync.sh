#!/usr/bin/env bash
# check-sync.sh — Verify shared source files match their vault-template copies.
#
# Fails with exit code 1 if any copy has drifted from the shared canonical source.
# Run in CI or before committing changes to shared/ files.
#
# Usage:
#   bash scripts/check-sync.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAIL=0

check() {
    local src="$1"
    local dst="$2"
    if ! diff -q "$REPO_ROOT/$src" "$REPO_ROOT/$dst" > /dev/null 2>&1; then
        echo "DRIFT: $src → $dst"
        echo "  Run: cp $src $dst"
        FAIL=1
    fi
}

# CLAUDE.md — shared source stamped into each vault template
for variant in work family personal; do
    check "shared/CLAUDE.md" "vault-templates/$variant/CLAUDE.md"
done

# CLAUDE.variant.md — per-variant source stamped into _variant/ directory
for variant in work family personal; do
    check "shared/CLAUDE.variant.$variant.md" "vault-templates/$variant/_variant/CLAUDE.variant.md"
done

if [ "$FAIL" -eq 1 ]; then
    echo ""
    echo "Sync check failed. Run 'bash scripts/sync-shared.sh' to propagate changes."
    exit 1
else
    echo "All shared files are in sync."
fi
