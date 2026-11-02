#!/usr/bin/env python3
"""Paired case-normalisation ablation (PLAN D1): score the CamelCase subset.

Normalisation leaves CamelCase identifiers unchanged, so they are *the same
strings* in both corpora.  Scoring just those gives a paired comparison of a
model trained on the normalised corpus vs one trained on the raw corpus, with
the target held fixed.
"""
import sys
import numpy as np
sys.path.insert(0, 'scripts')
import tree_words as tw
import hfactor_words as hf
import cluster_words as cw

KAPPA = 300.0
dirs = {'normalised': sys.argv[1] if len(sys.argv) > 1 else 'work/tw2040',
        'raw': sys.argv[2] if len(sys.argv) > 2 else 'work/tw2040raw'}

raw_val = tw.read_lines('work/raw/merged_validation.txt', stride=20)
camel = [s for s in raw_val
         if any(c.islower() for c in s) and any(c.isupper() for c in s)]
print(f"raw validation (stride 20): {len(raw_val)} ids; "
      f"CamelCase subset {len(camel)} (unchanged by normalisation)")

for name, d in dirs.items():
    M, uni, chars, rules, sym = hf.dense_matrix(d)
    V = M.shape[0]
    nchars = len(chars)
    _, _, M_ref = hf.priors(M, KAPPA * V)
    # tokenisability check: every char must be in the vocabulary
    char_id = {c: i for i, c in enumerate(chars)}
    miss = sorted({c for s in camel for c in s if c not in char_id})
    b = cw.bits_of(M_ref / M_ref.sum(1, keepdims=True), chars, rules,
                   nchars, camel)
    print(f"  {name:11s} {d}: V={V}  full-table {b:.3f} bits "
          f"(missing chars: {miss})")
