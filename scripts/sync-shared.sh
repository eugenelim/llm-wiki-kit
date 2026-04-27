#!/usr/bin/env bash
# sync-shared.sh — Propagate shared source files into vault-template copies.
#
# Run after editing any file in shared/ to keep vault templates in sync.
#
# Usage:
#   bash scripts/sync-shared.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

for variant in work family personal; do
    cp shared/CLAUDE.md "vault-templates/$variant/CLAUDE.md"
    echo "Synced CLAUDE.md → vault-templates/$variant/CLAUDE.md"
done

for variant in work family personal; do
    cp "shared/CLAUDE.variant.$variant.md" "vault-templates/$variant/_variant/CLAUDE.variant.md"
    echo "Synced CLAUDE.variant.$variant.md → vault-templates/$variant/_variant/CLAUDE.variant.md"
done

echo ""
echo "Done. Run 'bash scripts/check-sync.sh' to verify."
