#!/usr/bin/env python3
"""Word-level (pair-merge) model for `docs/TREE_WORDS.md`.

Builds the dictionary by the greedy pair-merge rule of TREE_WORDS.md, tokenises
a corpus with it (a *dictionary split*: only word boundaries matter, the
characters inside a word are not looked at), and counts the word x word
adjacency of the tokenised, cyclic corpus.

Dictionary.  Start with the set of words = the single characters.  Repeat
`NUM_PAIRS` times: find the most common length-2 substring `uv` of *words* in
the corpus, add `(uv)` as a word, and replace every occurrence of `uv`.
Occurrences inside brackets are not looked at, i.e. this is ordinary BPE.  The
stop character `\\n` is a separator, not a word: it is never merged across (a
word spanning two identifiers would be meaningless).

Tokenising.  Replay the wordlist in creation order, replacing each occurrence in
turn; equivalently, merge the lowest-ranked adjacent pair until no rule applies.

Counts.  After tokenising an identifier the cyclic sequence is `tokens + [\\n]`;
the adjacency matrix counts its cyclic word bigrams.  Hence `N(\\n) =` number of
strings and `sum_v N(u,v) = N(u)` for every word `u`, the identity the
`CS = S1 - S2` derivation relies on.

Symbol ids: `0..len(chars)-1` are the characters, `len(chars)` is the stop
`\\n`, and `len(chars)+1+r` is the word created by merge `r`.

Usage:
    tree_words.py train --corpus work/camel/merged_training.txt \\
        --num-pairs 256 --sample 100000 --outdir work/tw256
    tree_words.py stats --dir work/tw256 --corpus work/camel/merged_validation.txt
"""
import argparse
import heapq
import json
import os
from collections import Counter

import numpy as np

STOP = '\n'
STOP_LABEL = '\\n'


def read_lines(path, stride=0, limit=0):
    """Read one identifier per line.  `stride` = keep every k-th line (spread
    across the sorted corpus); 0 = all.  `limit` caps the number of lines."""
    lines = []
    with open(path, 'r', encoding='ascii') as f:
        for i, line in enumerate(f):
            if stride and i % stride:
                continue
            s = line.rstrip('\n')
            if s:
                lines.append(s)
                if limit and len(lines) >= limit:
                    break
    return lines


def build_dictionary(lines, num_pairs, verbose=False):
    """Greedy pair-merge (BPE).  Returns (chars, wordlist, sym)."""
    chars = sorted(set(''.join(lines)))
    cid = {c: i for i, c in enumerate(chars)}
    sym = list(chars) + [STOP]
    seqs = [[cid[c] for c in s] for s in lines]

    cnt = Counter()
    pos = {}

    def decr(si, p, j):
        s = pos.get(p)
        if s is not None and (si, j) in s:
            s.discard((si, j))
            cnt[p] -= 1

    for si, seq in enumerate(seqs):
        for j in range(len(seq) - 1):
            p = (seq[j], seq[j + 1])
            pos.setdefault(p, set()).add((si, j))
            cnt[p] += 1

    heap = [(-c, p) for p, c in cnt.items() if c > 1]
    heapq.heapify(heap)

    def incr(si, p, j):
        s = pos.setdefault(p, set())
        if (si, j) not in s:
            s.add((si, j))
            cnt[p] += 1
            heapq.heappush(heap, (-cnt[p], p))

    def rebuild():
        return [(-c, p) for p, c in cnt.items() if c > 1]

    wordlist = []
    next_id = len(chars) + 1
    for step in range(num_pairs):
        while heap:
            neg, p = heapq.heappop(heap)
            if cnt.get(p, 0) == -neg and -neg > 1:
                break
        else:
            break
        a, b = p
        positions = list(pos.pop(p, ()))
        new = next_id
        next_id += 1
        sym.append(sym[a] + sym[b])
        wordlist.append((a, b))
        for si, i in positions:
            s = seqs[si]
            if i + 1 >= len(s) or s[i] is None or s[i + 1] is None:
                continue
            if s[i] != a or s[i + 1] != b:
                continue
            left = s[i - 1] if i - 1 >= 0 else None
            right = s[i + 2] if i + 2 < len(s) else None
            decr(si, (a, b), i)
            if left is not None:
                decr(si, (left, a), i - 1)
            if right is not None:
                decr(si, (b, right), i + 1)
            s[i] = new
            s[i + 1] = None
            if left is not None:
                incr(si, (left, new), i - 1)
            if right is not None:
                incr(si, (new, right), i)
        if len(heap) > 4 * len(cnt) + 4096:
            heap = rebuild()
            heapq.heapify(heap)
        if verbose and (step + 1) % 500 == 0:
            print(f"  merge {step + 1}/{num_pairs} {sym[new]!r} "
                  f"(cnt {(-neg)}) vocab {len(sym)}", flush=True)
    return chars, wordlist, sym


def save_dictionary(outdir, chars, wordlist, sym):
    with open(os.path.join(outdir, 'dict.txt'), 'w', encoding='ascii') as f:
        f.write('\t'.join(c if c != STOP else STOP_LABEL for c in chars) + '\n')
        for a, b in wordlist:
            f.write(f"{a}\t{b}\n")
    np.save(os.path.join(outdir, 'sym.npy'), np.array(
        [w if w != STOP else STOP_LABEL for w in sym]))


def load_dictionary(outdir):
    sym = [str(x) for x in np.load(os.path.join(outdir, 'sym.npy'))]
    chars = [s for s in sym if len(s) == 1 and s != STOP_LABEL]
    wordlist = []
    with open(os.path.join(outdir, 'dict.txt'), 'r', encoding='ascii') as f:
        next(f)                                   # the charset line
        for line in f:
            a, b = line.rstrip('\n').split('\t')
            wordlist.append((int(a), int(b)))
    return chars, wordlist, sym


def make_rank(wordlist, nchars):
    """rank[(a,b)] = creation order; merged symbol id = nchars+1+rank."""
    return {p: r for r, p in enumerate(wordlist)}


def tokenize(s, char_id, rank, nchars):
    """Merge the lowest-ranked adjacent pair until no rule applies.

    Equivalent to replaying the wordlist in creation order ("for each `uv`, in
    turn, replace every occurrence") and, because a newly created pair always
    has a higher rank than the rule that made it, equivalent to repeatedly
    merging the *lowest-ranked* adjacent pair.  A doubly linked list over the
    tokens avoids index shifting when a pair is merged.
    """
    ids = [char_id[c] for c in s]
    n = len(ids)
    nxt = list(range(1, n + 1))          # n is a sentinel past the end
    prv = list(range(-1, n - 1))
    dead = [False] * n
    h = []

    def push(i):
        if 0 <= i < n and not dead[i]:
            j = nxt[i]
            if j < n and not dead[j]:
                r = rank.get((ids[i], ids[j]))
                if r is not None:
                    heapq.heappush(h, (r, i))

    for i in range(n):
        push(i)
    while h:
        r, i = heapq.heappop(h)
        if dead[i]:
            continue
        j = nxt[i]
        if j >= n or dead[j] or rank.get((ids[i], ids[j])) != r:
            continue
        ids[i] = nchars + 1 + r
        dead[j] = True
        nxt[i] = nxt[j]
        if nxt[j] < n:
            prv[nxt[j]] = i
        push(prv[i])
        push(i)
    out = []
    i = 0 if n else n
    while i < n:
        out.append(ids[i])
        i = nxt[i]
    return out


def count_adjacency(lines, chars, wordlist, sym):
    """Count cyclic word bigrams and unigrams over `lines`."""
    nchars = len(chars)
    char_id = {c: i for i, c in enumerate(chars)}
    rank = make_rank(wordlist, nchars)
    stop = nchars
    big = Counter()
    uni = Counter()
    for s in lines:
        toks = tokenize(s, char_id, rank, nchars)
        seq = toks + [stop]
        n = len(seq)
        for i in range(n):
            uni[seq[i]] += 1
            big[(seq[i], seq[(i + 1) % n])] += 1
    return big, uni


_W = {}


def _init_worker(char_id, rank, nchars):
    _W['char_id'] = char_id
    _W['rank'] = rank
    _W['nchars'] = nchars


def _count_chunk(lines):
    char_id, rank, nchars = _W['char_id'], _W['rank'], _W['nchars']
    stop = nchars
    big = Counter()
    uni = Counter()
    for s in lines:
        toks = tokenize(s, char_id, rank, nchars)
        seq = toks + [stop]
        n = len(seq)
        for i in range(n):
            uni[seq[i]] += 1
            big[(seq[i], seq[(i + 1) % n])] += 1
    return big, uni


def count_adjacency_parallel(lines, chars, wordlist, sym, jobs=1, chunksize=2000):
    if jobs <= 1:
        return count_adjacency(lines, chars, wordlist, sym)
    import multiprocessing as mp
    nchars = len(chars)
    char_id = {c: i for i, c in enumerate(chars)}
    rank = make_rank(wordlist, nchars)
    big = Counter()
    uni = Counter()
    chunks = [lines[i:i + chunksize] for i in range(0, len(lines), chunksize)]
    with mp.Pool(jobs, initializer=_init_worker,
                 initargs=(char_id, rank, nchars)) as pool:
        for b, u in pool.imap_unordered(_count_chunk, chunks):
            big.update(b)
            uni.update(u)
    return big, uni


def write_adj(outdir, big, uni, sym, name='adj'):
    rows = np.fromiter((k[0] for k in big), dtype=np.int64, count=len(big))
    cols = np.fromiter((k[1] for k in big), dtype=np.int64, count=len(big))
    data = np.fromiter(big.values(), dtype=np.float64, count=len(big))
    nvoc = len(sym)
    uni_arr = np.zeros(nvoc, dtype=np.int64)
    for k, v in uni.items():
        uni_arr[k] = v
    np.savez_compressed(os.path.join(outdir, name + '.npz'),
                        rows=rows, cols=cols, data=data, uni=uni_arr,
                        nvoc=np.array([nvoc]))


def cmd_train(args):
    outdir = args.outdir or f'work/tw{args.num_pairs}'
    os.makedirs(outdir, exist_ok=True)
    build = read_lines(args.corpus, stride=args.sample)
    print(f"dictionary corpus {args.corpus}: {len(build)} lines "
          f"(stride {args.sample or 1})", flush=True)
    chars, wordlist, sym = build_dictionary(build, args.num_pairs, verbose=True)
    print(f"dictionary: {len(wordlist)} merges, vocab {len(sym)}", flush=True)
    save_dictionary(outdir, chars, wordlist, sym)
    with open(os.path.join(outdir, 'meta.json'), 'w') as f:
        json.dump(dict(corpus=args.corpus, num_pairs=args.num_pairs,
                       sample=args.sample, nlines=len(build)), f)

    full = read_lines(args.corpus, stride=0)
    print(f"tokenising {len(full)} lines", flush=True)
    big, uni = count_adjacency_parallel(full, chars, wordlist, sym,
                                        jobs=args.jobs)
    write_adj(outdir, big, uni, sym)
    print(f"adjacency: {len(big)} distinct bigrams, "
          f"N={sum(uni.values())}, N(stop)={uni[len(chars)]}", flush=True)
    print(f"wrote {outdir}/adj.npz", flush=True)


def load_adj(outdir):
    z = np.load(os.path.join(outdir, 'adj.npz'))
    big = {(int(r), int(c)): float(d)
           for r, c, d in zip(z['rows'], z['cols'], z['data'])}
    uni = z['uni']
    return big, uni, int(z['nvoc'][0])


def reference_probabilities(big, uni, kappa=1000.0):
    """Return (num, den) with P_ref(b|a) = num[(a,b)] / den[a].

    The counting prior of `docs/ADJACENCY_MATRIX.md`:  M_ref = M + alpha*P_mar,
    P_mar = (r/T)(c/T)^T, alpha = kappa*V.  For the cyclic word bigram matrix
    r = c = uni, T = N.
    """
    T = float(uni.sum())
    V = len(uni)
    alpha = kappa * V
    den = uni.astype(np.float64) * (1.0 + alpha / T)
    return big, den, T, alpha


def score_lines(lines, chars, wordlist, sym, big, uni, T, alpha, kappa=1000.0):
    """Ideal arithmetic code length (bits) of each identifier's tokenisation."""
    nchars = len(chars)
    char_id = {c: i for i, c in enumerate(chars)}
    rank = make_rank(wordlist, nchars)
    stop = nchars
    log2 = 1.0 / np.log(2.0)
    out = []
    for s in lines:
        toks = tokenize(s, char_id, rank, nchars)
        seq = toks + [stop]
        n = len(seq)
        bits = 0.0
        for i in range(n):
            a = seq[i]
            b = seq[(i + 1) % n]
            num = big.get((a, b), 0.0) + alpha * (uni[a] / T) * (uni[b] / T)
            p = num / (uni[a] * (1.0 + alpha / T))
            bits -= np.log(p) * log2
        out.append(bits)
    return out


def cmd_stats(args):
    chars, wordlist, sym = load_dictionary(args.dir)
    big, uni, V = load_adj(args.dir)
    print(f"vocab {V}, merges {len(wordlist)}, distinct bigrams {len(big)}, "
          f"N={int(uni.sum())}, N(stop)={int(uni[len(chars)])}")


def cmd_score(args):
    chars, wordlist, sym = load_dictionary(args.dir)
    big, uni, V = load_adj(args.dir)
    _, den, T, alpha = reference_probabilities(big, uni, kappa=args.kappa)
    lines = read_lines(args.corpus, stride=args.stride)
    print(f"scoring {len(lines)} held-out identifiers "
          f"(vocab {V}, kappa {args.kappa})", flush=True)
    import time
    t = time.time()
    bits = score_lines(lines, chars, wordlist, sym, big, uni, T, alpha,
                       kappa=args.kappa)
    bits = np.array(bits)
    print(f"tokenised in {time.time()-t:.0f}s")
    budgets = [int(x) for x in args.budgets.split(',')]
    print(f"mean bits {bits.mean():.2f}")
    for bud in budgets:
        print(f"  fit <= {bud} bits: {100.0*(bits <= bud).mean():.1f}%")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    tr = sub.add_parser('train')
    tr.add_argument('--corpus', default='work/camel/merged_training.txt')
    tr.add_argument('--num-pairs', type=int, required=True)
    tr.add_argument('--sample', type=int, default=0,
                    help='stride for dictionary building (0 = all)')
    tr.add_argument('--outdir', default=None)
    tr.add_argument('--jobs', type=int, default=1)
    tr.set_defaults(func=cmd_train)
    st = sub.add_parser('stats')
    st.add_argument('--dir', required=True)
    st.add_argument('--corpus', default=None)
    st.set_defaults(func=cmd_stats)
    sc = sub.add_parser('score')
    sc.add_argument('--dir', required=True)
    sc.add_argument('--corpus', default='work/camel/merged_validation.txt')
    sc.add_argument('--stride', type=int, default=0)
    sc.add_argument('--kappa', type=float, default=1000.0)
    sc.add_argument('--budgets', default='64,128')
    sc.set_defaults(func=cmd_score)
    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
