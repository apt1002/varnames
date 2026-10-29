#!/bin/bash
# Sweep the successor-model analyses over all common-substring thresholds.
#
#   run_sweep.sh [CORPUS]
#
# For each threshold T (work/common$T):
#   * successor_distributions  -> successor_distributions.tsv
#   * code_lengths             -> code_lengths.tsv  (64/128-bit fit rates)
#   * pair_matrix              -> pair_stats.txt / pair_factors_L*.npy
# (the latter only for thresholds whose N is small enough to hold the dense
#  N x N matrix in memory; pair_matrix skips the factorisation itself.)
set -u
cd "$(dirname "$0")/.."
CORPUS="${1:-work/camel/merged.txt}"
THRESHOLDS="${THRESHOLDS:-100000 50000 20000 10000 5000 2000 1000 500}"
PAIR_THRESHOLDS="${PAIR_THRESHOLDS:-100000 50000 20000 10000 5000}"

for T in $THRESHOLDS; do
    D="work/common$T"
    S="$D/common_substrings.txt"
    [ -f "$S" ] || { echo "== skip $T (no $S)"; continue; }
    echo "===== threshold $T ($(wc -l < "$S") substrings) ====="
    if [ ! -f "$D/successor_distributions.tsv" ]; then
        echo "--- successor_distributions"
        time python3 scripts/successor_distributions.py "$CORPUS" "$S" --outdir "$D"
    fi
    echo "--- code_lengths"
    time python3 scripts/code_lengths.py "$CORPUS" "$S" --outdir "$D"
done

for T in $PAIR_THRESHOLDS; do
    D="work/common$T"
    S="$D/common_substrings.txt"
    [ -f "$S" ] || continue
    echo "===== pair_matrix $T ====="
    time python3 scripts/pair_matrix.py "$CORPUS" "$S" --outdir "$D" \
         --lsvd 2,4,8,16,32,64
done
echo "===== sweep done ====="
