#!/usr/bin/env python3
"""Word-level (run-aware pair-merge) model for `docs/TREE_WORDS.md`.

The dictionary is the **run-aware** rule of `docs/TREE_WORDS.md` §9.1.  Create
`NUM_PAIRS` *words* in total: find the most common length-2 substring `uv` of
*words*; if `u != v` merge it (ordinary BPE, one word); if `u == v` **collapse
every maximal run `u^k` (`k >= 2`) to a flat word `(u^k)`, one word per observed
run length** (so a run step can spend several words of the budget at once).

A run word `(u^k)` is a single **`k`-ary** node with `lc((u^k)) = rc((u^k)) = u`
(it is *not* `k-1` nested binary merges).  This replaces the earlier plain
pair-merge rule, which is obsolete.

Effects of a run collapse are exact: a maximal run of length `L` becomes the
word `(u^L)` if that word was created, else a greedy longest-match decomposition
into the run words that do exist (so `L = 4` with only `(u^2)` present becomes
`(u^2)(u^2)`); a leftover single character stays a character.

Tokenising replays the rules in creation order.  Consecutive *pair* rules are
merged with a linked-list "lowest-ranked adjacent pair" pass; a *run* rule is a
leftmost maximal-run replacement with greedy longest match (so unseen run
lengths decompose, e.g. `L = 4` with only `(u^2)` present becomes `(u^2)(u^2)`).

Counts.  Each identifier is the cycle `tokens + [\n]`; the adjacency matrix
counts its cyclic word bigrams, so `N(\n) =` number of strings and
`sum_v N(u,v) = N(u)` for every word `u`.

Symbol ids: `0..len(chars)-1` are the characters, `len(chars)` is `\n`, and
`len(chars)+1+r` is the word (pair or run) created at rank `r`.

Usage:
    tree_words.py train --corpus work/camel/merged_training.txt \\
        --num-pairs 256 --sample 100000 --outdir work/tw256
    tree_words.py stats --dir work/tw256
    tree_words.py score --dir work/tw256 --corpus work/camel/merged_validation.txt
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
    """Run-aware greedy dictionary.  Returns `(chars, rules, sym)`.

    `rules[r]` is `('pair', (a, b), new_id)` or `('run', a, [(k, new_id), ...])`
    in creation order; ids are `len(chars)+1+r` in order.

    If `trace` is a dict, it is filled with the information needed to replay the
    *cyclic* word-bigram count matrix level by level (for the break-open prior):
    `trace['level0']` = the level-0 counts, and `trace['entries']` = one entry
    per rule, `('pair', u, v, w, Ls, Rs)` (the left/right neighbours, `stop` at a
    line boundary, of each merged occurrence) or `('run', a, created, snapshot)`
    (the counts after the run)."""
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
    heap[:] = [(-c, p) for p, c in cnt.items() if c > 1]
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
        heap[:] = [(-c, p) for p, c in cnt.items() if c > 1]
        heapq.heapify(heap)

    def decr(si, p, j):
        s = pos.get(p)
        if s is not None and (si, j) in s:
            s.discard((si, j))
            cnt[p] -= 1
            if cnt[p] > 1:                   # keep a valid heap key for `p`
                heapq.heappush(heap, (-cnt[p], p))

    def incr(si, p, j):
        s = pos.setdefault(p, set())
        if (si, j) not in s:
            s.add((si, j))
            cnt[p] += 1
            heapq.heappush(heap, (-cnt[p], p))

    step = 0
    while budget > 0:
        p = None
        while heap:
            neg, pp = heapq.heappop(heap)
            if cnt.get(pp, 0) == -neg and -neg > 1:
                p = pp
                break
        if p is None:
            break

        if p[0] == p[1]:                                   # doubled -> run step
            a = p[0]
            # drop the `None` holes left by earlier pair merges so run
            # detection and `rebuild` see clean, indexable arrays
            for idx in range(len(seqs)):
                if None in seqs[idx]:
                    seqs[idx] = [x for x in seqs[idx] if x is not None]
            lengths = Counter()
            for seq in seqs:
                i = 0
                n = len(seq)
                while i < n:
                    if seq[i] == a:
                        j = i
                        while j < n and seq[j] == a:
                            j += 1
                        if j - i >= 2:
                            lengths[j - i] += 1
                        i = j
                    else:
                        i += 1
            if not lengths:                                # no actual run: skip
                continue
            else:
                order = sorted(lengths, key=lambda k: (-lengths[k], k))
                created = []
                for k in order:
                    if budget <= 0:
                        break
                    nid = next_id
                    next_id += 1
                    sym.append(sym[a] * k)
                    created.append((k, nid))
                    budget -= 1
                cmap = dict(created)
                for idx in range(len(seqs)):
                    seq = seqs[idx]
                    out = []
                    i = 0
                    n = len(seq)
                    while i < n:
                        if seq[i] == a:
                            j = i
                            while j < n and seq[j] == a:
                                j += 1
                            Lr = j - i
                            if Lr >= 2:
                                kmax = max(cmap)
                                rem = Lr
                                while rem > 0:
                                    k = min(rem, kmax)
                                    while k > 1 and k not in cmap:
                                        k -= 1
                                    if k in cmap:
                                        out.append(cmap[k])
                                        rem -= k
                                    else:
                                        out.extend([a] * rem)
                                        rem = 0
                            else:
                                out.extend([a] * Lr)
                            i = j
                        else:
                            out.append(seq[i])
                            i += 1
                    seqs[idx] = out
                rules.append(('run', a, created))
                if trace is not None:
                    trace['entries'].append(
                        ('run', a, list(created),
                         _cyclic_arrays(seqs, len(chars))))
                step += 1
                rebuild()
                if verbose and step % 500 == 0:
                    print(f"  step {step} run {sym[a]}* "
                          f"({len(created)} words) vocab {len(sym)}", flush=True)
                continue

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
            heap[:] = [(-c, pp) for pp, c in cnt.items() if c > 1]
            heapq.heapify(heap)
        if verbose and step % 500 == 0:
            print(f"  step {step} pair {sym[new]!r} vocab {len(sym)}", flush=True)
    return chars, rules, sym


def save_dictionary(outdir, chars, rules, sym):
    with open(os.path.join(outdir, 'dict.txt'), 'w', encoding='ascii') as f:
        f.write('\t'.join(c if c != STOP else STOP_LABEL for c in chars) + '\n')
        for item in rules:
            if item[0] == 'pair':
                _, (a, b), _nid = item
                f.write(f"P\t{a}\t{b}\n")
            else:
                _, a, created = item
                f.write("R\t" + str(a) + "\t"
                        + "\t".join(str(k) for k, _ in created) + "\n")
    np.save(os.path.join(outdir, 'sym.npy'), np.array(
        [w if w != STOP else STOP_LABEL for w in sym]))


def load_dictionary(outdir):
    sym = [str(x) for x in np.load(os.path.join(outdir, 'sym.npy'))]
    chars = [s for s in sym if len(s) == 1 and s != STOP_LABEL]
    nchars = len(chars)
    rules = []
    next_id = nchars + 1
    with open(os.path.join(outdir, 'dict.txt'), 'r', encoding='ascii') as f:
        next(f)                                          # the charset line
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if parts[0] == 'P':
                a, b = int(parts[1]), int(parts[2])
                rules.append(('pair', (a, b), next_id))
                next_id += 1
            else:
                a = int(parts[1])
                created = [(int(k), next_id + i)
                           for i, k in enumerate(parts[2:])]
                rules.append(('run', a, created))
                next_id += len(created)
    return chars, rules, sym


def make_plan(rules, nchars):
    """Compile the rule list into a tokenisation plan: alternating
    `('pairs', {(a,b): (rank, new_id)})` blocks and `('run', a, {k: new_id})`
    rules, in creation order.  Rank `r` has word id `nchars+1+r`."""
    plan = []
    block = {}
    rank = 0
    for item in rules:
        if item[0] == 'pair':
            _, (a, b), _nid = item
            block[(a, b)] = (rank, nchars + 1 + rank)
            rank += 1
        else:
            _, a, created = item
            if block:
                plan.append(('pairs', block))
                block = {}
            plan.append(('run', a, {k: nid for k, nid in created}))
            rank += len(created)
    if block:
        plan.append(('pairs', block))
    return plan


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


def _apply_run(tokens, a, lenmap):
    """Replace each maximal run of `a`: the exact-length word if present, else
    a greedy longest-match decomposition (leftover `a`'s kept as `a`)."""
    if not lenmap:
        return tokens
    kmax = max(lenmap)
    out = []
    i = 0
    n = len(tokens)
    while i < n:
        if tokens[i] == a:
            j = i
            while j < n and tokens[j] == a:
                j += 1
            rem = j - i
            while rem > 0:
                k = min(rem, kmax)
                while k not in lenmap and k > 1:
                    k -= 1
                if k in lenmap:
                    out.append(lenmap[k])
                    rem -= k
                else:
                    out.extend([a] * rem)
                    rem = 0
            i = j
        else:
            out.append(tokens[i])
            i += 1
    return out


def tokenize(s, char_id, plan, nchars):
    """Tokenise with the ascending-rank bucket parser (production path)."""
    toks = [char_id[c] for c in s]
    for item in plan:
        if item[0] == 'pairs':
            toks = _apply_pair_block_buckets(toks, item[1])
        else:
            toks = _apply_run(toks, item[1], item[2])
    return toks


def tokenize_heap(s, char_id, plan, nchars):
    """Reference tokeniser: the heap + linked-list pair blocks (see
    `check_tree_words.py` / `tokenizer_bench.py`)."""
    toks = [char_id[c] for c in s]
    for item in plan:
        if item[0] == 'pairs':
            toks = _apply_pair_block(toks, item[1])
        else:
            toks = _apply_run(toks, item[1], item[2])
    return toks


def tokenize_stack(s, char_id, plan, nchars):
    """Same as `tokenize` but with the precedence-parser pair blocks."""
    toks = [char_id[c] for c in s]
    for item in plan:
        if item[0] == 'pairs':
            toks = _apply_pair_block_stack(toks, item[1])
        else:
            toks = _apply_run(toks, item[1], item[2])
    return toks


def tokenize_buckets(s, char_id, plan, nchars):
    """Same as `tokenize` but with the ascending-rank bucket-queue pair blocks."""
    toks = [char_id[c] for c in s]
    for item in plan:
        if item[0] == 'pairs':
            toks = _apply_pair_block_buckets(toks, item[1])
        else:
            toks = _apply_run(toks, item[1], item[2])
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


def cmd_train(args):
    outdir = args.outdir or f'work/tw{args.num_pairs}'
    os.makedirs(outdir, exist_ok=True)
    build = read_lines(args.corpus, stride=args.sample)
    print(f"dictionary corpus {args.corpus}: {len(build)} lines "
          f"(stride {args.sample or 1})", flush=True)
    chars, rules, sym = build_dictionary(build, args.num_pairs, verbose=True)
    print(f"dictionary: {len(rules)} rules, vocab {len(sym)}", flush=True)
    save_dictionary(outdir, chars, rules, sym)
    with open(os.path.join(outdir, 'meta.json'), 'w') as f:
        json.dump(dict(corpus=args.corpus, num_pairs=args.num_pairs,
                       sample=args.sample, nlines=len(build), runs=True), f)

    char_id = {c: i for i, c in enumerate(chars)}
    plan = make_plan(rules, len(chars))
    full = read_lines(args.corpus, stride=0)
    print(f"tokenising {len(full)} lines", flush=True)
    big, uni = count_adjacency_parallel(full, char_id, plan, len(chars),
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
    full = read_lines(args.corpus, stride=args.stride)
    print(f"tokenising {len(full)} lines (stride {args.stride or 1})", flush=True)
    big, uni = count_adjacency_parallel(full, char_id, plan, len(chars),
                                        jobs=args.jobs)
    write_adj(args.dir, big, uni, sym)
    print(f"adjacency: {len(big)} distinct bigrams, "
          f"N={sum(uni.values())}, N(stop)={uni[len(chars)]}", flush=True)
    print(f"wrote {args.dir}/adj.npz", flush=True)


def cmd_stats(args):
    chars, rules, sym = load_dictionary(args.dir)
    big, uni, V = load_adj(args.dir)
    nruns = sum(1 for r in rules if r[0] == 'run')
    print(f"vocab {V}, rules {len(rules)} ({nruns} run), distinct bigrams "
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
