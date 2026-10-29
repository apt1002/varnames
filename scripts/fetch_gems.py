#!/usr/bin/env python3
"""Download RubyGem .gem archives (latest version of each gem) in parallel.

Usage:
    python3 fetch_gems.py VERSIONS_FILE OUTDIR [--limit N] [--seed S] [--workers W]
"""
import os
import sys
import random
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor


def parse_versions(path, limit, seed):
    gems = []
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("---") or line.startswith("created_at"):
                continue
            parts = line.split(" ")
            if len(parts) < 2:
                continue
            name = parts[0]
            versions = parts[1].split(",")
            latest = versions[-1]
            gems.append((name, latest))
    rng = random.Random(seed)
    rng.shuffle(gems)
    if limit:
        gems = gems[:limit]
    return gems


def download(args):
    name, ver, outdir = args
    dest = os.path.join(outdir, f"{name}-{ver}.gem".replace("/", "%2F"))
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return True
    url = f"https://rubygems.org/downloads/{name}-{ver}.gem"
    r = subprocess.run(
        ["curl", "-sS", "-fL", "--max-time", "60", "-o", dest, url],
        capture_output=True,
    )
    if r.returncode != 0:
        if os.path.exists(dest):
            os.remove(dest)
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("versions")
    ap.add_argument("outdir")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    gems = parse_versions(args.versions, args.limit, args.seed)
    print(f"will fetch {len(gems)} gems -> {args.outdir}", file=sys.stderr)

    ok = 0
    jobs = [(n, v, args.outdir) for n, v in gems]
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, res in enumerate(ex.map(download, jobs), 1):
            ok += res
            if i % 500 == 0:
                print(f"  {i}/{len(jobs)} ({ok} ok)", file=sys.stderr)
    print(f"done: {ok}/{len(jobs)} downloaded", file=sys.stderr)


if __name__ == "__main__":
    main()
