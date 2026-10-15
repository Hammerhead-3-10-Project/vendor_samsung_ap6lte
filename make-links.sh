#!/usr/bin/env bash
# Create the symbolic links and the empty directories of the stock vendor inside the vendor output directory.
#   make-links.sh <vendor repo dir> <$(TARGET_OUT_VENDOR)>
set -euo pipefail
repo="$1"; out="$2"
while IFS= read -r d; do
  [ -n "$d" ] && mkdir -p "$out/$d"
done < "$repo/dirs.list"
while IFS=$'\t' read -r path target; do
  [ -n "$path" ] || continue
  mkdir -p "$out/$(dirname "$path")"
  ln -sfn "$target" "$out/$path"
done < "$repo/links.list"
