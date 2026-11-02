#!/usr/bin/env python3
"""Convert non-CamelCase identifiers to CamelCase.

Reads <indir>/lower_case.txt and <indir>/upper_case.txt (produced by
classify_identifiers.py) and rewrites each identifier with the rule:

  * the first letter after a run of underscores becomes upper-case;
  * all other letters, including the leading letter of the identifier, become
    lower-case;
  * a run of underscores immediately followed by a letter loses exactly one
    underscore (the separator that marks the word start); any remaining
    underscores are kept, so "a_b" -> "aB" but "a__b" -> "a_B".  Underscores
    not followed by a letter (before a digit, or at the end) are kept as-is.

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


def _is_letter(ch):
    return ('a' <= ch <= 'z') or ('A' <= ch <= 'Z')


def to_camel(s):
    out = []
    upper = False         # the leading letter is *not* capitalised
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == '_':
            j = i
            while j < n and s[j] == '_':
                j += 1
            if j < n and _is_letter(s[j]):
                out.append('_' * (j - i - 1))   # keep all but one underscore
                upper = True                    # next letter upper-case
                i = j
                continue
            out.append('_' * (j - i))
            upper = False
            i = j
            continue
        if _is_letter(c):
            out.append(c.upper() if upper else c.lower())
            upper = False
        else:
            out.append(c)
            upper = False
        i += 1
    return ''.join(out)


def from_camel(s, cls):
    """Invert `to_camel` given the identifier's case class (`'lower'`/`'upper'`).

    `to_camel` is injective within a class, so this recovers the original exactly
    from its CamelCase form plus the class.  In the normalised form an uppercase
    letter always marks a (possibly invisible, length-1) underscore run directly
    before it: `to_camel` swallows one underscore of a run that precedes a letter
    and capitalises that letter.
    """
    fix = str.lower if cls == 'lower' else str.upper
    out = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == '_':
            j = i
            while j < n and s[j] == '_':
                j += 1
            m = j - i
            if j < n and 'A' <= s[j] <= 'Z':     # run that swallowed a separator
                out.append('_' * (m + 1))
                out.append(fix(s[j]))
                i = j + 1
            else:                                 # run not followed by a letter
                out.append('_' * m)
                i = j
        elif 'A' <= c <= 'Z':                     # capitalised: a run hid here
            out.append('_')
            out.append(fix(c))
            i += 1
        elif _is_letter(c):
            out.append(fix(c))
            i += 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def convert(infile, outfile):
    n = 0
    with open(infile) as f, open(outfile, 'w') as g:
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
        with open(os.path.join(indir, fname)) as f:
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
