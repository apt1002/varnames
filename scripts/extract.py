#!/usr/bin/env python3
"""Streaming identifier extractor for the varnames corpus.

Walks source trees, tokenizes files for programming-language identifiers that
match `[A-Za-z_][A-Za-z0-9_]*` (ASCII), and writes the *distinct* set to disk
without ever holding more than ~`threshold` strings in memory.

Strategy: keep a global set; when it exceeds `threshold`, sort its keys and
append them to a shard file, then clear. At the end, `sort -m -u` the shards.

Usage:
    python3 extract.py OUT.shards ROOT [ROOT ...] [--exts ...] [--threshold N]
"""
import os
import re
import sys
import argparse

IDENT = re.compile(rb"[A-Za-z_][A-Za-z0-9_]*")

DEFAULT_EXTS = {
    # namespace-rich, source-bearing languages we care about.
    # (ASCII, identifier-friendly, and *not* C-style prefix-only languages.)
    ".py", ".pyi", ".pyx", ".pxd",
    ".rb", ".rake", ".gemspec", ".erb",
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue", ".svelte",
    ".java", ".kt", ".kts", ".scala", ".groovy", ".cs",
    ".go", ".rs", ".swift", ".dart",
    ".pl", ".pm", ".php", ".php3", ".php4", ".php5", ".phtml",
    ".lua", ".ex", ".exs", ".clj", ".cljs", ".hs", ".ml", ".lisp", ".scm", ".r",
    ".sh", ".bash", ".zsh", ".fish",
}


def walk_files(roots, exts):
    for root in roots:
        if os.path.isfile(root):
            yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # skip obvious vcs / vendored noise
            dirnames[:] = [d for d in dirnames if d not in (".git", ".svn", ".hg")]
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext in exts:
                    yield os.path.join(dirpath, fn)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shards")
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--threshold", type=int, default=2_000_000)
    ap.add_argument("--exts", default="")
    args = ap.parse_args()

    exts = set(DEFAULT_EXTS)
    if args.exts:
        exts = {e if e.startswith(".") else "." + e for e in args.exts.split(",")}

    shard_fh = open(args.shards, "w", encoding="utf-8")
    seen = set()
    files = 0
    total_tokens = 0

    def flush():
        nonlocal seen
        if seen:
            for tok in sorted(seen):
                shard_fh.write(tok + "\n")
            seen = set()

    for path in walk_files(args.roots, exts):
        try:
            with open(path, "rb") as fh:
                head = fh.read(65536)
                if b"\x00" in head:
                    continue
                data = head + fh.read()
        except OSError:
            continue
        files += 1
        found = set(IDENT.findall(data))
        total_tokens += len(found)
        seen |= {t.decode("ascii") for t in found}
        if len(seen) >= args.threshold:
            flush()
        if files % 20000 == 0:
            print(f"  scanned {files} files, shard set={len(seen)}", file=sys.stderr)

    flush()
    shard_fh.close()
    print(f"scanned {files} files from {len(args.roots)} roots", file=sys.stderr)


if __name__ == "__main__":
    main()
