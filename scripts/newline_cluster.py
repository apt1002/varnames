#!/usr/bin/env python3
"""Reserve a singleton cluster for the stop token (`docs/NEWLINE_CLUSTER.md`).

The stop token `\\n` is the odd symbol in the vocabulary: `N(\\n)` is the number
of identifiers, its row is the distribution of *first* tokens and its column the
distribution of *last* tokens.  In the Hellinger `k`-means it is also the
heaviest single point (weights are occurrence counts), so it drags a whole cell
towards itself on each side and its exact row/column are then replaced by a cell
average that mixes `\\n` with ordinary words.

This script runs the three-way comparison that separates "the stop is alone"
from "one cell fewer for the words":

    plain(k)       k word clusters per side, `\\n` pooled into a cell
    plain(k-1)     k-1 word clusters per side, `\\n` pooled into a cell
    reserved(k)    k-1 word clusters per side, `\\n` a singleton cell each side

Reports, per configuration:

* **compression** -- held-out mean bits and fit <=64 / <=128, split into the
  boundary transitions (those touching `\\n`) and the interior ones.  The
  boundary share is what a reservation could recover at best;
* **generation** -- sampled identifiers scored on "first token never starts a
  corpus identifier", "last token never ends one", "first character is a
  digit", the exact KL of the model's first/last-token distributions against the
  corpus (no sampling noise), the length distribution, and the real-identifier
  hit rate.

The stop's profile is excluded from the clustering when the reservation is
built (`--profile sub`, the default): clustering `V-1` words on the `V-1`
submatrix is the literal reading of "cluster the non-stop tokens".  `--profile
full` keeps the stop column/row in each word's profile, which isolates "the stop
is alone" from "the stop is excluded from the metric".

Usage:
    newline_cluster.py --dir work/tw512ns --k 16 --kappa 300 --stride 100
"""
import argparse
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw
import hfactor_words as hf
import cluster_words as cw
import model_fit_rates as mfr
import budget64_study as b64

VALID = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def model_from(M_ref, lcl, rcl, k):
    """The stored `(c, D)` of the assoc model for a given labelling."""
    c, D, Cc = mfr.assoc_numbers(M_ref, lcl, rcl, k)
    den = D @ Cc
    return dict(lcl=lcl, rcl=rcl, c=c, D=D, Cc=Cc, den=den, k=k,
                logc=np.log2(np.maximum(c, 1e-300)),
                logD=np.log2(np.maximum(D, 1e-300)),
                logden=np.log2(np.maximum(den, 1e-300)))


def plain_labels(M_ref, k, stop, seed):
    """Cluster all V symbols, stop included (the current pipeline)."""
    rng = np.random.default_rng(seed)
    lcl, _ = cw.cluster_axis(M_ref, k, rng, 0)
    rng = np.random.default_rng(seed + 1)
    rcl, _ = cw.cluster_axis(M_ref, k, rng, 1)
    return lcl, rcl


def reserved_labels(M_ref, k, stop, seed, profile='sub'):
    """Cluster the `V-1` non-stop symbols with `k-1` clusters, then give the
    stop a singleton cell of its own on each side.

    `profile='sub'` clusters on the `(V-1) x (V-1)` submatrix, so the stop's row
    and column are not part of any word's profile; `profile='full'` keeps them
    (rows of `M` for the left axis, columns of `M` for the right)."""
    V = M_ref.shape[0]
    words = np.array([i for i in range(V) if i != stop])
    if profile == 'sub':
        Xl = Xr = M_ref[np.ix_(words, words)]
    else:
        Xl = M_ref[words, :]                    # rows: full successor profile
        Xr = M_ref[:, words]                    # columns: full predecessor one
    rng = np.random.default_rng(seed)
    lw, _ = cw.cluster_axis(Xl, k - 1, rng, 0)
    rng = np.random.default_rng(seed + 1)
    rw, _ = cw.cluster_axis(Xr, k - 1, rng, 1)
    lcl = np.full(V, k - 1, dtype=np.int64)
    rcl = np.full(V, k - 1, dtype=np.int64)
    lcl[words] = lw
    rcl[words] = rw
    return lcl, rcl


def bits_split(seqs, m, stop):
    """Held-out bits per identifier, and the part spent on transitions that
    touch the stop token."""
    lcl, rcl = m['lcl'], m['rcl']
    logc, logD, logden = m['logc'], m['logD'], m['logden']
    out = np.empty(len(seqs))
    bnd = np.empty(len(seqs))
    for j, seq in enumerate(seqs):
        a = np.asarray(seq, dtype=np.int64)
        b = np.roll(a, -1)
        A = lcl[a]
        bits = logden[A] - logc[b] - logD[A, rcl[b]]
        out[j] = bits.sum()
        bnd[j] = bits[(a == stop) | (b == stop)].sum()
    return out, bnd


def boundary_dists(m, M_raw, stop, side):
    """`(corpus, model)` boundary distributions, both normalised over the
    non-stop tokens.  `side='first'` is the distribution of the first token,
    `side='last'` that of the last token."""
    c, D, den, lcl, rcl = m['c'], m['D'], m['den'], m['lcl'], m['rcl']
    if side == 'first':                     # distribution of the first token
        p = M_raw[stop].astype(np.float64)
        q = c * D[lcl[stop], rcl] / max(den[lcl[stop]], 1e-300)
    else:                                   # distribution of the last token
        p = M_raw[:, stop].astype(np.float64)
        q = c[stop] * D[lcl, rcl[stop]] / np.maximum(den[lcl], 1e-300)
    p[stop] = 0.0
    q[stop] = 0.0
    p = p / p.sum()
    q = q / q.sum()
    return p, q


def boundary_kl(m, M_raw, stop, side):
    """Exact KL (bits), corpus || model, of a boundary distribution."""
    p, q = boundary_dists(m, M_raw, stop, side)
    ok = (p > 0) & (q > 0)
    return float(np.sum(p[ok] * np.log2(p[ok] / q[ok])))


def report(name, m, seqs, M_raw, nchars, sym, args, rng, corpus):
    stop = nchars
    bits, bnd = bits_split(seqs, m, stop)
    print(f"\n=== {name} (k={m['k']}) ===")
    print(f"held-out mean {bits.mean():.3f} bits  "
          f"fit<=64 {100 * (bits <= 64).mean():.1f}%  "
          f"fit<=128 {100 * (bits <= 128).mean():.1f}%")
    print(f"  of which boundary transitions {bnd.mean():.3f} bits "
          f"({100 * bnd.mean() / bits.mean():.1f}%), "
          f"interior {bits.mean() - bnd.mean():.3f}")

    # ---- generation -----------------------------------------------------
    gen = b64.sample(m, stop, args.samples, rng)
    gstr = [''.join(sym[t] for t in seq) for seq in gen]
    glen = np.array([len(s) for s in gstr])
    starts = np.flatnonzero(M_raw[stop] > 0)
    ends = np.flatnonzero(M_raw[:, stop] > 0)
    first = np.array([seq[0] if seq else -1 for seq in gen])
    last = np.array([seq[-1] if seq else -1 for seq in gen])
    start_mid = np.mean([f not in set(starts.tolist()) for f in first])
    end_mid = np.mean([l not in set(ends.tolist()) for l in last])
    digit = np.mean([bool(s) and s[0].isdigit() for s in gstr])
    clen = np.array([len(s) for s in seqs])
    print(f"generation ({args.samples} samples):")
    print(f"  starts mid-word {100 * start_mid:5.1f}%   "
          f"ends mid-word {100 * end_mid:5.1f}%   "
          f"first char digit {100 * digit:5.1f}%")
    print(f"  first-token KL {boundary_kl(m, M_raw, stop, 'first'):.4f} bits, "
          f"last-token KL {boundary_kl(m, M_raw, stop, 'last'):.4f} bits")
    for side, label in (('first', 'first'), ('last', 'last')):
        p, q = boundary_dists(m, M_raw, stop, side)
        dig = np.array([len(w) == 1 and w.isdigit() for w in sym])
        over = np.argsort(-(q / np.maximum(p, 1e-12)))[:4]
        detail = ", ".join(f"{sym[t]!r} {100 * q[t]:.2f}%/{100 * p[t]:.2f}%"
                           for t in over if p[t] > 0)
        print(f"  {label}-token: digit mass model {100 * q[dig].sum():.2f}% "
              f"vs corpus {100 * p[dig].sum():.2f}%;   over-produced "
              f"(model/corpus): {detail}")
    print(f"  length mean {glen.mean():.2f} (corpus {clen.mean():.2f}), "
          f"95th pct {np.percentile(glen, 95):.0f} "
          f"(corpus {np.percentile(clen, 95):.0f})")
    valid = np.mean([bool(VALID.match(s)) for s in gstr])
    real = np.mean([s in corpus for s in gstr])
    print(f"  syntactically valid {100 * valid:.1f}%, "
          f"real identifier hit rate {100 * real:.2f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--k', type=int, default=16)
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--validation', default='work/camel/merged_validation.txt')
    ap.add_argument('--stride', type=int, default=100)
    ap.add_argument('--samples', type=int, default=5000)
    ap.add_argument('--profile', choices=('sub', 'full'), default='sub')
    ap.add_argument('--seed', type=int, default=1)
    args = ap.parse_args()

    M, uni, chars, rules, sym = hf.dense_matrix(args.dir)
    V, nchars = M.shape[0], len(chars)
    stop = nchars
    M_raw = M.copy()
    alpha = args.kappa * V
    _, P_mar, M_ref = hf.priors(M, alpha)
    lines = tw.read_lines(args.validation, stride=args.stride)
    seqs = mfr.tokenise(lines, chars, rules, nchars)
    corpus = set(tw.read_lines(args.validation))
    print(f"{args.dir}: V={V}, k={args.k}, kappa={args.kappa}, "
          f"held-out n={len(seqs)}, profile={args.profile}")
    print(f"corpus boundary check: {len(np.flatnonzero(M_raw[stop] > 0))} "
          f"tokens ever start, {len(np.flatnonzero(M_raw[:, stop] > 0))} "
          f"ever end; corpus mean length {np.mean([len(s) for s in seqs]):.2f} "
          f"tokens")

    configs = [('plain(k)', plain_labels(M_ref, args.k, stop, args.seed)),
               ('plain(k-1)', plain_labels(M_ref, args.k - 1, stop, args.seed)),
               ('reserved(k)', reserved_labels(M_ref, args.k, stop, args.seed,
                                               args.profile))]
    for name, (lcl, rcl) in configs:
        k = int(max(lcl.max(), rcl.max())) + 1
        m = model_from(M_ref, lcl, rcl, k)
        rng = np.random.default_rng(args.seed + 7)
        report(name, m, seqs, M_raw, nchars, sym, args, rng, corpus)

    print("\nmodel bytes: identical in the three configurations "
          "(k*k pair table + 2V word numbers), so the comparison is free.")


if __name__ == '__main__':
    main()
