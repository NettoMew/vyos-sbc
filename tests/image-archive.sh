#!/usr/bin/env bash
# No root, Docker, network, or board compilation: exercise actual xz streams.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "${ROOT}/lib/image.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT
OUT_DIR="${TMP}/output space"; mkdir -p "${OUT_DIR}"
JOBS=1; XZ_LEVEL=0; KEEP_RAW_IMAGE=1
img="${TMP}/test image.img"
printf 'A5E boot image fixture\n' > "${img}"
cp "${img}" "${TMP}/expected"
archive_disk_image "${img}"
[[ -f "${img}" ]]
[[ "$(stat -c %a "${OUT_DIR}/test image.img.xz")" == 644 ]]
# Later xz() definitions inject failures only after this real-tool round-trip.
# shellcheck disable=SC2218
command xz -dc "${OUT_DIR}/test image.img.xz" | cmp - "${TMP}/expected"
(cd "${OUT_DIR}" && sha256sum -c 'test image.img.xz.sha256')
KEEP_RAW_IMAGE=0
archive_disk_image "${img}"
[[ ! -e "${img}" ]]
echo 'PASS xz round-trip, checksum, keep/remove raw'

# Failure must not replace a previous complete archive or delete its raw input.
cp "${TMP}/expected" "${img}"
cp "${OUT_DIR}/test image.img.xz" "${TMP}/previous.xz"
xz() { printf 'partial'; return 1; }
if archive_disk_image "${img}"; then echo 'compression failure ignored' >&2; exit 1; fi
[[ -f "${img}" ]]
cmp "${TMP}/previous.xz" "${OUT_DIR}/test image.img.xz"
[[ -z "$(find "${OUT_DIR}" -name '*.tmp.*' -print)" ]]
unset -f xz
echo 'PASS failed compression preserves raw and previous archive'

xz() {
  if [[ "$1" == --test ]]; then command xz "$@"; else printf 'invalid xz stream'; fi
}
if archive_disk_image "${img}"; then echo 'invalid stream accepted' >&2; exit 1; fi
[[ -f "${img}" ]]
cmp "${TMP}/previous.xz" "${OUT_DIR}/test image.img.xz"
[[ -z "$(find "${OUT_DIR}" -name '*.tmp.*' -print)" ]]
unset -f xz
echo 'PASS failed stream validation preserves raw and previous archive'
