#!/usr/bin/env python3
"""Leave-one-piece-out ablations, measured in the packed harness.

Every arm changes one thing about the shipped model and is scored the same way:
pack the model to `model.nvm1`, decode the held-out identifiers through the
packed file, and report **bytes**, **mean bits** and the **64/128-bit fit
rates**.  The arms:

    base            the shipped configuration (V=8,192, k=32, q=1, kappa=300)
    k=16, k=64      the cluster count, at the same vocabulary
    kappa=30/3000   the prior strength
    q=2             two right clusters per left cluster
    stop weighted   the top trees built with the stop's true mass, so the
                    terminator has to be coded instead of arriving as padding
    5-bit depths     no depth-flattening bias, so a depth needs five bits
                    instead of four; that is a different file, so only its
                    bits are measured
    no case norm.   a dictionary built on the raw corpus instead of the
                    normalised one, scored on the identifiers normalisation
                    leaves unchanged (the only ones both models can code
                    identically)
    k = V           clustering off: one right cluster per word, at a
                    vocabulary small enough to cost about what the shipped
                    model costs

The last two arms need their own dictionaries, which takes minutes: the case
arm from `--raw-corpus`, the flat arm from `--flat-corpus`.  The rest reuse an
existing dictionary directory.

    ablation.py --dir work/tw8192ns
    ablation.py --dir work/tw8192ns --raw-corpus corpus/identifiers.multilang.txt
    ablation.py --dir work/tw8192ns --flat 240

The measurements land in `docs/ABLATION.md`.  Nothing here is a research
script: it exists to answer "what is each piece worth" in one table, and the
notes it cites carry the design arguments.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'python'))

import model_fit_rates as mfr   # noqa: E402
import model_size as msz        # noqa: E402
import tree_words as tw         # noqa: E402
from varnames.case import classify, to_camel    # noqa: E402


# --------------------------------------------------------------- measuring

def heldout_lines(path, stride):
    return tw.read_lines(path, stride=stride)


def score(buf, lines, chars, rules, charge_stop=False):
    """Bytes, held-out bits and fit rates of a packed model.

    `charge_stop` counts the terminator explicitly: the encoder writes the
    stop's codeword and only its trailing zeros are dropped, which is what a
    model without the zero-weight stop has to do.
    """
    m = msz.unpack(buf)
    nchars = len(chars)
    known = set(chars)
    lines = [s for s in lines if s and set(s) <= known]
    seqs = [[msz.to_file_id(s, nchars) for s in seq[:-1]]
            for seq in mfr.tokenise(lines, chars, rules, nchars)]
    lcl = np.asarray(m['memberships'], dtype=np.int64) // m['q']
    bottom, top = msz.codes_from(m, lcl)
    bits = []
    for line, seq in zip(lines, seqs):
        b = msz.encode(seq, m, lcl, bottom, top, write_stop=charge_stop)
        if charge_stop:                     # the stop's own trailing zeros
            while b and b[-1] == 0:
                b.pop()
        if msz.decode(b, m, lcl, bottom, top) != seq:
            raise SystemExit(f'round trip failed on {line!r}')
        bits.append(len(b))
    bits = np.array(bits)
    return dict(bytes=len(buf), n=int(bits.size),
                mean_bits=float(bits.mean()),
                fit64=float((bits <= 64).mean()),
                fit128=float((bits <= 128).mean()),
                max_bits=int(bits.max()))


def bits_only(m, lines, chars, rules, charge_stop=False):
    """Mean bits of a model that cannot be packed (no comparison of bytes)."""
    nchars = len(chars)
    known = set(chars)
    lines = [s for s in lines if s and set(s) <= known]
    seqs = [[msz.to_file_id(s, nchars) for s in seq[:-1]]
            for seq in mfr.tokenise(lines, chars, rules, nchars)]
    lcl = np.asarray(m['memberships'], dtype=np.int64) // m['q']
    bottom, top = msz.codes_from(m, lcl)
    bits = []
    for seq in seqs:
        b = msz.encode(seq, m, lcl, bottom, top, write_stop=charge_stop)
        if charge_stop:
            while b and b[-1] == 0:
                b.pop()
        bits.append(len(b))
    bits = np.array(bits)
    return dict(n=int(bits.size), mean_bits=float(bits.mean()),
                fit64=float((bits <= 64).mean()),
                fit128=float((bits <= 128).mean()),
                max_bits=int(bits.max()))


def row(name, what, res, base=None, fmt='{:,}'):
    """One table row; `res` may carry only an estimate of the bytes."""
    b = res.get('bytes', res.get('bytes_estimate'))
    bb = None if base is None else \
        base.get('bytes', base.get('bytes_estimate'))

    def delta(x):
        # the table uses a real minus sign, as the notes do
        return x.replace('-', '\u2212')

    d_bytes = '\u2014' if bb is None else delta(f"{b - bb:+,}")
    d_bits = '\u2014' if base is None else \
        delta(f"{res['mean_bits'] - base['mean_bits']:+.3f}")
    d_fit = '\u2014' if base is None else \
        delta(f"{100 * (res['fit64'] - base['fit64']):+.1f}")
    bytes_s = '\u2014' if b is None else fmt.format(b)
    return (f"| {name} | {what} | {bytes_s} | {d_bytes} | "
            f"{res['mean_bits']:.3f} | {d_bits} | "
            f"{100 * res['fit64']:.1f} % | {d_fit} |")


# ------------------------------------------------------- the raw-corpus arm

def normalise(s):
    """The pipeline's normalisation of one identifier: `to_camel`, which is the
    identity on a CamelCase name (`STANDARD.md` §11)."""
    return to_camel(s)


def raw_arm(raw_corpus, normalised_val, outdir, V, sample, jobs):
    """Build a dictionary + model on the raw corpus, matched to the same split.

    A raw line is held out iff its normalised form is in the normalised
    held-out set, so the two arms are blind to the same identifiers and only
    the case convention differs.  The arm is scored on the raw held-out lines
    that normalisation leaves unchanged, which is the only subset both models
    can code identically.
    """
    import build_tables as bt

    os.makedirs(outdir, exist_ok=True)
    held = set(tw.read_lines(normalised_val))
    train_path = os.path.join(outdir, 'train.txt')
    val_path = os.path.join(outdir, 'val.txt')
    n_tr = n_va = 0
    with open(raw_corpus, 'r', encoding='utf-8') as src, \
            open(train_path, 'w', encoding='utf-8') as tr, \
            open(val_path, 'w', encoding='utf-8') as va:
        for line in src:
            s = line.rstrip('\n')
            if not s:
                continue
            if normalise(s) in held:
                va.write(s + '\n')
                n_va += 1
            else:
                tr.write(s + '\n')
                n_tr += 1
    print(f'  raw arm: {n_tr:,} training, {n_va:,} held out', flush=True)

    chars = tw.alphabet_of(train_path)
    nchars = len(chars)
    words = V - 1 - nchars
    directory = os.path.join(outdir, f'tw{V}')
    ns = argparse.Namespace(corpus=train_path, num_pairs=words,
                            sample=sample, stride=0, outdir=directory,
                            jobs=jobs)
    tw.cmd_train(ns)
    m = msz.build_model(directory, 32, 1, kappa=300.0, seed=1)
    buf, _ = msz.pack(m)
    lines = [s for s in tw.read_lines(val_path) if classify(s) == 'camel']
    _chars, rules, _sym = tw.load_dictionary(directory)
    return dict(buf=buf, lines=lines, directory=directory, chars=_chars,
                rules=rules)


def flat_arm(corpus, V, outdir, sample, jobs, stride, seed):
    """A model with no clustering: `k = V`, so each right cluster is a word.

    The vocabulary has to be small, because the top stage is `V` trees of
    `V + 1` leaves and grows as `V²/2` bytes.  `V = 240` lands at about the
    shipped file's size.  The corpus is the normalised one, split the same way
    the standard was, so the held-out identifiers are the same.
    """
    import build_tables as bt

    os.makedirs(outdir, exist_ok=True)
    train_path, _val = bt.split(corpus, outdir, stride)
    chars = tw.alphabet_of(train_path)
    nchars = len(chars)
    words = V - 1 - nchars
    if words < 1:
        raise SystemExit(f'--flat {V} leaves nothing for words: the corpus '
                         f'has {nchars} characters')
    directory = os.path.join(outdir, f'tw{V}')
    ns = argparse.Namespace(corpus=train_path, num_pairs=words,
                            sample=sample, stride=0, outdir=directory,
                            jobs=jobs)
    tw.cmd_train(ns)
    m = msz.build_model(directory, V, 1, kappa=300.0, seed=seed)
    buf, _ = msz.pack(m)
    _chars, rules, _sym = tw.load_dictionary(directory)
    return dict(buf=buf, chars=_chars, rules=rules, V=V, words=words)


# ------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir', default='work/tw8192ns',
                    help='dictionary directory the arms build from')
    ap.add_argument('--validation', default='work/camel/merged_validation.txt')
    ap.add_argument('--stride', type=int, default=10)
    ap.add_argument('--k', type=int, default=32)
    ap.add_argument('--q', type=int, default=1)
    ap.add_argument('--kappa', type=float, default=300.0)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--json', help='write the table to this path as JSON')
    ap.add_argument('--raw-corpus',
                    help='also run the case-normalisation arm on this corpus')
    ap.add_argument('--raw-out', default='build/ablation_raw',
                    help='working directory for the raw-corpus arm')
    ap.add_argument('--flat', type=int, metavar='V',
                    help='also build a flat model: k = V, one right cluster '
                         'per word, at V symbols')
    ap.add_argument('--flat-corpus', default='work/camel/merged.txt',
                    help='normalised corpus the flat model is built from')
    ap.add_argument('--flat-stride', type=int, default=10,
                    help='held-out stride for the flat build (the standard)')
    ap.add_argument('--flat-out', default='build/ablation_flat',
                    help='working directory for the flat arm')
    ap.add_argument('--sample', type=int, default=20)
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 1)
    args = ap.parse_args()

    chars, rules, _sym = tw.load_dictionary(args.dir)
    lines = heldout_lines(args.validation, args.stride)
    print(f'{args.dir}: {len(lines):,} held-out identifiers', flush=True)

    res = {}

    def run(name, what, m, charge_stop=False):
        t0 = time.time()
        buf, _ = msz.pack(m)
        r = score(buf, lines, chars, rules, charge_stop=charge_stop)
        r['seconds'] = round(time.time() - t0, 1)
        res[name] = dict(res=r, what=what)
        print(f'  {name:<16} {r["bytes"]:>7,} B  {r["mean_bits"]:.3f} bits  '
              f'{100 * r["fit64"]:.1f} %', flush=True)

    base = msz.build_model(args.dir, args.k, args.q, kappa=args.kappa,
                           seed=args.seed)
    run('base', 'the shipped configuration', base)

    prepared = msz.prepared_matrix(args.dir, args.kappa)
    for k in (16, 64):
        if k == args.k:
            continue
        m = msz.build_model(args.dir, k, args.q, kappa=args.kappa,
                            seed=args.seed, prepared=prepared)
        run(f'k={k}', f'left clusters {args.k} → {k}', m)
    for kappa in (30.0, 3000.0):
        if kappa == args.kappa:
            continue
        m = msz.build_model(args.dir, args.k, args.q, kappa=kappa,
                            seed=args.seed)
        run(f'kappa={kappa:g}', f'prior strength {args.kappa:g} → {kappa:g}', m)
    if args.q == 1:
        m = msz.build_model(args.dir, args.k, 2, kappa=args.kappa,
                            seed=args.seed, prepared=prepared)
        run('q=2', 'two right clusters per left cluster', m)

    m = msz.build_model(args.dir, args.k, args.q, kappa=args.kappa,
                        seed=args.seed, prepared=prepared, stop_weight=True)
    run('stop weighted', 'the stop given its true mass and coded', m,
        charge_stop=True)

    t0 = time.time()
    mb = msz.build_model(args.dir, args.k, args.q, kappa=args.kappa,
                         seed=args.seed, prepared=prepared, bias=False)
    r = bits_only(mb, lines, chars, rules)
    # five-bit depths instead of four: one extra bit per leaf, and a new file
    V, k = mb['V'], mb['k']
    extra = (V + k * (k * mb['q'] + 1) + 7) // 8
    r['bytes_estimate'] = len(msz.pack(base)[0]) + extra
    r['seconds'] = round(time.time() - t0, 1)
    res['5-bit depths'] = dict(res=r, what='no depth bias; five bits a depth')
    print(f'  5-bit depths     {r["bytes_estimate"]:>7,} B (five-bit field)  '
          f'{r["mean_bits"]:.3f} bits  {100 * r["fit64"]:.1f} %', flush=True)

    if args.raw_corpus:
        t0 = time.time()
        raw = raw_arm(args.raw_corpus, args.validation, args.raw_out,
                      V=8192, sample=args.sample, jobs=args.jobs)
        r = score(raw['buf'], raw['lines'], raw['chars'], raw['rules'])
        r['seconds'] = round(time.time() - t0, 1)
        res['no case norm.'] = dict(
            res=r, what='dictionary built on the raw corpus')
        print(f'  no case norm.    {r["bytes"]:>7,} B  '
              f'{r["mean_bits"]:.3f} bits  {100 * r["fit64"]:.1f} %',
              flush=True)
        # the normalised arm on exactly the same identifiers
        nb = msz.pack(base)[0]
        rn = score(nb, raw['lines'], chars, rules)
        res['case norm.'] = dict(res=rn, what='the same identifiers, '
                                             'normalised model')
        print(f'  case norm.       {rn["bytes"]:>7,} B  '
              f'{rn["mean_bits"]:.3f} bits  {100 * rn["fit64"]:.1f} %',
              flush=True)

    if args.flat:
        t0 = time.time()
        fm = flat_arm(args.flat_corpus, args.flat, args.flat_out, args.sample,
                      args.jobs, args.flat_stride, args.seed)
        r = score(fm['buf'], lines, fm['chars'], fm['rules'])
        r['seconds'] = round(time.time() - t0, 1)
        if r['n'] != res['base']['res']['n']:
            print(f'  note: the flat arm scored {r["n"]:,} identifiers, '
                  f'not {res["base"]["res"]["n"]:,}', flush=True)
        name = f'k = V = {fm["V"]}'
        res[name] = dict(
            res=r, what=f'clustering off, {fm["words"]} words, one tree '
                        f'per word')
        print(f'  {name:<16} {r["bytes"]:>7,} B  {r["mean_bits"]:.3f} bits  '
              f'{100 * r["fit64"]:.1f} %', flush=True)

    print('\n| arm | what changes | bytes | Δ bytes | mean bits | Δ bits '
          '| fit ≤64 | Δ fit (pt) |')
    print('|---|---|---:|---:|---:|---:|---:|---:|')
    for name, item in res.items():
        # the case arms are compared with each other, on their own identifier
        # set: their deltas are not differences from the shipped row
        if name == 'base':
            ref = None
        elif name in ('no case norm.', 'case norm.'):
            ref = res['case norm.']['res']
        else:
            ref = res['base']['res']
        print(row(name, item['what'], item['res'], base=ref,
                  fmt='~{:,}' if 'bytes_estimate' in item['res']
                  and 'bytes' not in item['res'] else '{:,}'))

    if args.json:
        with open(args.json, 'w') as f:
            json.dump({name: dict(what=item['what'], **item['res'])
                       for name, item in res.items()}, f, indent=2)
        print(f'\nwrote {args.json}')


if __name__ == '__main__':
    main()
