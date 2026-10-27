#!/bin/sh
# Identifier corpus -> CamelCase -> common-substring pipeline.
#
#   classify : split into lower_case / UPPER_CASE / CamelCase   -> CAMEL dir
#   camelize : convert the non-CamelCase lists to CamelCase     -> CAMEL dir
#   merge    : merge the three lists and de-duplicate           -> CAMEL dir
#   substr   : wrap ^id$, enumerate substrings occurring >= threshold times
#                                                               -> COMMON dir
#
# The case-normalisation artefacts live in CAMEL (default work/camel) and the
# common-substring artefacts in COMMON (default work/common<THRESHOLD>).
#
# Usage: run_camel_pipeline.sh [CORPUS] [CAMEL_DIR]
#        (defaults: corpus/identifiers.multilang.txt  work/camel)
#        THRESHOLD=2000 sh scripts/run_camel_pipeline.sh   # -> work/common2000
set -e

CORPUS="${1:-corpus/identifiers.multilang.txt}"
CAMEL="${2:-work/camel}"
THRESHOLD="${THRESHOLD:-10000}"
COMMON="${COMMON:-work/common$THRESHOLD}"

python3 scripts/classify_identifiers.py "$CORPUS" "$CAMEL"
python3 scripts/camelize_identifiers.py "$CAMEL"
python3 scripts/merge_identifiers.py "$CAMEL"
python3 scripts/common_substrings.py "$CAMEL/merged.txt" --outdir "$COMMON" --threshold "$THRESHOLD"
