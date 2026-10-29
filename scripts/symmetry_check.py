#!/usr/bin/env python3
"""Symmetry sanity check: reversal of the corpus must transpose the roles of
the left context (longest common suffix of the left half) and the right
context (longest common prefix of the right half).

Let phi be "reverse the string and swap ^ <-> $".  phi is a count-preserving
bijection from the substrings of ^id$ to the substrings of ^rev(id)$ and maps
wrap(id) -> wrap(rev(id)).  Therefore, for M built on C and M^R built on
rev(C),

    M^R[phi(b), phi(a)] == M[a, b]      for all a, b.

Everything on the row side is then the mirror image of the column side:
r^R = phi(c), u1^R = phi(v1), so cos(u1, r) on rev(C) equals cos(v1, c) on C.

This script builds both matrices, aligns them through phi and reports the
discrepancy, so a directional bug in the left/right handling would show up as
a large non-zero residual.

Usage: symmetry_check.py CORPUS SUBS REVCORPUS SUBSTR
    e.g. symmetry_check.py work/camel/merged.txt \
             work/common10000/common_substrings.txt \
             work/rev/merged_rev.txt \
             work/rev/common10000/common_substrings.txt
"""
import sys

import numpy as np

sys.path.insert(0, 'scripts')
import pair_matrix


def phi_vocab(vocab):
    """phi on a vocabulary of byte strings: reverse, swapping ^ and $."""
    out = []
    for s in vocab:
        t = bytes(reversed(s))
        t = t.replace(b'^', b'\x00').replace(b'$', b'^').replace(b'\x00', b'$')
        out.append(t)
    return out


def main():
    corpus, subs, revcorpus, subsR = (sys.argv[1], sys.argv[2],
                                      sys.argv[3], sys.argv[4])
    M, vocab, _ = pair_matrix.build_matrix(corpus, subs)
    MR, vocabR, _ = pair_matrix.build_matrix(revcorpus, subsR)
    print(f"M  N={len(vocab)}  M^R N={len(vocabR)}")

    phiv = phi_vocab(vocab)
    idxR = {s: i for i, s in enumerate(vocabR)}
    missing = [s for s in phiv if s not in idxR]
    print(f"phi(V) not in V^R: {len(missing)} of {len(phiv)}")
    if missing:
        print("  examples:", [m.decode('latin1') for m in missing[:8]])

    # align: M^R[phi(b), phi(a)] should equal M[a, b].
    # Take the a, b for which both phi(a), phi(b) exist in V^R.
    keep = [i for i, s in enumerate(phiv) if s in idxR]
    p = np.array([idxR[phiv[i]] for i in keep])          # phi on retained idx
    sub = M[np.ix_(keep, keep)].astype(np.float64)
    subm = MR[np.ix_(p, p)].astype(np.float64)
    # subm[i,j] = M^R[phi(a_i), phi(a_j)]; predicted = M^T[i,j] = M[a_j, a_i]
    resid = subm - sub.T
    denom = np.abs(sub.T).sum()
    print(f"retained {len(keep)} / {len(vocab)} contexts")
    print(f"||M^R[phi(b),phi(a)] - M[a,b]||_F / ||M||_F = "
          f"{np.linalg.norm(resid) / max(np.linalg.norm(M), 1):.3e}")
    print(f"max abs discrepancy: {np.abs(resid).max():.0f}  "
          f"(max count {M.max():.0f})")

    # marginal relation r^R = phi(c)
    r = M.sum(1).astype(np.float64)
    c = M.sum(0).astype(np.float64)
    rR = MR.sum(1).astype(np.float64)
    phi_c = np.array([c[i] for i in keep])
    print(f"max |r^R[phi(b)] - c[b]| = {np.abs(rR[p] - phi_c).max():.0f}")


if __name__ == '__main__':
    main()
