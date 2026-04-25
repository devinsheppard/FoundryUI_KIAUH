#!/usr/bin/env bash
set -euo pipefail

SELF_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
KIAUH_DIR="${1:-$HOME/kiauh}"
MODE="${2:-copy}"
SRC_DIR="${SELF_DIR}/foundry_ui"
DST_DIR="${KIAUH_DIR}/kiauh/extensions/foundry_ui"

if [[ ! -d "${KIAUH_DIR}/kiauh/extensions" ]]; then
  echo "KIAUH extensions directory not found at: ${KIAUH_DIR}/kiauh/extensions" >&2
  exit 1
fi

if [[ ! -d "${SRC_DIR}" ]]; then
  echo "Source extension directory not found: ${SRC_DIR}" >&2
  exit 1
fi

mkdir -p "$(dirname "${DST_DIR}")"

if [[ "${MODE}" == "--symlink" || "${MODE}" == "symlink" ]]; then
  rm -rf "${DST_DIR}"
  ln -s "${SRC_DIR}" "${DST_DIR}"
  echo "Symlinked Foundry UI extension into ${DST_DIR}"
else
  mkdir -p "${DST_DIR}"
  rsync -a --delete "${SRC_DIR}/" "${DST_DIR}/"
  echo "Copied Foundry UI extension into ${DST_DIR}"
fi

echo "Open KIAUH and navigate to: Extensions -> Foundry UI"
