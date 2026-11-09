#!/usr/bin/env python3
"""Convert non-CamelCase identifiers to CamelCase.

Reads <indir>/lower_case.txt and <indir>/upper_case.txt (produced by
classify_identifiers.py) and rewrites each identifier with the rule:

  * a cased character immediately preceded by an underscore becomes
    upper-case (`_a` -> `_A`), so a digit between them stops it (`__3a`
    stays `__3a`);
  * all other cased characters, including the leading one, become lower-case;
  * a run of underscores immediately followed by a cased character loses
    exactly one underscore (the separator that marks the word start); any
    remaining underscores are kept, so "a_b" -> "aB" but "a__b" -> "a_B".
    Underscores not followed by a cased character (before a digit, before an
    inert character, or at the end) are kept as-is.

"cased" is `STANDARD.md` §11's set: ASCII letters, and the 1:1-paired letters
of U+00C0-U+017F and U+0400-U+052F.  Everything else, Greek included, is inert
and copied through unchanged.  The implementation lives in
`python/varnames/case.py` and is imported here, so the builder and the library
cannot drift.

CamelCase identifiers are already in the target form and are not touched here;
they are merged in unchanged by merge_identifiers.py.

`to_camel` is injective *within* a case class, so it is inverted exactly by
`from_camel(s, cls)`; run `camelize_identifiers.py --check` to verify the
round-trip on `lower_case.txt` / `upper_case.txt`.  Collisions happen only
*across* classes (`_abc` lower, `_ABC` upper and `Abc` CamelCase all normalise to
`Abc`), and the class label disambiguates them.

Output: <indir>/camel_from_lower.txt and <indir>/camel_from_upper.txt,
        one identifier per line.

Usage: camelize_identifiers.py [INDIR]     (default: work/camel)
       camelize_identifiers.py --check [INDIR]   (round-trip self-test)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'python'))
from varnames.case import from_camel, to_camel    # noqa: E402


def convert(infile, outfile):
    n = 0
    with open(infile, encoding='utf-8') as f, open(outfile, 'w', encoding='utf-8') as g:
        for line in f:
            s = line.rstrip('\n')
            if not s:
                continue
            g.write(to_camel(s) + '\n')
            n += 1
    return n


def check(indir):
    """Round-trip `from_camel(to_camel(x), cls) == x` on the class lists."""
    bad = 0
    for cls, fname in (('lower', 'lower_case.txt'), ('upper', 'upper_case.txt')):
        n = 0
        with open(os.path.join(indir, fname), encoding='utf-8') as f:
            for line in f:
                x = line.rstrip('\n')
                if not x:
                    continue
                n += 1
                if from_camel(to_camel(x), cls) != x:
                    bad += 1
                    if bad <= 5:
                        print(f"  collision ({cls}): {x!r}")
        print(f"  {cls}: {n} identifiers, {bad} failures")
    return bad


def main():
    argv = sys.argv[1:]
    if '--check' in argv:
        argv.remove('--check')
        indir = argv[0] if argv else 'work/camel'
        bad = check(indir)
        print('round-trip OK' if not bad else f'{bad} FAILURES')
        raise SystemExit(1 if bad else 0)
    indir = argv[0] if argv else 'work/camel'
    a = convert(os.path.join(indir, 'lower_case.txt'),
                os.path.join(indir, 'camel_from_lower.txt'))
    b = convert(os.path.join(indir, 'upper_case.txt'),
                os.path.join(indir, 'camel_from_upper.txt'))
    print(f"camelized lower_case: {a}  UPPER_CASE: {b}")
    print(f"wrote {os.path.join(indir, 'camel_from_lower.txt')}")
    print(f"wrote {os.path.join(indir, 'camel_from_upper.txt')}")


if __name__ == '__main__':
    main()
