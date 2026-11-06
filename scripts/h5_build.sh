#!/bin/bash
# H5: rebuild the canonical-grid dictionaries and their cyclic bigram matrices.
#
# Dictionary: --sample 20 over work/camel/merged_training.txt (the 5% sample the
# whole grid was built with, so the word lists stay comparable across V).
# Adjacency: --stride 0 (the entire training corpus) -- the model needs the full
# counts even though the word list comes from a sample.
#
# Usage:  bash scripts/h5_build.sh [ns|s0|both]     (default: both)
#         OUT=/tmp/h5check bash scripts/h5_build.sh ns    # build elsewhere
#
# Cost on the current box (4 cores): about 1 minute per V, dominated by the
# stride-0 adjacency pass.  Run it detached if you are not waiting:
#
#   nohup bash scripts/h5_build.sh > work/h5_build.log 2>&1 &
#   tail -5 work/h5_build.log; grep -c H5_DONE work/h5_build.log
set -u
cd "$(dirname "$0")/.." || exit 1
export PYTHONUNBUFFERED=1

CORPUS=work/camel/merged_training.txt
OUT="${OUT:-work}"
WHICH="${1:-both}"
JOBS="${JOBS:-$(nproc)}"

build() {   # $1 = num_pairs, $2 = sample, $3 = dir suffix
    local n="$1" s="$2" suffix="$3"
    local v=$((n + 64))
    local dir="$OUT/tw${v}${suffix}"
    echo "=== V=$v num_pairs=$n sample=$s suffix='$suffix' start $(date -Is) ==="
    python3 scripts/tree_words.py train \
        --corpus "$CORPUS" \
        --num-pairs "$n" \
        --sample "$s" \
        --stride 0 \
        --outdir "$dir" \
        --jobs "$JOBS" || echo "!!! V=$v suffix='$suffix' FAILED rc=$?"
    echo "=== V=$v suffix='$suffix' end $(date -Is) ==="
}

if [ "$WHICH" = ns ] || [ "$WHICH" = both ]; then
    # V = 63 chars + stop + num_pairs; the grid is 512, 4096, 6144, 8192.
    for N in 448 4032 6080 8128; do build "$N" 20 ns; done
fi
if [ "$WHICH" = s0 ] || [ "$WHICH" = both ]; then
    # sample-0 twins: dictionary from all lines, same stride-0 adjacency.
    for N in 448 4032 8128; do build "$N" 0 s0; done
fi
echo H5_DONE
