#!/usr/bin/env python3
"""How much is the identifier-boundary trigram ``(u, v, \\n)`` worth?

The run-aware word dictionary (`docs/TREE_WORDS.md`)
never merges across the string boundary, so a tokenised identifier ends
``… u v \\n`` and the model codes the boundary with the two *bigrams*
``P(v|u)`` and ``P(\\n|v)``.  Allowing a word ``v\\n`` would instead code it
with ``P(v\\n|u) = P(v|u)·P(\\n|u,v)``, i.e. it would capture the trigram
``P(\\n | u, v)`` that says whether ``v`` is final *given* ``u``.

The bits on the table are therefore the uncaptured conditional mutual
information, summed over boundaries:

    gain = sum_{u,v} N(u,v,\\n) · log2[ P(\\n|u,v) / P(\\n|v) ]
         = sum_{u,v} N(u,v,\\n) · log2[ N(u,v,\\n)·N(v) / (N(u,v)·N(v,\\n)) ] .

This script estimates it two ways:

* **in-sample** -- plug-in on the whole corpus (optimistic upper estimate);
* **held-out** -- trigram counted on a train half, code length measured on a
  disjoint test half, backing off to ``P(\\n|v)`` when ``(u,v,\\n)`` is unseen
  (the "unobserved data" wrinkle).

Both are compared to the corpus size ``CS = S1 - S2`` in bits.

Usage:
    python3 scripts/boundary_trigram.py --dirs work/tw512 work/tw2040
    python3 scripts/boundary_trigram.py --dirs work/tw2040 --stride 20 --jobs 4
"""
import argparse
import json
import math
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw

LOG2 = math.log(2.0)
_W = {}


def L(z):
    return 0.0 if z <= 0 else z * math.log2(z)


def reader(path, stride):
    with open(path, 'r', encoding='ascii') as f:
        for i, line in enumerate(f):
            if stride > 1 and i % stride:
                continue
            s = line.rstrip('\n')
            if s:
                yield s


def _init(dirpath, half):
    chars, rules, sym = tw.load_dictionary(dirpath)
    _W['nchars'] = len(chars)
    _W['cid'] = {c: i for i, c in enumerate(chars)}
    _W['plan'] = tw.make_plan(rules, len(chars))
    _W['half'] = half


def _count_chunk(arg):
    start, lows = arg
    nchars = _W['nchars']; cid = _W['cid']; plan = _W['plan']; half = _W['half']
    nstop = nchars
    C = Counter(); Ctr = Counter(); Cte = Counter()
    Nv = Counter(); Nuv = Counter()
    Nv_tr = Counter(); Nuv_tr = Counter()
    for k, s in enumerate(lows):
        i = start + k
        toks = tw.tokenize(s, cid, plan, nchars)
        if len(toks) >= 2:
            C[(toks[-2], toks[-1])] += 1
        seq = toks + [nstop]; m = len(seq)
        for j in range(m):
            Nv[seq[j]] += 1
            Nuv[(seq[j], seq[(j + 1) % m])] += 1
        if i < half:
            if len(toks) >= 2:
                Ctr[(toks[-2], toks[-1])] += 1
            for j in range(m):
                Nv_tr[seq[j]] += 1
                Nuv_tr[(seq[j], seq[(j + 1) % m])] += 1
        elif len(toks) >= 2:
            Cte[(toks[-2], toks[-1])] += 1
    return start, C, Nv, Nuv, Ctr, Cte, Nv_tr, Nuv_tr


def collect(dirpath, corpus, stride, jobs, split, chunksize):
    chars, rules, sym = tw.load_dictionary(dirpath)
    nchars = len(chars)
    nvoc = len(sym)
    nstop = nchars
    print(f"\n=== {dirpath}   V={nvoc}", flush=True)

    nklines = sum(1 for _ in reader(corpus, stride))
    half = int(nklines * split)
    print(f"  {corpus} stride {stride}: {nklines} lines "
          f"(train {half}, test {nklines-half})", flush=True)

    t0 = time.time()
    C = Counter(); Ctr = Counter(); Cte = Counter()
    Nv = Counter(); Nuv = Counter()
    Nv_tr = Counter(); Nuv_tr = Counter()
    if jobs > 1:
        import multiprocessing as mp
        def gen():
            buf = []; start = 0; i = 0
            for s in reader(corpus, stride):
                if not buf:
                    start = i
                buf.append(s)
                if len(buf) >= chunksize:
                    yield (start, buf); buf = []
                i += 1
            if buf:
                yield (start, buf)
        with mp.Pool(jobs, initializer=_init, initargs=(dirpath, half)) as pool:
            done = 0
            for (start, c, nv, nuv, ctr, cte, nv_tr, nuv_tr) in \
                    pool.imap_unordered(_count_chunk, gen()):
                C.update(c); Nv.update(nv); Nuv.update(nuv)
                Ctr.update(ctr); Cte.update(cte)
                Nv_tr.update(nv_tr); Nuv_tr.update(nuv_tr)
                done += 1
                if done % 20 == 0:
                    print(f"    {done} chunks  {time.time()-t0:.0f}s", flush=True)
    else:
        _init(dirpath, half); i = 0
        for s in reader(corpus, stride):
            _, c, nv, nuv, ctr, cte, nv_tr, nuv_tr = _count_chunk((i, [s]))
            C.update(c); Nv.update(nv); Nuv.update(nuv)
            Ctr.update(ctr); Cte.update(cte)
            Nv_tr.update(nv_tr); Nuv_tr.update(nuv_tr)
            i += 1
            if i % 500000 == 0:
                print(f"    pass {i}/{nklines}  {time.time()-t0:.0f}s", flush=True)
    print(f"  tokenised in {time.time()-t0:.0f}s", flush=True)

    nstr = Nv[nstop]
    CS = sum(L(float(x)) for x in Nv.values()) - sum(L(v) for v in Nuv.values())
    print(f"  CS={CS:.1f} bits ({CS/nstr:.3f} bits/string)  N(\\n)={nstr}", flush=True)

    gain = 0.0; tot = 0
    for (u, v), c in C.items():
        Nuv_c = Nuv.get((u, v), 0.0); Nvn = Nuv.get((v, nstop), 0.0)
        Nv_c = float(Nv[v])
        if Nuv_c <= 0 or Nvn <= 0 or Nv_c <= 0:
            continue
        gain += c * math.log(c * Nv_c / (Nuv_c * Nvn)); tot += c
    g = gain / LOG2
    print(f"  IN-SAMPLE : {tot} triples, gain {g:.1f} bits "
          f"= {g/nstr:.4f} b/string = {g/CS*100:.3f}% of CS", flush=True)

    n = 0; bb = tb = 0.0; used = 0
    for (u, v), c in Cte.items():
        Nv = Nv_tr[v]; Nvn = Nuv_tr.get((v, nstop), 0)
        if Nv <= 0 or Nvn <= 0:
            continue
        p_big = Nvn / Nv
        n += c; bb += c * -math.log2(p_big)
        Nuvv = Ctr.get((u, v), 0); Nuv = Nuv_tr.get((u, v), 0)
        if Nuvv > 0 and Nuv > 0:
            p_tri = Nuvv / Nuv; used += c
        else:
            p_tri = p_big
        tb += c * -math.log2(p_tri)
    save = bb - tb
    print(f"  HELD-OUT  : {n} test strings, bigram {bb:.1f} vs trigram+backoff "
          f"{tb:.1f} -> save {save:.1f} bits = {save/n:.4f} b/string "
          f"({used/n*100:.1f}% used the trigram)", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dirs', nargs='+', required=True,
                    help='dictionary directories (e.g. work/tw2040)')
    ap.add_argument('--corpus', default=None, help='override the meta.json corpus')
    ap.add_argument('--stride', type=int, default=1,
                    help='keep every k-th line (1 = all)')
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--split', type=float, default=0.5, help='train fraction')
    ap.add_argument('--chunksize', type=int, default=20000,
                    help='lines per chunk when --jobs > 1')
    args = ap.parse_args()
    for d in args.dirs:
        corpus = args.corpus or json.load(open(d + '/meta.json'))['corpus']
        collect(d, corpus, args.stride, args.jobs, args.split, args.chunksize)


if __name__ == '__main__':
    main()
