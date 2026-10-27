#!/usr/bin/env python3
"""Convert non-CamelCase identifiers to CamelCase.

Reads <indir>/lower_case.txt and <indir>/upper_case.txt (produced by
classify_identifiers.py) and rewrites each identifier with the rule:

  * the first letter after a run of underscores becomes upper-case;
  * all other letters, including the leading letter of the identifier, become
    lower-case;
  * a run of underscores immediately followed by a letter loses exactly one
    underscore (the separator that marks the word start); any remaining
    underscores are kept, so "a_b" -> "AB" but "a__b" -> "A_B".  Underscores
    not followed by a letter (before a digit, or at the end) are kept as-is.

CamelCase identifiers are already in the target form and are not touched here;
they are merged in unchanged by merge_identifiers.py.

Output: <indir>/camel_from_lower.txt and <indir>/camel_from_upper.txt,
        one identifier per line.

Usage: camelize_identifiers.py [INDIR]   (default: work/camel)
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


def main():
    indir = sys.argv[1] if len(sys.argv) > 1 else 'work/camel'
    a = convert(os.path.join(indir, 'lower_case.txt'),
                os.path.join(indir, 'camel_from_lower.txt'))
    b = convert(os.path.join(indir, 'upper_case.txt'),
                os.path.join(indir, 'camel_from_upper.txt'))
    print(f"camelized lower_case: {a}  UPPER_CASE: {b}")
    print(f"wrote {os.path.join(indir, 'camel_from_lower.txt')}")
    print(f"wrote {os.path.join(indir, 'camel_from_upper.txt')}")


if __name__ == '__main__':
    main()
