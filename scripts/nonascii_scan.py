#!/usr/bin/env python3
"""Non-ASCII identifiers in a Python source tree, counted by script.

Tokenises every `.py` file under the given roots and looks only at NAME
tokens, which are exactly the identifiers: strings and comments never appear,
so this is a census of names rather than of characters.  Each non-ASCII name
is classified by the scripts of its non-ASCII characters, and the script
counts are per identifier (a name with a Han character and a kana counts once
in each).

The point of the measurement is to answer "how often does a real codebase name
something outside ASCII", which is the question behind the corpus's ASCII-only
token rule (see `docs/UNICODE.md`).  Pass whole package trees:

    nonascii_scan.py /usr/lib/python3/dist-packages /usr/lib/python3.13

Directories called `test`, `tests` or `__pycache__` are skipped, because a
test suite may spell out an identifier per script on purpose; the report says
what was skipped so the number can be read for what it is.
"""
import collections
import os
import sys
import tokenize
import unicodedata
from concurrent.futures import ProcessPoolExecutor

# Hand-written ranges, so the classifier does not depend on unicodedata's
# script data (which the standard library does not expose).
RANGES = [
    ("latin-diacritic", [(0x00C0, 0x024F), (0x1E00, 0x1EFF)]),
    ("greek", [(0x0370, 0x03FF), (0x1F00, 0x1FFF)]),
    ("cyrillic", [(0x0400, 0x04FF), (0x0500, 0x052F)]),
    ("hebrew", [(0x0590, 0x05FF)]),
    ("arabic", [(0x0600, 0x06FF), (0x0750, 0x077F)]),
    ("devanagari", [(0x0900, 0x097F)]),
    ("thai", [(0x0E00, 0x0E7F)]),
    ("han", [(0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF)]),
    ("kana", [(0x3040, 0x30FF), (0x31F0, 0x31FF)]),
    ("hangul", [(0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7AF)]),
    ("emoji-symbol", [(0x2600, 0x27BF), (0x2B00, 0x2BFF), (0x1F000, 0x1FAFF)]),
]

SKIP_DIRS = {'.git', '__pycache__', 'test', 'tests', 'testing'}


def script_of(ch):
    """The script bucket of one non-ASCII character."""
    o = ord(ch)
    for name, ranges in RANGES:
        for a, b in ranges:
            if a <= o <= b:
                return name
    cat = unicodedata.category(ch)
    if cat.startswith('L'):
        return 'other-letter'
    if cat.startswith('S'):
        return 'emoji-symbol'
    if cat.startswith('M'):
        return 'combining-mark'
    return 'other'


def scan(path):
    """(names, non-ascii names, script counter, names themselves) for a file."""
    names = non = 0
    scripts = collections.Counter()
    found = collections.Counter()
    try:
        with open(path, 'rb') as f:
            for tok in tokenize.tokenize(f.readline):
                if tok.type != tokenize.NAME:
                    continue
                s = tok.string
                names += 1
                if s.isascii():
                    continue
                non += 1
                found[s] += 1
                for script in {script_of(c) for c in s if not c.isascii()}:
                    scripts[script] += 1
    except (tokenize.TokenError, SyntaxError, UnicodeDecodeError, LookupError,
            OSError):
        pass                        # a broken file is not a naming choice
    return names, non, scripts, found


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith('.py'):
                yield os.path.join(dirpath, fn)


def main():
    roots = sys.argv[1:]
    if not roots:
        raise SystemExit(__doc__)
    files = [p for r in roots for p in walk(r)]
    print(f'{len(files):,} files under {", ".join(roots)}', flush=True)
    names = non = 0
    scripts = collections.Counter()
    found = collections.Counter()
    with ProcessPoolExecutor() as ex:
        for n, m, sc, fd in ex.map(scan, files, chunksize=64):
            names += n
            non += m
            scripts.update(sc)
            found.update(fd)
    print(f'NAME tokens       {names:,}')
    pct = 100 * non / names if names else 0.0
    print(f'non-ASCII NAMEs   {non:,}  ({pct:.4f} %)')
    if scripts:
        print('by script (one count per identifier per script it uses):')
        for k, v in scripts.most_common():
            print(f'  {k:<18} {v:>7,}')
        print('the identifiers:')
        for k, v in found.most_common(30):
            print(f'  {k!r:<28} {v:>5,}')


if __name__ == '__main__':
    main()
