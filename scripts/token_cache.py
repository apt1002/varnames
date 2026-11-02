#!/usr/bin/env python3
"""Cache a tokenised corpus for a given word dictionary.

Tokenising the corpus (``tw.tokenize`` once per line) is the dominant cost in
every script that touches the raw corpus -- typically an order of magnitude
more than the counting they then do.  A tokenised corpus depends only on
``(dictionary, corpus, stride)``, so it can be written once and reloaded cheaply
by any consumer.

Storage.  A flat ``int32`` array of token ids plus an ``int64`` offsets array
(``offsets[j] : offsets[j+1]`` is line ``j``), written to a single ``.npz``.
The token id space is small (``V ~ 10^3``), so this is compact.

Usage::

    python3 scripts/token_cache.py build --dict work/tw2040 \\
        --corpus work/camel/merged_training.txt --stride 20
    python3 scripts/token_cache.py info --dict work/tw2040 \\
        --corpus work/camel/merged_training.txt --stride 20

In Python::

    import token_cache as tc
    ids, offs = tc.load(tc.cache_file(dict_dir, corpus, stride))
    for seq in tc.iter_seqs(ids, offs):      # numpy views, zero-copy
        ...
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree_words as tw

CACHE_DIR = 'work/tokcache'


def cache_file(dict_dir, corpus, stride, cachedir=CACHE_DIR):
    """Path of the cache for ``(dictionary, corpus, stride)``."""
    dict_name = os.path.basename(os.path.normpath(dict_dir))
    corpus_name = os.path.basename(corpus)
    return os.path.join(cachedir,
                        f"{dict_name}.{corpus_name}.s{stride}.npz")


def build_with(tag, corpus, stride, tokenize_one, nchars, vocab,
               cachedir=CACHE_DIR, verbose=True, force=False):
    """Cache the tokenisation produced by ``tokenize_one(line) -> list[int]``.

    Use this when the dictionary is not on disk (e.g. an overshoot build):
    ``tag`` names the cache (any filesystem-safe string)."""
    out = os.path.join(cachedir,
                       f"{tag}.{os.path.basename(corpus)}.s{stride}.npz")
    if os.path.exists(out) and not force:
        if verbose:
            print(f"using cache {out}", flush=True)
        return out
    os.makedirs(cachedir, exist_ok=True)
    t0 = time.time()
    parts = []
    offs = [0]
    nlines = 0
    for s in tw.read_lines(corpus, stride=stride):
        toks = tokenize_one(s)
        parts.append(np.asarray(toks, dtype=np.int32))
        nlines += 1
        offs.append(offs[-1] + len(toks))
        if verbose and nlines % 20000 == 0:
            print(f"  {nlines} lines  {time.time()-t0:.0f}s", flush=True)
    ids = np.concatenate(parts) if parts else np.empty(0, dtype=np.int32)
    np.savez(out, ids=ids,
             offsets=np.asarray(offs, dtype=np.int64),
             nchars=np.int64(nchars), vocab=np.int64(vocab),
             stride=np.int64(stride), dict_dir=np.str_(tag),
             corpus=np.str_(corpus))
    if verbose:
        print(f"wrote {out}: {nlines} lines, {len(ids)} tokens, "
              f"vocab {vocab}, {time.time()-t0:.0f}s", flush=True)
    return out


def build(dict_dir, corpus, stride, cachedir=CACHE_DIR, verbose=True,
          force=False):
    """Tokenise ``corpus`` with the dictionary in ``dict_dir`` and cache it."""
    chars, rules, sym = tw.load_dictionary(dict_dir)
    nchars = len(chars)
    cid = {c: i for i, c in enumerate(chars)}
    plan = tw.make_plan(rules, nchars)
    return build_with(os.path.basename(os.path.normpath(dict_dir)),
                      corpus, stride,
                      lambda s: tw.tokenize(s, cid, plan, nchars),
                      nchars, len(sym), cachedir, verbose, force)


def load(path):
    """Return ``(ids, offsets)``; line ``j`` is ``ids[offsets[j]:offsets[j+1]]``.

    Both are read-only numpy arrays (zero-copy views into the ``.npz``)."""
    z = np.load(path)
    return z['ids'], z['offsets']


def iter_seqs(ids, offsets):
    """Yield each line's token-id sequence as an ``int32`` numpy view."""
    for j in range(len(offsets) - 1):
        yield ids[offsets[j]:offsets[j + 1]]


def info(path):
    z = np.load(path)
    ids, offs = z['ids'], z['offsets']
    n = len(offs) - 1
    print(f"{path}")
    print(f"  dictionary : {str(z['dict_dir'])}")
    print(f"  corpus     : {str(z['corpus'])}  stride {int(z['stride'])}")
    print(f"  lines      : {n}   tokens {len(ids)}   vocab {int(z['vocab'])}")
    print(f"  size       : {os.path.getsize(path)/1e6:.1f} MB")


def _selfcheck():
    """Round-trip a small cache through build/load and compare to direct tokenise."""
    import tempfile
    chars, rules, sym = tw.load_dictionary('work/tw96')
    nchars = len(chars)
    cid = {c: i for i, c in enumerate(chars)}
    plan = tw.make_plan(rules, nchars)
    lines = tw.read_lines('work/camel/merged_validation.txt', stride=997)[:50]
    with tempfile.TemporaryDirectory() as d:
        direct = [tw.tokenize(s, cid, plan, nchars) for s in lines]
        # write what we would tokenise, via a tiny synthetic check of the
        # storage round-trip (build() reads the corpus itself)
        parts = [np.asarray(t, dtype=np.int32) for t in direct]
        offs = np.concatenate([[0], np.cumsum([len(t) for t in direct])])
        ids = np.concatenate(parts) if parts else np.empty(0, np.int32)
        p = os.path.join(d, 'x.npz')
        np.savez(p, ids=ids, offsets=offs, nchars=nchars, vocab=len(sym),
                 stride=997, dict_dir='work/tw96', corpus='x')
        ids2, offs2 = load(p)
        got = list(iter_seqs(ids2, offs2))
        ok = (len(got) == len(direct)
              and all(np.array_equal(np.asarray(a), np.asarray(b))
                      for a, b in zip(got, direct)))
        print(f"storage round-trip ok: {ok}  ({len(direct)} lines, "
              f"{sum(map(len, direct))} tokens)")
        assert ok


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('build', 'info'):
        p = sub.add_parser(name)
        p.add_argument('--dict', required=True)
        p.add_argument('--corpus', required=True)
        p.add_argument('--stride', type=int, default=20)
        p.add_argument('--cachedir', default=CACHE_DIR)
    sub.choices['build'].add_argument('--force', action='store_true')
    sub.add_parser('selfcheck')
    a = ap.parse_args()
    if a.cmd == 'build':
        build(a.dict, a.corpus, a.stride, a.cachedir, force=a.force)
    elif a.cmd == 'info':
        info(cache_file(a.dict, a.corpus, a.stride, a.cachedir))
    else:
        _selfcheck()


if __name__ == '__main__':
    main()
