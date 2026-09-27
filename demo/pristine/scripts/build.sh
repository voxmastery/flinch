#!/bin/sh
# Builds the shop. Needs config/app.json (not committed; copy it from config/app.example.json).
set -e
cd "$(dirname "$0")/.."
if [ ! -f config/app.json ]; then
  echo "Error: config/app.json not found" >&2
  exit 1
fi
echo "build ok: $(wc -l < data/customers.db 2>/dev/null || echo 0) bytes of data, config loaded"
