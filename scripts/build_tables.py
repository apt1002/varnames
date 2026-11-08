#!/usr/bin/env python3
"""Build a model file from a corpus of identifiers: the table-building tool.

One command, from identifiers to a `.nvm1` file that the reference and the
engineering implementations can both read:

    build_tables.py --corpus corpus/identifiers.multilang.txt --out build \\
        --V 8192 --k 32

The stages, each of which the other documents describe in full:

  1. **case normalisation** (`CASE_NORMALISATION.md`): split the corpus into
     lower_case / UPPER_CASE / CamelCase, camelise the first two, merge and
     de-duplicate.  `--skip-normalise` starts from a corpus that is already in
     the target form.
  2. **split**: hold out every `--holdout-stride`-th line, so the rate that is
     reported at the end is measured on identifiers the dictionary never saw.
  3. **dictionary and adjacency** (`TREE_WORDS.md`, `DICTIONARY_RULES.md`):
     pair-merge `--words` words from every `--sample`-th training line, then
     count the cyclic word bigrams over the whole training set.  This is the
     expensive stage; it prints its own timings.
  4. **model** (`CLUSTER_WORDS.md`, `HELLINGER_FACTORISATION.md`): co-cluster
     the matrix into `k` left clusters and `q` right clusters each, build the
     Huffman trees, and pack the result (`MODEL_FORMAT.md`).
  5. **check**: read the bytes back with the decoder, round-trip a sample of the
     held-out identifiers and report bits/identifier and the 64/128-bit fit
     rates.

`--V` is the size of the file's alphabet-plus-word space; the number of words is
`V - 1 - (characters in the corpus)`, so `--words` is available instead.  The
shipped standard model is `V = 8,192`, `k = 32`, `q = 1` (`STANDARD.md`), and
`build_standard_model.py` builds that one from an existing dictionary directory.

Nothing here is language-specific except `model_yaml`, and nothing here needs
to be: a port that can read `model.nvm1` can use the tables whatever built
them.

Usage:
    build_tables.py --corpus ids.txt --out build --V 8192 --k 32
    build_tables.py --corpus ids.txt --out build --words 448 --k 8 --sample 1
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import model_fit_rates as mfr  # noqa: E402
import model_size as msz      # noqa: E402
import tree_words as tw       # noqa: E402


def stage(name):
    print(f'--- {name} ---', flush=True)


def run_script(script, *args):
    """Run one of the sibling scripts, whose CLIs are the documented ones."""
    cmd = [sys.executable, os.path.join(HERE, script), *map(str, args)]
    print('  ' + ' '.join([os.path.basename(script), *map(str, args)]),
          flush=True)
    subprocess.run(cmd, check=True)


def normalise(corpus, outdir):
    """Case-normalise the corpus; returns the merged, de-duplicated file."""
    camel = os.path.join(outdir, 'camel')
    os.makedirs(camel, exist_ok=True)
    merged = os.path.join(camel, 'merged.txt')
    run_script('classify_identifiers.py', corpus, camel)
    run_script('camelize_identifiers.py', camel)
    run_script('merge_identifiers.py', camel, merged)
    return merged


def split(merged, outdir, stride):
    """Train / held-out split by line position in the sorted corpus."""
    train = os.path.join(outdir, 'train.txt')
    val = os.path.join(outdir, 'val.txt')
    n_train = n_val = 0
    with open(merged, 'r', encoding='ascii') as src, \
            open(train, 'w', encoding='ascii') as tr, \
            open(val, 'w', encoding='ascii') as va:
        for i, line in enumerate(src):
            if stride and i % stride == 0:
                va.write(line)
                n_val += 1
            else:
                tr.write(line)
                n_train += 1
    print(f'  {n_train:,} training, {n_val:,} held out', flush=True)
    return train, val


def non_ascii_lines(path, limit=5):
    """The first lines holding a non-ASCII byte, and how many there are.

    The model's alphabet is ASCII: a character outside it has no id, no rule
    and no code, so a corpus that uses one cannot be built.  Checking here, on
    bytes, keeps the failure at the entrance instead of letting it surface
    later as a codec error inside the dictionary (`docs/UNICODE.md`).
    """
    bad = []
    n = 0
    with open(path, 'rb') as f:
        for i, line in enumerate(f, 1):
            if line.isascii():
                continue
            n += 1
            if len(bad) < limit:
                bad.append((i, line.rstrip(b'\n')))
    return n, bad


def require_ascii(path):
    n, bad = non_ascii_lines(path)
    if not n:
        return
    examples = '\n'.join(
        f'  line {i}: {s.decode("utf-8", "replace")}' for i, s in bad)
    more = f'\n  … {n - len(bad):,} more' if n > len(bad) else ''
    raise SystemExit(
        f'{path}: {n:,} line(s) contain non-ASCII bytes.\n{examples}{more}\n'
        'The model alphabet is the 63 ASCII characters that occur in\n'
        'identifiers, so a character outside it has no id, no dictionary\n'
        'rule and no codeword.  Transliterate or drop those identifiers\n'
        'before building; how much that leaves out is measured in\n'
        'docs/UNICODE.md.')


def alphabet_of(path, sample):
    """The characters the dictionary will see: sorted, from the sampled lines.

    This is the rule `tree_words.read_corpus_array` applies, reproduced here so
    that `--V` can be turned into a word count before the build starts.
    """
    seen = set()
    with open(path, 'rb') as f:
        for i, line in enumerate(f):
            if sample > 1 and i % sample:
                continue
            s = line.rstrip(b'\n')
            if s:
                seen.update(s)
    return ''.join(sorted(chr(c) for c in seen))


def even_sample(path, limit):
    """Held-out lines spread across the file, at most `limit` of them.

    The corpus is sorted, so a positional prefix is not a sample: the first
    thousand lines of `val.txt` all begin with the same letter.  Take every
    k-th line instead, with k chosen from the file's length.
    """
    if not limit:
        return tw.read_lines(path)
    with open(path, 'rb') as f:
        total = sum(1 for _ in f)
    return tw.read_lines(path, stride=max(1, total // limit), limit=limit)


def check(buf, directory, val_path, limit):
    """Decode the padded bytes, round-trip a sample, report the held-out rate."""
    stage('check')
    m = msz.unpack(buf)
    chars, rules, _sym = tw.load_dictionary(directory)
    nchars = len(chars)
    known = set(chars)
    lines = even_sample(val_path, limit)
    skipped = [s for s in lines if not set(s) <= known]
    lines = [s for s in lines if set(s) <= known]
    seqs = [[msz.to_file_id(s, nchars) for s in seq[:-1]]
            for seq in mfr.tokenise(lines, chars, rules, nchars)]

    lcl = np.asarray(m['memberships'], dtype=np.int64) // ARGS.q
    bottom, top = msz.codes_from(m, lcl)
    bits = []
    for line, seq in zip(lines, seqs):
        b = msz.encode(seq, m, lcl, bottom, top)
        back = msz.decode(b, m, lcl, bottom, top)
        if back != seq:
            raise SystemExit(f'round trip failed on {line!r}')
        bits.append(len(b))
    if not bits:
        print('  no held-out identifier is inside the alphabet', flush=True)
        return dict(n=0)
    bits = np.array(bits)
    if skipped:
        print(f'  skipped {len(skipped)} held-out identifiers with a character '
              f'the dictionary never saw', flush=True)
    rate = dict(n=int(bits.size), mean_bits=float(bits.mean()),
                fit64=float((bits <= 64).mean()),
                fit128=float((bits <= 128).mean()), max_bits=int(bits.max()))
    print(f'  n={rate["n"]:,}  mean {rate["mean_bits"]:.3f} bits  '
          f'fit<=64 {100 * rate["fit64"]:.1f}%  '
          f'fit<=128 {100 * rate["fit128"]:.1f}%  '
          f'max {rate["max_bits"]} bits', flush=True)
    return rate


def main():
    global ARGS
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--corpus', required=True,
                    help='one identifier per line')
    ap.add_argument('--out', required=True,
                    help='directory for the build and the model file')
    size = ap.add_mutually_exclusive_group()
    size.add_argument('--V', type=int, default=8192,
                      help='file symbols, characters and stop included '
                           '(default 8192, the standard)')
    size.add_argument('--words', type=int,
                      help='number of pair-merge words, instead of --V')
    ap.add_argument('--k', type=int, default=32, help='left clusters')
    ap.add_argument('--q', type=int, default=1,
                    help='right clusters per left cluster')
    ap.add_argument('--kappa', type=float, default=300.0,
                    help='prior mass per row')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--sample', type=int, default=20,
                    help='build the dictionary from every Nth line')
    ap.add_argument('--holdout-stride', type=int, default=10,
                    help='hold out every Nth surviving line (0 = none)')
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 1)
    ap.add_argument('--skip-normalise', action='store_true',
                    help='the corpus is already in CamelCase form')
    ap.add_argument('--check-limit', type=int, default=20000,
                    help='held-out identifiers to score (0 = all)')
    ARGS = ap.parse_args()

    os.makedirs(ARGS.out, exist_ok=True)
    t0 = time.time()
    print(f'corpus {ARGS.corpus} -> {ARGS.out}', flush=True)
    require_ascii(ARGS.corpus)

    stage('normalise')
    if ARGS.skip_normalise:
        merged = ARGS.corpus
        print('  skipped', flush=True)
    else:
        merged = normalise(ARGS.corpus, ARGS.out)

    stage('split')
    train_path, val_path = split(merged, ARGS.out, ARGS.holdout_stride)

    stage('dictionary and adjacency')
    chars = alphabet_of(train_path, ARGS.sample)
    nchars = len(chars)
    words = ARGS.words if ARGS.words is not None else ARGS.V - 1 - nchars
    if words < 1:
        raise SystemExit(f'--V {ARGS.V} leaves nothing for words: the corpus '
                         f'has {nchars} characters')
    V = words + 1 + nchars
    directory = os.path.join(ARGS.out, f'tw{V}')
    print(f'  alphabet {nchars} characters, {words} words, V={V}', flush=True)
    ns = argparse.Namespace(corpus=train_path, num_pairs=words,
                            sample=ARGS.sample, stride=0, outdir=directory,
                            jobs=ARGS.jobs)
    tw.cmd_train(ns)

    stage('model')
    m = msz.build_model(directory, ARGS.k, ARGS.q, kappa=ARGS.kappa,
                        seed=ARGS.seed)
    buf, sections = msz.pack(m)

    stage('write')
    path = os.path.join(ARGS.out, 'model.nvm1')
    with open(path, 'wb') as f:
        f.write(buf)
    digest = hashlib.sha256(buf).hexdigest()
    yaml_path = os.path.join(ARGS.out, 'model.yaml')
    with open(yaml_path, 'w', encoding='ascii') as f:
        f.write(msz.model_yaml(m))
    print(f'  {path}: {len(buf):,} bytes, sha256 {digest}', flush=True)
    for name, size_bytes in sections.items():
        if not name.endswith('_bits'):
            print(f'    {name:<16} {size_bytes:>7,}', flush=True)

    rate = check(buf, directory, val_path, ARGS.check_limit)

    with open(os.path.join(ARGS.out, 'build.json'), 'w') as f:
        json.dump(dict(corpus=ARGS.corpus, V=V, words=words, nchars=nchars,
                       k=ARGS.k, q=ARGS.q, kappa=ARGS.kappa, seed=ARGS.seed,
                       sample=ARGS.sample, holdout_stride=ARGS.holdout_stride,
                       normalised=not ARGS.skip_normalise, bytes=len(buf),
                       sha256=digest, held_out=rate,
                       seconds=round(time.time() - t0)), f, indent=2)
    print(f'done in {time.time() - t0:.0f}s; wrote {path}', flush=True)


if __name__ == '__main__':
    main()
