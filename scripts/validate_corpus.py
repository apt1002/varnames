#!/usr/bin/env python3
"""Validate a corpus identifier list.

Checks, for each file given on the command line:
  * every line matches ^[A-Za-z_][A-Za-z0-9_]*$ (ASCII identifiers only)
  * no empty lines
  * the list is sorted and unique (``LC_ALL=C`` byte order)
  * reports residual numeric-literal artefacts and hex/base64-style noise

Usage:  python3 scripts/validate_corpus.py FILE [FILE ...]
"""
import re
import sys

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Suspect shapes that usually mean a numeric literal or an escaped byte run
# leaked into the corpus (``0x1f`` -> ``x1f``, ``0b1010`` -> ``b1010``,
# ``1_000`` -> ``_000``, ``1e6`` -> ``e6``, ``\x01020304`` -> ``x01020304``).
ARTIFACTS = re.compile(
    r"^(?:"
    r"[xbo]_?[0-9A-Fa-f]{2,}"          # base-prefixed hex/bin/oct tail
    r"|_[0-9][0-9_]*"                  # decimal separator tail
    r"|[eE][0-9]{1,}"                  # exponent tail
    r"|[iuf][0-9]+"                    # Rust/int-float suffix
    r"|[A-Za-z][0-9A-Fa-f]{10,}"       # very long hex-ish tail
    r")$"
)
PURE_HEX = re.compile(r"^[0-9A-Fa-f]+$")


def main():
    status = 0
    for path in sys.argv[1:]:
        total = bad = empty = arts = unsorted = 0
        prev = None
        seen = set()
        pure_hex = 0
        with open(path, "r", encoding="ascii", errors="strict") as fh:
            for line in fh:
                tok = line.rstrip("\n")
                total += 1
                if not tok:
                    empty += 1
                    continue
                if not IDENT.match(tok):
                    bad += 1
                    if bad <= 5:
                        print(f"  BAD TOKEN: {tok!r}")
                if prev is not None and tok <= prev:
                    unsorted += 1
                    if unsorted <= 5:
                        print(f"  NOT SORTED/UNIQUE: {prev!r} -> {tok!r}")
                prev = tok
                if ARTIFACTS.match(tok):
                    arts += 1
                    if arts <= 8:
                        print(f"  suspicious (may be legit): {tok!r}")
                if len(tok) >= 12 and PURE_HEX.match(tok):
                    pure_hex += 1
        flags = []
        if bad:
            flags.append(f"{bad} bad")
        if empty:
            flags.append(f"{empty} empty")
        if unsorted:
            flags.append(f"{unsorted} unsorted/dup")
        if arts:
            flags.append(f"{arts} artefact-like")
        if pure_hex:
            flags.append(f"{pure_hex} pure-hex>=12")
        mark = "FAIL" if (bad or empty or unsorted) else "ok"
        print(f"{mark:4} {path}: {total} lines"
              + (f" -- {', '.join(flags)}" if flags else ""))
        if bad or empty or unsorted:
            status = 1
    sys.exit(status)


if __name__ == "__main__":
    main()
