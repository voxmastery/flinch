#!/usr/bin/env bash
# Build demo/shop from demo/pristine: a small git repo with a local "origin", Flinch hooks installed.
# Usage: demo/reset.sh            fresh shop, no pain memories
#        demo/reset.sh --keep-pain  restore files but keep .flinch/ (scars, reflex, memories)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
shop="$here/shop"
remote="$here/.remote/shop.git"
keep="${1:-}"

if [[ "$keep" == "--keep-pain" && -d "$shop/.flinch" ]]; then
  mv "$shop/.flinch" "$here/.flinch.keep"
fi
rm -rf "$shop" "$remote"
mkdir -p "$shop" "$(dirname "$remote")"
cp -r "$here/pristine/." "$shop/"

git -C "$shop" init -q -b main
git -C "$shop" -c user.name=shop -c user.email=shop@example.com add -A
git -C "$shop" -c user.name=shop -c user.email=shop@example.com commit -q -m "initial shop"
git init -q --bare -b main "$remote"
git -C "$shop" remote add origin "$remote"
git -C "$shop" push -q origin main

if [[ -d "$here/.flinch.keep" ]]; then
  mv "$here/.flinch.keep" "$shop/.flinch"
fi
if claude plugin list 2>/dev/null | grep -q "flinch@"; then
  "$here/../.venv/bin/flinch" init --project "$shop" --no-hooks >/dev/null  # the plugin provides hooks
else
  "$here/../.venv/bin/flinch" init --project "$shop" --strict >/dev/null
fi
echo "demo/shop reset${keep:+ ($keep)}"
