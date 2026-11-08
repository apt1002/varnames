#!/usr/bin/env python3
"""Visualise the rank-`L` square-root (Hellinger) factorisation as two 3D clouds.

`docs/HELLINGER_FACTORISATION.md` factorises the word x word adjacency matrix as

    sqrt(M_ref)  ~  U Sigma V^T ,     U^T U = V^T V = I ,  Sigma = diag(sigma),

so word `w` gets a **left** coordinate `U[w] * sqrt(sigma)` and a **right**
coordinate `V[w] * sqrt(sigma)`.  This script plots the two clouds (one subplot
each) after projecting the first `--rank` latent dimensions (default 4) down to
3 spatial axes plus a size axis, so you can look at the shape and hunt for
structure worth compressing.

Design (change with the flags):
  * spatial axes  -- default latent dims 2, 3, 4 (scaled by sqrt(sigma));
  * point size    -- default |dim 1| coordinate, since the leading latent
                     dimension roughly tracks probability mass; `--size mass`
                     uses the observed unigram mass instead;
  * point colour  -- log10 observed unigram mass (so rare junk words are visible),
                     or, with `--model` or `--clusters`, the word's cluster;
  * the `--label N` most massive points per cloud are annotated with the word.

Colouring by the cluster is what shows the co-clustering rather than leaving it
to be inferred: pass the packed model (`--model standard/model.nvm1`) to use the
very assignment the build chose, or `--clusters K` to compute one on the spot.
The same label is used in both clouds, so a cluster that is a tight clump in the
left cloud *and* in the right cloud is what a good shared assignment looks
like.

`--divide-unigram` divides each of the three plotted coordinates by the **square
root** of the word's 1-gram probability, stripping the mass/gain trend so the
remaining (angular) structure is visible.

It is self-contained: it needs `numpy`, `matplotlib`, and only the files
`<dir>/adj.npz` and `<dir>/sym.npy` (e.g. copy `work/tw2040/`; ~3.4 MB).

Usage:
    factor_cloud.py --dir work/tw8192ns --model standard/model.nvm1 --no-show
    factor_cloud.py --dir work/tw2040 --clusters 16 --no-show
    factor_cloud.py --dir work/tw2040                 # show and save PNG
    factor_cloud.py --dir work/tw2040 --size mass --save cloud.png
    factor_cloud.py --dir work/tw2040 --axes 1,2,3 --size 4 --no-show
    factor_cloud.py --dir work/tw2040 --divide-unigram --no-show
"""
import argparse
import os
import sys

import numpy as np


def load_model(d, kappa):
    """Load the word x word matrix and return `(M_ref, uni, sym)`."""
    z = np.load(os.path.join(d, 'adj.npz'))
    rows, cols, data = z['rows'], z['cols'], z['data']
    uni = np.asarray(z['uni'], dtype=np.float64)
    V = int(z['nvoc'][0])
    M = np.zeros((V, V), dtype=np.float64)
    M[rows, cols] = data
    sym = [str(x) for x in np.load(os.path.join(d, 'sym.npy'))]
    T = float(M.sum())
    r, c = M.sum(1), M.sum(0)
    P_mar = np.outer(r / T, c / T)
    alpha = kappa * V
    return M + alpha * P_mar, uni, sym


def factorise(M_ref, rank):
    """Rank-`rank` SVD of the elementwise sqrt (Hellinger embedding)."""
    A = np.sqrt(np.maximum(M_ref, 0.0))
    U, s, Vt = np.linalg.svd(A, full_matrices=False)
    L = min(rank, len(s))
    U, s, Vt = U[:, :L], s[:L], Vt[:L]
    left = U * np.sqrt(s)          # V x L
    right = Vt.T * np.sqrt(s)      # V x L
    return left, right, s


def axes_and_size(coords, dims, size_spec, uni, divide_unigram=False):
    xyz = coords[:, [d - 1 for d in dims]].copy()
    if divide_unigram:
        p = uni / max(uni.sum(), 1.0)
        xyz = xyz / np.sqrt(np.maximum(p, 1e-300))[:, None]
    if size_spec == 'mass':
        s = uni
    else:
        s = np.abs(coords[:, int(size_spec) - 1])
    return xyz, s


def model_labels(path, V0):
    """The right-cluster label of every point, from a packed model file.

    The model numbers the words from the first id after the alphabet; the
    adjacency matrix carries the stop token in the middle of its symbol list, so
    the stop is skipped and everything after it shifts down one.  Returns a
    label per adjacency symbol, `-1` for the stop.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'python'))
    import varnames

    model = varnames.Model.from_path(path)
    nchars = model.nchars
    if model.V + 1 != V0:
        sys.exit(f'{path}: V={model.V} does not match the adjacency ({V0 - 1})')
    labels = np.full(V0, -1, dtype=np.int64)
    for i in range(V0):
        if i == nchars:
            continue                      # the stop token
        labels[i] = model.memberships[i if i < nchars else i - 1]
    return labels


def cluster_labels(M_ref, k, seed):
    """The row half of the shared assignment, computed on the spot."""
    import cluster_words as cw

    labels, _centers = cw.cluster_axis(M_ref, k, np.random.default_rng(seed), 0)
    return np.asarray(labels, dtype=np.int64)


def scale(kind, v, lo, hi):
    if kind == 'log':
        v = np.log10(np.maximum(v, 1.0))
    v = v - v.min()
    span = v.max() - v.min()
    if span > 0:
        v = v / span
    return lo + v * (hi - lo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='work/tw2040')
    ap.add_argument('--rank', type=int, default=4)
    ap.add_argument('--kappa', type=float, default=300.0,
                    help='prior mass per row (0 = no prior)')
    ap.add_argument('--axes', default='2,3,4',
                    help='three latent dims (1-based) for x,y,z')
    ap.add_argument('--size', default='1',
                    help="latent dim (1-based) for point size, or 'mass'")
    ap.add_argument('--label', type=int, default=100,
                    help='annotate this many most-massive words per cloud')
    ap.add_argument('--divide-unigram', action='store_true',
                    help='divide the three plotted coordinates by the square '
                         "root of the word's 1-gram probability (to strip the "
                         'mass/gain trend)')
    ap.add_argument('--clip', type=float, default=99.0,
                    help='set axis limits to this percentile range so the bulk '
                         'is visible (100 = show full range)')
    ap.add_argument('--model', metavar='PATH',
                    help='an NVM1 model whose cluster assignment colours the '
                         'points (the assignment the build chose)')
    ap.add_argument('--clusters', type=int, metavar='K',
                    help='colour by a fresh K-means assignment of this size, '
                         'when no model is given')
    ap.add_argument('--seed', type=int, default=1,
                    help='seed for `--clusters`')
    ap.add_argument('--save', default='factor_cloud.png')
    ap.add_argument('--no-show', action='store_true')
    args = ap.parse_args()

    import matplotlib
    if args.no_show:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    M_ref, uni, sym = load_model(args.dir, args.kappa)
    left, right, s = factorise(M_ref, args.rank)
    print(f"{args.dir}: V={M_ref.shape[0]}  top singular values "
          + ", ".join(f"{x:.1f}" for x in s))
    print(f"  sqrt(M_ref) rank-{len(s)} captures "
          f"{100 * (s ** 2).sum() / (np.sqrt(M_ref) ** 2).sum():.2f}% of the "
          f"Frobenius energy")

    dims = [int(x) for x in args.axes.split(',')]
    if len(dims) != 3:
        sys.exit('--axes needs exactly three dims')

    labels = None
    V0 = len(sym)
    if args.model:
        labels = model_labels(args.model, V0)
        print(f"  coloured by {args.model}: "
              f"{len(set(labels[labels >= 0]))} clusters")
    elif args.clusters:
        labels = cluster_labels(M_ref, args.clusters, args.seed)
        print(f"  coloured by {args.clusters} fresh clusters")

    fig = plt.figure(figsize=(13, 6.5))
    clusters = None if labels is None else sorted(set(labels[labels >= 0]))
    cmap = plt.get_cmap('hsv', len(clusters)) if clusters else None
    sc = None
    for i, (name, coords) in enumerate((('left (row) cloud  U*sqrt(sigma)', left),
                                        ('right (col) cloud  V*sqrt(sigma)', right))):
        xyz, size_raw = axes_and_size(coords, dims, args.size, uni,
                                       args.divide_unigram)
        ax = fig.add_subplot(1, 2, i + 1, projection='3d')
        siz = scale('log' if args.size == 'mass' else 'lin', size_raw, 3.0, 90.0)
        if labels is None:
            col = scale('log', uni, 0.0, 1.0)
            sc = ax.scatter(xyz[:, 0], xyz[:, 1], xyz[:, 2], s=siz, c=col,
                            cmap='viridis', alpha=0.6, edgecolors='none')
        else:
            keep = labels >= 0
            sc = ax.scatter(xyz[keep, 0], xyz[keep, 1], xyz[keep, 2],
                            s=siz[keep], c=labels[keep], cmap=cmap,
                            vmin=-0.5, vmax=len(clusters) - 0.5,
                            alpha=0.7, edgecolors='none')
            stop = np.flatnonzero(labels < 0)
            if stop.size:
                ax.scatter(xyz[stop, 0], xyz[stop, 1], xyz[stop, 2],
                           s=120, c='black', marker='x', linewidths=1.5)
            for j, label in enumerate(clusters):      # number each cluster
                idx = labels == label
                c = xyz[idx].mean(axis=0)
                ax.text(c[0], c[1], c[2], str(label), fontsize=9,
                        fontweight='bold', color='black',
                        bbox=dict(boxstyle='round,pad=0.1', fc='white',
                                  ec='none', alpha=0.65))
        # annotate the most massive words
        for w in np.argsort(uni)[::-1][:args.label]:
            nm = sym[w] if len(sym[w]) > 1 else repr(sym[w])
            ax.text(xyz[w, 0], xyz[w, 1], xyz[w, 2], f' {nm}', fontsize=7)
        ax.set_xlabel(f'dim {dims[0]}')
        ax.set_ylabel(f'dim {dims[1]}')
        ax.set_zlabel(f'dim {dims[2]}')
        if args.clip < 100.0:
            lo, hi = (100.0 - args.clip) / 2.0, (100.0 + args.clip) / 2.0
            for setlim, v in zip((ax.set_xlim, ax.set_ylim, ax.set_zlim),
                                 (xyz[:, 0], xyz[:, 1], xyz[:, 2])):
                setlim(np.percentile(v, lo), np.percentile(v, hi))
        ax.set_title(name, fontsize=10)
    if sc is not None and labels is None:
        cb = fig.colorbar(sc, ax=fig.axes, fraction=0.02, pad=0.06)
        cb.set_label('log10 unigram mass')
    size_lbl = 'unigram mass' if args.size == 'mass' else f'|dim {args.size}|'
    colour_lbl = ('cluster' if labels is not None
                  else 'log10 unigram mass')
    fig.suptitle(f"{args.dir}  sqrt(M_ref) rank-{len(s)}   "
                 f"size = {size_lbl} (log-scaled)   colour = {colour_lbl}",
                 fontsize=11)
    if args.save:
        fig.savefig(args.save, dpi=170, bbox_inches='tight')
        print(f"wrote {args.save}")

    # a CSV so the clouds can be re-plotted elsewhere
    out = os.path.splitext(args.save)[0] + '.csv'
    import csv
    with open(out, 'w', newline='', encoding='utf-8') as f:
        wr = csv.writer(f)
        header = ['id', 'word', 'mass']
        if labels is not None:
            header.append('cluster')
        wr.writerow(header
                    + [f'U{d + 1}' for d in range(left.shape[1])]
                    + [f'V{d + 1}' for d in range(right.shape[1])])
        for w in range(len(sym)):
            row = [w, sym[w], f'{uni[w]:.0f}']
            if labels is not None:
                row.append(int(labels[w]))
            wr.writerow(row
                        + [f'{x:.6g}' for x in left[w]]
                        + [f'{x:.6g}' for x in right[w]])
    print(f"wrote {out}")

    if not args.no_show:
        plt.show()


if __name__ == '__main__':
    main()
