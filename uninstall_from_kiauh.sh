#!/usr/bin/env bash
set -euo pipefail

KIAUH_DIR="${1:-$HOME/kiauh}"
DST_DIR="${KIAUH_DIR}/kiauh/extensions/foundry_ui"

if [[ -L "${DST_DIR}" || -d "${DST_DIR}" ]]; then
  rm -rf "${DST_DIR}"
  echo "Removed Foundry UI extension from ${DST_DIR}"
else
  echo "Foundry UI extension is not installed in ${DST_DIR}"
fi
