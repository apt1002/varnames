#!/usr/bin/env python3
"""Word-level pair-merge model for `docs/TREE_WORDS.md`.

The dictionary is plain **pair-merge with self-merges forbidden**: create
`NUM_PAIRS` *words* in total by repeatedly merging the most common length-2
substring `uv` of *words* (`u != v`).  A doubled character can therefore never
collapse into a run word of its own; it is absorbed only by a pair word that
also contains a neighbour.  This is the rule described in `TREE_WORDS.md` §9.1
with the run-collapse option switched off — empirically the run words cost
nothing to remove, so the k-ary run node, the run-length table and the run
replay are gone (`docs/DICTIONARY_RULES.md`).

Tokenising replays the rules in creation order: within each block of pair rules
the lowest-ranked applicable adjacent pair is merged repeatedly, so a later
rule never makes an earlier one applicable again.

Counts.  Each identifier is the cycle `tokens + [\n]`; the adjacency matrix
counts its cyclic word bigrams, so `N(\n) =` number of strings and
`sum_v N(u,v) = N(u)` for every word `u`.

Symbol ids: `0..len(chars)-1` are the characters, `len(chars)` is `\n`, and
`len(chars)+1+r` is the word created at rank `r`.

Usage:
    tree_words.py train --corpus work/camel/merged_training.txt \\
        --num-pairs 256 --sample 100000 --outdir work/tw256
    tree_words.py stats --dir work/tw256
    tree_words.py score --dir work/tw256 --corpus work/camel/merged_validation.txt
"""
import argparse
import heapq
import time
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
    with open(path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if stride and i % stride:
                continue
            s = line.rstrip('\n')
            if s:
                lines.append(s)
                if limit and len(lines) >= limit:
                    break
    return lines


SEP = -1
RADIX = 1 << 16          # pair key = a * RADIX + b; ids are < 2**16


def alphabet_of(path):
    """Every character in the corpus, sorted by code point.

    The alphabet is the corpus's character set, so it is read from every line
    rather than from a sample: `stride` thins the identifiers the dictionary
    learns from, not the characters the model can code.  Sorting is what makes
    the ids deterministic.
    """
    seen = set()
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            s = line.rstrip('\n')
            if s:
                seen.update(s)
    return ''.join(sorted(seen))


def read_corpus_array(path, stride=0, limit=0, chars=None):
    """Stream a one-identifier-per-line corpus into one int32 id array with
    `SEP` between identifiers.

    The corpus is UTF-8.  `stride` thins the *identifiers* only: unless
    `chars` is given, every line read is still scanned for the character set,
    so a character that falls outside the sample keeps its id.  `limit` does
    stop the read, so with a limit the alphabet covers the prefix it saw.
    `chars`, when given, must cover the file.

    The mapping stays vectorised: one `str.translate` onto code points
    `0 .. len(chars)`, then a UTF-32 view.  This is what makes the full-corpus
    (stride 0) build fit in memory — a list of strings, or a list of lists of
    ids, is 10-100x bigger than the packed array.
    """
    buf = bytearray()
    seen = set()
    kept = 0
    with open(path, 'rb') as f:
        for i, line in enumerate(f):
            s = line.rstrip(b'\n')
            if not s:
                continue
            if chars is None:
                seen.update(s.decode('utf-8'))
            if stride and i % stride:
                continue
            buf += s
            buf += b'\n'
            kept += 1
            if limit and kept >= limit:
                break
    text = buf.decode('utf-8')
    chars = sorted(seen) if chars is None else list(chars)
    missing = set(text) - set(chars) - {'\n'}
    if missing:
        shown = ', '.join(repr(c) for c in sorted(missing)[:8])
        more = f' and {len(missing) - 8} more' if len(missing) > 8 else ''
        raise ValueError(
            f'{path}: character(s) {shown}{more} are not in the alphabet; '
            'pass every character in the corpus')
    nchars = len(chars)
    table = {ord(c): chr(i) for i, c in enumerate(chars)}
    table[10] = chr(nchars)             # the separator, past the last id
    codes = np.frombuffer(text.translate(table).encode('utf-32-le'),
                          dtype='<u4').astype(np.int32)
    codes[codes == nchars] = SEP
    return chars, codes


def _iter_line_chunks(path, chunk=50000, stride=0):
    """Yield lists of at most `chunk` non-empty identifiers."""
    buf = []
    with open(path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if stride and i % stride:
                continue
            s = line.rstrip('\n')
            if not s:
                continue
            buf.append(s)
            if len(buf) >= chunk:
                yield buf
                buf = []
    if buf:
        yield buf


def _cyclic_arrays(seqs, nstop):
    """Cyclic word bigram counts (with the stop token) as `(rows, cols, vals)`.

    Each line is `seq + \\n` bent into a cycle, so the bigrams are the adjacent
    `(u,v)` pairs plus `(last, \\n)` and `(\\n, first)`."""
    cnt = Counter()
    for s in seqs:
        real = [x for x in s if x is not None]
        m = len(real)
        if m == 0:
            continue
        for i in range(m - 1):
            cnt[(real[i], real[i + 1])] += 1
        cnt[(real[-1], nstop)] += 1
        cnt[(nstop, real[0])] += 1
    rows = np.fromiter((k[0] for k in cnt), dtype=np.int64, count=len(cnt))
    cols = np.fromiter((k[1] for k in cnt), dtype=np.int64, count=len(cnt))
    vals = np.fromiter(cnt.values(), dtype=np.float64, count=len(cnt))
    return rows, cols, vals


def build_dictionary(lines, num_pairs, verbose=False, trace=None):
    """Greedy pair-merge dictionary with self-merges forbidden.

    Every merge is between two *different* words, so a doubled character (or a
    doubled word) is never collapsed on its own — it can only be absorbed by a
    pair word that also contains a neighbour.

    `rules[r]` is `('pair', (a, b), new_id)` in creation order; ids are
    `len(chars)+1+r`.

    If `trace` is a dict, it is filled with the information needed to replay the
    *cyclic* word-bigram count matrix level by level (for the break-open prior):
    `trace['level0']` = the level-0 counts, and `trace['entries']` = one entry
    per rule, `('pair', u, v, w, Ls, Rs)` (the left/right neighbours, `stop` at a
    line boundary, of each merged occurrence)."""
    chars = sorted(set(''.join(lines)))
    cid = {c: i for i, c in enumerate(chars)}
    sym = list(chars) + [STOP]
    seqs = [[cid[c] for c in s] for s in lines]
    rules = []
    next_id = len(chars) + 1
    budget = num_pairs
    if trace is not None:
        trace['nchars'] = len(chars)
        trace['level0'] = _cyclic_arrays(seqs, len(chars))
        trace['entries'] = []

    cnt = Counter()
    pos = {}
    heap = []
    for si, seq in enumerate(seqs):
        for j in range(len(seq) - 1):
            p = (seq[j], seq[j + 1])
            pos.setdefault(p, set()).add((si, j))
            cnt[p] += 1
    heap[:] = [(-c, p) for p, c in cnt.items() if c > 1 and p[0] != p[1]]
    heapq.heapify(heap)

    def rebuild():
        cnt.clear()
        pos.clear()
        for si, seq in enumerate(seqs):
            for j in range(len(seq) - 1):
                if seq[j] is None or seq[j + 1] is None:
                    continue
                p = (seq[j], seq[j + 1])
                pos.setdefault(p, set()).add((si, j))
                cnt[p] += 1
        heap[:] = [(-c, p) for p, c in cnt.items() if c > 1 and p[0] != p[1]]
        heapq.heapify(heap)

    def decr(si, p, j):
        s = pos.get(p)
        if s is not None and (si, j) in s:
            s.discard((si, j))
            cnt[p] -= 1
            if cnt[p] > 1 and p[0] != p[1]:  # keep a valid heap key for `p`
                heapq.heappush(heap, (-cnt[p], p))

    def incr(si, p, j):
        s = pos.setdefault(p, set())
        if (si, j) not in s:
            s.add((si, j))
            cnt[p] += 1
            if p[0] != p[1]:
                heapq.heappush(heap, (-cnt[p], p))

    step = 0
    while budget > 0:
        p = None
        while heap:
            neg, pp = heapq.heappop(heap)
            if cnt.get(pp, 0) == -neg and -neg > 1 and pp[0] != pp[1]:
                p = pp
                break
        if p is None:
            break

        a, b = p                                            # ordinary pair merge
        positions = list(pos.pop(p, ()))
        new = next_id
        next_id += 1
        sym.append(sym[a] + sym[b])
        rules.append(('pair', (a, b), new))
        _Ls = [] if trace is not None else None
        _Rs = [] if trace is not None else None
        for si, i in positions:
            s = seqs[si]
            if i >= len(s) or s[i] is None or s[i] != a:
                continue
            ri = i + 1                       # true right token of the pair
            while ri < len(s) and s[ri] is None:
                ri += 1
            if ri >= len(s) or s[ri] != b:
                continue
            li = i - 1                       # true left neighbour (skip holes)
            while li >= 0 and s[li] is None:
                li -= 1
            rr = ri + 1                      # token after `b` (skip holes)
            while rr < len(s) and s[rr] is None:
                rr += 1
            left = s[li] if li >= 0 else None
            right = s[rr] if rr < len(s) else None
            if trace is not None:            # bound the cycle by the stop token
                nstop = len(chars)
                _Ls.append(left if left is not None else nstop)
                _Rs.append(right if right is not None else nstop)
            if left is not None:
                decr(si, (left, a), li)
            if right is not None:
                decr(si, (b, right), ri)
            s[i] = new
            s[ri] = None
            if left is not None:
                incr(si, (left, new), li)
            if right is not None:
                incr(si, (new, right), i)
        if trace is not None:
            trace['entries'].append(
                ('pair', a, b, new, np.array(_Ls, dtype=np.int64),
                 np.array(_Rs, dtype=np.int64)))
        cnt[p] = 0                       # all occurrences consumed by the merge
        budget -= 1
        step += 1
        if len(heap) > 4 * len(cnt) + 4096:
            heap[:] = [(-c, pp) for pp, c in cnt.items()
                       if c > 1 and pp[0] != pp[1]]
            heapq.heapify(heap)
        if verbose and step % 500 == 0:
            print(f"  step {step} pair {sym[new]!r} vocab {len(sym)}", flush=True)
    return chars, rules, sym


def _counts_all(arr, chunk=2_000_000):
    """Pair -> count over the whole array, excluding separator adjacencies.

    Chunked so the peak stays at a couple of 2M-element integers instead of two
    Python lists the length of the corpus."""
    cnt = {}
    n = arr.size
    for s in range(0, max(n - 1, 0), chunk):
        e = min(s + chunk, n - 1)
        a = arr[s:e]
        b = arr[s + 1:e + 1]
        m = (a != SEP) & (b != SEP)
        if not m.any():
            continue
        code = a[m].astype(np.int64) * RADIX + b[m]
        u, c = np.unique(code, return_counts=True)
        for k, v in zip(u.tolist(), c.tolist()):
            key = (k // RADIX, k % RADIX)
            cnt[key] = cnt.get(key, 0) + v
    return cnt


def build_dictionary_arr(chars, arr, num_pairs, verbose=False):
    """`build_dictionary` on a packed id array, with no position index.

    Same greedy rule and the same tie-breaking as `build_dictionary`, so the
    word list is identical; the difference is that occurrences are found by a
    numpy scan of the array at each merge instead of being tracked in a
    `{(a, b): {(seq, pos), ...}}` dict.  That dict is what made the full-corpus
    build need gigabytes; the scan is O(N) per merge but vectorised, and the
    array is 10-100x smaller than the equivalent list of lists.

    `arr` is consumed (mutated in place); do not reuse it afterwards.
    """
    nchars = len(chars)
    sym = list(chars) + [STOP]
    rules = []
    next_id = nchars + 1
    budget = num_pairs

    cnt = _counts_all(arr)
    heap = [(-c, p) for p, c in cnt.items() if c > 1 and p[0] != p[1]]
    heapq.heapify(heap)

    step = 0
    while budget > 0:
        p = None
        while heap:
            neg, pp = heapq.heappop(heap)
            if cnt.get(pp, 0) == -neg and -neg > 1 and pp[0] != pp[1]:
                p = pp
                break
        if p is None:
            break
        a, b = p

        idx = np.flatnonzero((arr[:-1] == a) & (arr[1:] == b))
        if idx.size == 0:
            cnt[p] = 0
            continue
        new = next_id
        next_id += 1
        sym.append(sym[a] + sym[b])
        rules.append(('pair', (a, b), new))

        # Count diff, vectorised: only pairs touching a merged slot change.  In
        # a chain of adjacent occurrences (.. a b a b ..) the pair *between* two
        # merged tokens is (b, a) -- removed once, via the second's left -- and
        # (new, new) -- created once, via the first's right -- so the left and
        # right contributions are suppressed on the "inside" of a chain.
        n = arr.size
        isocc = np.zeros(n, dtype=bool)
        isocc[idx] = True
        L = idx - 1
        Lm = np.maximum(L, 0)
        Lvalid = (L >= 0) & (arr[Lm] != SEP)
        Ltok = arr[Lm]
        cl = np.maximum(idx - 2, 0)
        chain_left = (idx - 2 >= 0) & isocc[cl]
        R = idx + 2
        Rm = np.minimum(R, n - 1)
        Rin = R < n
        Rvalid = Rin & (arr[Rm] != SEP)
        Rtok = arr[Rm]
        chain_right = Rin & isocc[Rm]

        rem = Counter({(a, b): int(idx.size)})
        for x in Ltok[Lvalid].tolist():
            rem[(x, a)] += 1
        for y in Rtok[Rvalid & ~chain_right].tolist():
            rem[(b, y)] += 1
        cre = Counter()
        for y in np.where(chain_right, new, Rtok)[Rvalid].tolist():
            cre[(new, y)] += 1
        for x in Ltok[Lvalid & ~chain_left].tolist():
            cre[(x, new)] += 1

        d = Counter(cre)
        d.subtract(rem)
        for q, dc in d.items():
            if dc:
                cnt[q] = cnt.get(q, 0) + dc
                if cnt[q] > 1 and q[0] != q[1]:
                    heapq.heappush(heap, (-cnt[q], q))
        cnt[p] = 0

        arr[idx] = new
        keep = np.ones(n, dtype=bool)
        keep[idx + 1] = False
        arr = arr[keep]
        budget -= 1
        step += 1
        if verbose and step % 500 == 0:
            print(f"  step {step} pair {sym[new]!r} vocab {len(sym)}",
                  flush=True)
    return chars, rules, sym


def save_dictionary(outdir, chars, rules, sym):
    with open(os.path.join(outdir, 'dict.txt'), 'w', encoding='utf-8') as f:
        f.write('\t'.join(c if c != STOP else STOP_LABEL for c in chars) + '\n')
        for _, (a, b), _nid in rules:
            f.write(f"P\t{a}\t{b}\n")
    np.save(os.path.join(outdir, 'sym.npy'), np.array(
        [w if w != STOP else STOP_LABEL for w in sym]))


def load_dictionary(outdir):
    sym = [str(x) for x in np.load(os.path.join(outdir, 'sym.npy'))]
    chars = [s for s in sym if len(s) == 1 and s != STOP_LABEL]
    nchars = len(chars)
    rules = []
    next_id = nchars + 1
    with open(os.path.join(outdir, 'dict.txt'), 'r', encoding='utf-8') as f:
        next(f)                                          # the charset line
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if parts[0] != 'P':
                raise ValueError(
                    f"{outdir}: 'R' (run) rules are no longer supported -- this "
                    "dictionary predates the no-run rule, rebuild it")
            a, b = int(parts[1]), int(parts[2])
            rules.append(('pair', (a, b), next_id))
            next_id += 1
    return chars, rules, sym


def make_plan(rules, nchars):
    """Compile the rule list into a tokenisation plan: one
    `('pairs', {(a,b): (rank, new_id)})` block, in creation order.  Rank `r` has
    word id `nchars+1+r`."""
    block = {}
    for rank, (_, (a, b), _nid) in enumerate(rules):
        block[(a, b)] = (rank, nchars + 1 + rank)
    return [('pairs', block)]


def _apply_pair_block(tokens, rank_map):
    """Merge the lowest-ranked applicable adjacent pair repeatedly (the block's
    pair rules all apply before any later rule; within the block lowest rank
    first).  Doubly linked list, so no index shifting on a merge."""
    n = len(tokens)
    if n < 2:
        return tokens
    nxt = list(range(1, n + 1))
    prv = list(range(-1, n - 1))
    dead = [False] * n
    val = tokens[:]
    h = []

    def best(i):
        if not (0 <= i < n) or dead[i]:
            return None
        j = nxt[i]
        if j >= n or dead[j]:
            return None
        return rank_map.get((val[i], val[j]))

    def push(i):
        b = best(i)
        if b is not None:
            heapq.heappush(h, (b[0], i))

    for i in range(n):
        push(i)
    while h:
        r, i = heapq.heappop(h)
        b = best(i)
        if b is None:
            continue
        if b[0] != r:
            heapq.heappush(h, (b[0], i))
            continue
        _, newid = b
        j = nxt[i]
        val[i] = newid
        dead[j] = True
        nxt[i] = nxt[j]
        if nxt[j] < n:
            prv[nxt[j]] = i
        push(prv[i])
        push(i)
    out = []
    i = 0
    while i < n:
        out.append(val[i])
        i = nxt[i]
    return out


def _apply_pair_block_stack(tokens, rank_map):
    """Tokenise one pair block with a precedence (operator) parser.

    `rank_map[(a, b)] = (rank, new_id)`, lower rank binds tighter.  Keep a
    stack; before pushing the next symbol reduce the top pair while its rank is
    `<=` the rank of the pair it would form with the lookahead (left wins on
    ties) -- i.e. reduce exactly the *local minima*.  Equivalent to the heap
    version because the ranks are nested (a merge always outranks the merges
    that built its operands), so the lowest-rank-first rule reduces local minima
    only.  O(n) with plain list ops instead of a heap.
    """
    if len(tokens) < 2:
        return tokens
    stack = []
    for t in tokens:
        while len(stack) >= 2:
            left = rank_map.get((stack[-2], stack[-1]))
            if left is None:
                break
            right = rank_map.get((stack[-1], t))
            if right is not None and left[0] > right[0]:
                break                      # the pair with `t` binds tighter
            stack[-2] = left[1]            # reduce the top pair
            del stack[-1]
        stack.append(t)
    while len(stack) >= 2:                 # drain: no more lookahead
        left = rank_map.get((stack[-2], stack[-1]))
        if left is None:
            break
        stack[-2] = left[1]
        del stack[-1]
    return stack


def _apply_pair_block_buckets(tokens, rank_map):
    """Tokenise one pair block with an ascending-rank bucket queue.

    Ranks are nested -- a merge's rank always exceeds the ranks that built its
    operands -- so a merge never creates a pair with a lower rank than itself.
    Hence sweeping ranks 0,1,2,... once, merging every still-valid pair found in
    each bucket, performs the same merges as lowest-rank-first but in O(n) with
    the distinct ranks spawned (small), not a full heap.  Linked list over
    positions; stale entries are skipped.
    """
    n = len(tokens)
    if n < 2 or not rank_map:
        return tokens
    nxt = list(range(1, n + 1))
    prv = list(range(-1, n - 1))
    dead = [False] * n
    val = tokens[:]
    buckets = {}
    rank_heap = []
    get = rank_map.get

    for i in range(n - 1):                       # initial adjacent pairs
        b = get((val[i], val[i + 1]))
        if b is not None:
            lst = buckets.get(b[0])
            if lst is None:
                buckets[b[0]] = [i]
                heapq.heappush(rank_heap, b[0])
            else:
                lst.append(i)
    while rank_heap:
        r = rank_heap[0]
        bucket = buckets[r]
        if not bucket:
            heapq.heappop(rank_heap)
            del buckets[r]
            continue
        i = bucket.pop()
        if dead[i]:
            continue
        j = nxt[i]
        if j >= n or dead[j]:
            continue
        b = get((val[i], val[j]))
        if b is None or b[0] != r:
            continue
        val[i] = b[1]
        dead[j] = True
        nxt[i] = nxt[j]
        nj = nxt[j]
        if nj < n:
            prv[nj] = i
        for k in (prv[i], i):                    # refresh the two neighbours
            if k < 0 or dead[k]:
                continue
            jj = nxt[k]
            if jj >= n or dead[jj]:
                continue
            bb = get((val[k], val[jj]))
            if bb is None:
                continue
            lst = buckets.get(bb[0])
            if lst is None:
                buckets[bb[0]] = [k]
                heapq.heappush(rank_heap, bb[0])
            else:
                lst.append(k)
    out = []
    i = 0
    while i < n:
        out.append(val[i])
        i = nxt[i]
    return out


def tokenize(s, char_id, plan, nchars):
    """Tokenise with the ascending-rank bucket parser (production path)."""
    toks = [char_id[c] for c in s]
    for _, rank_map in plan:
        toks = _apply_pair_block_buckets(toks, rank_map)
    return toks


def tokenize_heap(s, char_id, plan, nchars):
    """Reference tokeniser: the heap + linked-list pair blocks (see
    `check_tree_words.py` / `tokenizer_bench.py`)."""
    toks = [char_id[c] for c in s]
    for _, rank_map in plan:
        toks = _apply_pair_block(toks, rank_map)
    return toks


def tokenize_stack(s, char_id, plan, nchars):
    """Same as `tokenize` but with the precedence-parser pair blocks."""
    toks = [char_id[c] for c in s]
    for _, rank_map in plan:
        toks = _apply_pair_block_stack(toks, rank_map)
    return toks


def tokenize_buckets(s, char_id, plan, nchars):
    """Same as `tokenize` but with the ascending-rank bucket-queue pair blocks."""
    toks = [char_id[c] for c in s]
    for _, rank_map in plan:
        toks = _apply_pair_block_buckets(toks, rank_map)
    return toks


def count_adjacency(lines, char_id, plan, nchars):
    """Count cyclic word bigrams and unigrams over `lines`."""
    stop = nchars
    big = Counter()
    uni = Counter()
    for s in lines:
        seq = tokenize(s, char_id, plan, nchars) + [stop]
        n = len(seq)
        for i in range(n):
            uni[seq[i]] += 1
            big[(seq[i], seq[(i + 1) % n])] += 1
    return big, uni


_W = {}


def _init_worker(char_id, plan, nchars):
    _W['char_id'] = char_id
    _W['plan'] = plan
    _W['nchars'] = nchars


def _count_chunk(lines):
    return count_adjacency(lines, _W['char_id'], _W['plan'], _W['nchars'])


def count_adjacency_parallel(lines, char_id, plan, nchars, jobs=1,
                             chunksize=2000):
    if jobs <= 1:
        return count_adjacency(lines, char_id, plan, nchars)
    import multiprocessing as mp
    big = Counter()
    uni = Counter()
    chunks = [lines[i:i + chunksize] for i in range(0, len(lines), chunksize)]
    with mp.Pool(jobs, initializer=_init_worker,
                 initargs=(char_id, plan, nchars)) as pool:
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


def write_adj_arrays(outdir, rows, cols, data, uni, sym, name='adj'):
    """`write_adj` for counts that are already arrays (the streaming path)."""
    nvoc = len(sym)
    uni_arr = np.zeros(nvoc, dtype=np.int64)
    uni_arr[:] = np.asarray(uni, dtype=np.int64)
    np.savez_compressed(os.path.join(outdir, name + '.npz'),
                        rows=np.asarray(rows, dtype=np.int64),
                        cols=np.asarray(cols, dtype=np.int64),
                        data=np.asarray(data, dtype=np.float64),
                        uni=uni_arr, nvoc=np.array([nvoc]))


_C = {}


def _init_code_worker(char_id, plan, nchars, nvoc=None):
    _C['char_id'] = char_id
    _C['plan'] = plan
    _C['nchars'] = nchars
    _C['nvoc'] = nvoc if nvoc else nchars + 1


def _chunk_codes(lines):
    """Tokenise a chunk and return (bigram codes, unigram counts).

    Codes are `a*V + b`, which stays inside int32 for every vocabulary in the
    grid (`V = 8192` gives `8191*8192 + 8191 < 2**31`)."""
    char_id = _C['char_id']
    plan = _C['plan']
    nchars = _C['nchars']
    V = _C['nvoc']
    stop = nchars
    seq = [stop]                       # the stop *before* the first identifier
    for s in lines:
        seq.extend(tokenize(s, char_id, plan, nchars))
        seq.append(stop)
    t = np.asarray(seq, dtype=np.int64)
    u = np.bincount(t[1:], minlength=V).astype(np.int64)
    c = (t[:-1] * V + t[1:]).astype(np.int32)
    return c, u


def count_adjacency_stream(path, char_id, plan, nchars, nvoc=None, chunk=50000,
                           jobs=1, stride=0, verbose=False):
    """Cyclic word-bigram counts over the whole file in bounded memory.

    Each identifier is tokenised and bracketed by the stop token, so the adjacent
    pairs of the concatenation are exactly the cyclic bigrams: `(t_i, t_i+1)`
    inside an identifier, `(last, stop)` at its end, `(stop, first)` at its
    start.  The stop *before* the first identifier is not counted as a unigram.
    Per-chunk `np.unique` + a dict merge turns the codes into
    `(rows, cols, counts)`.

    This replaces `count_adjacency_parallel`, which needed the whole corpus as a
    Python list of strings plus a bigram `Counter` of tuples.
    """
    if nvoc is None:
        nvoc = nchars + 1
    V = nvoc
    uni = np.zeros(V, dtype=np.int64)
    tot = {}
    seen = 0

    def take(pairs):
        """Fold each chunk's `(codes, unigram counts)` into the running totals.

        Per-chunk `np.unique` plus a dict merge keeps the peak at the size of
        the distinct-bigram dict.  Concatenating every code first and calling
        `np.unique` once would need two extra corpus-length int32 arrays."""
        nonlocal seen
        for c, u in pairs:
            uni[:] += u
            seen += int(u.sum())
            if c.size:
                v, n = np.unique(c, return_counts=True)
                for k, cn in zip(v.tolist(), n.tolist()):
                    tot[k] = tot.get(k, 0) + cn

    if jobs <= 1:
        _init_code_worker(char_id, plan, nchars, nvoc)
        take(_chunk_codes(lines)
             for lines in _iter_line_chunks(path, chunk, stride))
    else:
        import multiprocessing as mp
        with mp.Pool(jobs, initializer=_init_code_worker,
                     initargs=(char_id, plan, nchars, nvoc)) as pool:
            take(pool.imap_unordered(_chunk_codes,
                                     _iter_line_chunks(path, chunk, stride),
                                     chunksize=1))
    if not tot:
        return (np.empty(0, np.int64), np.empty(0, np.int64),
                np.empty(0, np.float64), uni)
    u = np.fromiter(tot.keys(), dtype=np.int64, count=len(tot))
    c = np.fromiter(tot.values(), dtype=np.int64, count=len(tot))
    del tot
    rows = (u // V).astype(np.int64)
    cols = (u % V).astype(np.int64)
    if verbose:
        print(f"  {seen} tokens, {u.size} distinct bigrams", flush=True)
    return rows, cols, c.astype(np.float64), uni


def cmd_train(args):
    outdir = args.outdir or f'work/tw{args.num_pairs}'
    os.makedirs(outdir, exist_ok=True)
    t0 = time.time()
    chars, arr = read_corpus_array(args.corpus, stride=args.sample)
    nlines = int(np.count_nonzero(arr == SEP))
    print(f"dictionary corpus {args.corpus}: {nlines} lines "
          f"(stride {args.sample or 1}), {arr.size - nlines} chars, "
          f"{arr.nbytes / 1e6:.0f} MB packed "
          f"({time.time() - t0:.0f}s read)", flush=True)
    chars, rules, sym = build_dictionary_arr(chars, arr, args.num_pairs,
                                             verbose=True)
    del arr
    print(f"dictionary: {len(rules)} rules, vocab {len(sym)} "
          f"({time.time() - t0:.0f}s)", flush=True)
    save_dictionary(outdir, chars, rules, sym)
    with open(os.path.join(outdir, 'meta.json'), 'w') as f:
        json.dump(dict(corpus=args.corpus, num_pairs=args.num_pairs,
                       sample=args.sample, nlines=nlines), f)

    char_id = {c: i for i, c in enumerate(chars)}
    plan = make_plan(rules, len(chars))
    t = time.time()
    print(f"counting cyclic bigrams over {args.corpus} "
          f"(stride {args.stride or 1}, jobs {args.jobs})", flush=True)
    rows, cols, data, uni = count_adjacency_stream(
        args.corpus, char_id, plan, len(chars), len(sym), jobs=args.jobs,
        stride=args.stride, verbose=True)
    write_adj_arrays(outdir, rows, cols, data, uni, sym)
    print(f"adjacency: {rows.size} distinct bigrams, N={int(uni.sum())}, "
          f"N(stop)={int(uni[len(chars)])} ({time.time() - t:.0f}s)", flush=True)
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


def score_lines(lines, char_id, plan, nchars, big, uni, T, alpha):
    """Ideal arithmetic code length (bits) of each identifier's tokenisation."""
    stop = nchars
    log2 = 1.0 / np.log(2.0)
    out = []
    for s in lines:
        seq = tokenize(s, char_id, plan, nchars) + [stop]
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


def cmd_adj(args):
    """Build ``adj.npz`` for an existing dictionary directory."""
    chars, rules, sym = load_dictionary(args.dir)
    char_id = {c: i for i, c in enumerate(chars)}
    plan = make_plan(rules, len(chars))
    print(f"counting cyclic bigrams over {args.corpus} "
          f"(stride {args.stride or 1}, jobs {args.jobs})", flush=True)
    rows, cols, data, uni = count_adjacency_stream(
        args.corpus, char_id, plan, len(chars), len(sym), jobs=args.jobs,
        stride=args.stride, verbose=True)
    write_adj_arrays(args.dir, rows, cols, data, uni, sym)
    print(f"adjacency: {rows.size} distinct bigrams, "
          f"N={int(uni.sum())}, N(stop)={int(uni[len(chars)])}", flush=True)
    print(f"wrote {args.dir}/adj.npz", flush=True)


def cmd_stats(args):
    chars, rules, sym = load_dictionary(args.dir)
    big, uni, V = load_adj(args.dir)
    print(f"vocab {V}, rules {len(rules)}, distinct bigrams "
          f"{len(big)}, N={int(uni.sum())}, N(stop)={int(uni[len(chars)])}")


def cmd_score(args):
    chars, rules, sym = load_dictionary(args.dir)
    big, uni, V = load_adj(args.dir)
    char_id = {c: i for i, c in enumerate(chars)}
    plan = make_plan(rules, len(chars))
    # Dead words -- created on the (sampled) build corpus but never selected on
    # the full corpus -- have zero count and would divide by zero.  Give them a
    # Laplace floor so their row (and the prior) is defined; this changes
    # nothing for words that do occur.
    dead = int(np.sum(np.asarray(uni) == 0))
    if dead:
        print(f"flooring {dead} zero-count words", flush=True)
        uni = np.maximum(np.asarray(uni, dtype=np.float64), 0.5)
    _, den, T, alpha = reference_probabilities(big, uni, kappa=args.kappa)
    lines = read_lines(args.corpus, stride=args.stride)
    print(f"scoring {len(lines)} held-out identifiers "
          f"(vocab {V}, kappa {args.kappa})", flush=True)
    import time
    t = time.time()
    bits = score_lines(lines, char_id, plan, len(chars), big, uni, T, alpha)
    bits = np.array(bits)
    print(f"tokenised in {time.time()-t:.0f}s")
    budgets = [int(x) for x in args.budgets.split(',')]
    print(f"mean bits {bits.mean():.2f}")
    for bud in budgets:
        n = int((bits <= bud).sum())
        print(f"  fit <= {bud} bits: {100.0*(bits <= bud).mean():.1f}% "
              f"({n} of {len(bits)})")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    tr = sub.add_parser('train')
    tr.add_argument('--corpus', default='work/camel/merged_training.txt')
    tr.add_argument('--num-pairs', type=int, required=True)
    tr.add_argument('--sample', type=int, default=0,
                    help='stride for dictionary building (0 = all)')
    tr.add_argument('--stride', type=int, default=0,
                    help='stride for the adjacency count (0 = all)')
    tr.add_argument('--outdir', default=None)
    tr.add_argument('--jobs', type=int, default=1)
    tr.set_defaults(func=cmd_train)
    ad = sub.add_parser('adj')
    ad.add_argument('--dir', required=True)
    ad.add_argument('--corpus', default='work/camel/merged_training.txt')
    ad.add_argument('--stride', type=int, default=0)
    ad.add_argument('--jobs', type=int, default=1)
    ad.set_defaults(func=cmd_adj)
    st = sub.add_parser('stats')
    st.add_argument('--dir', required=True)
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
