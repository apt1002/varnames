#!/usr/bin/env python3
"""C26 close-out: is the shared-assignment margin at 4096/k=64 real?

For each seed, at V=4096:
  * asymmetric(k=32), asymmetric(k=64), shared(k=64, w=1);
  * the frontier fit<=64 interpolated linearly in bytes to the shared model's
    size (18,416 B, between asym(32) 17,400 B and asym(64) 21,488 B);
  * the margin shared - frontier, per seed.
Prints per-seed numbers, then the paired mean +/- SE of the margin and of the
shared-vs-asym64 difference, plus the paired crossing counts at the 64-bit line.
"""
import os
import sys

import numpy as np

sys.path.insert(0, '/home/cod/varnames/scripts')
import tree_words as tw
import hfactor_words as hf
import cluster_words as cw
import model_fit_rates as mfr
from shared_clusters import cluster_shared, model_bytes, score

DIR = 'work/tw4096ns'
KAPPA = 300.0
STRIDE = 40
SEEDS = [int(x) for x in (sys.argv[1] if len(sys.argv) > 1 else '1,2,3,4,5').split(',')]
K = int(sys.argv[2]) if len(sys.argv) > 2 else 64
KLO = K // 2

M, uni, chars, rules, sym = hf.dense_matrix(DIR)
V, nchars = M.shape[0], len(chars)
alpha = KAPPA * V
_, P_mar, M_ref = hf.priors(M, alpha)
del M
lines = tw.read_lines('work/camel/merged_validation.txt', stride=STRIDE)
seqs = mfr.tokenise(lines, chars, rules, nchars)
print(f"{DIR} V={V} n={len(seqs)} kappa={KAPPA} seeds={SEEDS}", flush=True)

b32 = model_bytes(V, KLO, 2)['total']
b64 = model_bytes(V, K, 2)['total']
bsh = model_bytes(V, K, 1)['total']
print(f"bytes: asym{KLO} {b32:.0f}  asym{K} {b64:.0f}  shared{K} {bsh:.0f}", flush=True)

rows = []
for seed in SEEDS:
    out = {}
    for k in (KLO, K):
        rng = np.random.default_rng(seed)
        lcl, _ = cw.cluster_axis(M_ref, k, rng, 0)
        rng = np.random.default_rng(seed + 1)
        rcl, _ = cw.cluster_axis(M_ref, k, rng, 1)
        bits, D, asym = score(M_ref, lcl, rcl, k, seqs)
        out[f'asym{k}'] = (bits.mean(), 100 * (bits <= 64).mean(), bits)
        del lcl, rcl
    rng = np.random.default_rng(seed)
    lab = cluster_shared(M_ref, 1.0, K, rng)
    bits, D, asym = score(M_ref, lab, lab, K, seqs)
    out[f'shared{K}'] = (bits.mean(), 100 * (bits <= 64).mean(), bits)

    f32, f64s = out[f'asym{KLO}'][1], out[f'asym{K}'][1]
    frac = (bsh - b32) / (b64 - b32)
    front = f32 + frac * (f64s - f32)
    margin = out[f'shared{K}'][1] - front
    d_bits = out[f'shared{K}'][0] - out[f'asym{K}'][0]
    crossed = (out[f'shared{K}'][2] <= 64) & ~(out[f'asym{K}'][2] <= 64)
    uncrossed = ~(out[f'shared{K}'][2] <= 64) & (out[f'asym{K}'][2] <= 64)
    print(f"seed {seed}: asym{KLO} {out[f'asym{KLO}'][0]:.3f}/{f32:.1f}%  "
          f"asym{K} {out[f'asym{K}'][0]:.3f}/{f64s:.1f}%  "
          f"shared{K} {out[f'shared{K}'][0]:.3f}/{out[f'shared{K}'][1]:.1f}%  "
          f"frontier {front:.2f}%  margin {margin:+.2f} pt  "
          f"d_bits {d_bits:+.3f}  +{int(crossed.sum())}/-{int(uncrossed.sum())}",
          flush=True)
    rows.append((margin, d_bits, int(crossed.sum()), int(uncrossed.sum())))

m = np.array([r[0] for r in rows])
d = np.array([r[1] for r in rows])
print(f"\nmargin over seeds: mean {m.mean():+.3f} pt, sd {m.std(ddof=1):.3f}, "
      f"paired SE {m.std(ddof=1) / np.sqrt(len(m)):.3f} pt (n={len(m)} seeds)")
print(f"d_bits (shared - asym64): mean {d.mean():+.4f}, "
      f"paired SE {d.std(ddof=1) / np.sqrt(len(d)):.4f} bits/identifier")
print("crossings at the 64-bit line: "
      f"mean +{np.mean([r[2] for r in rows]):.1f} / -{np.mean([r[3] for r in rows]):.1f} "
      "identifiers per run")
