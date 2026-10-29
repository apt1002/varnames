#!/usr/bin/env python3
"""Unpack .gem archives (a tar containing data.tar.gz) into a source tree.

Usage: python3 unpack_gems.py INDIR OUTDIR
"""
import os
import sys
import tarfile


def main():
    indir, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    done = 0
    for name in sorted(os.listdir(indir)):
        if not name.endswith(".gem"):
            continue
        path = os.path.join(indir, name)
        dst = os.path.join(outdir, name[:-4])
        if os.path.isdir(dst):
            continue
        try:
            with tarfile.open(path, "r") as outer:
                member = outer.extractfile("data.tar.gz")
                if member is None:
                    continue
                with tarfile.open(fileobj=member, mode="r:gz") as inner:
                    inner.extractall(dst, filter="data")
            done += 1
        except Exception as e:
            print(f"skip {name}: {e}", file=sys.stderr)
        if done % 1000 == 0 and done:
            print(f"  unpacked {done}", file=sys.stderr)
    print(f"unpacked {done} gems -> {outdir}", file=sys.stderr)


if __name__ == "__main__":
    main()
