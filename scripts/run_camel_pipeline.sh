#!/bin/sh
# Identifier corpus -> CamelCase -> common-substring pipeline.
#
#   classify : split into lower_case / UPPER_CASE / CamelCase
#   camelize : convert the non-CamelCase lists to CamelCase
#   merge    : merge the three lists and de-duplicate
#   substr   : wrap ^id$, enumerate substrings occurring >= threshold times
#
# Usage: run_camel_pipeline.sh [CORPUS] [OUTDIR]
#        (defaults: corpus/identifiers.multilang.txt  work/camel)
set -e

CORPUS="${1:-corpus/identifiers.multilang.txt}"
OUT="${2:-work/camel}"
THRESHOLD="${THRESHOLD:-10000}"

python3 scripts/classify_identifiers.py "$CORPUS" "$OUT"
python3 scripts/camelize_identifiers.py "$OUT"
python3 scripts/merge_identifiers.py "$OUT"
python3 scripts/common_substrings.py "$OUT/merged.txt" --outdir "$OUT" --threshold "$THRESHOLD"
