#!/usr/bin/env python3
"""Harvest source packages for the identifier corpus (Java, Haskell, OCaml, Lua).

Each ecosystem publishes a machine-readable index; this script turns one into a
download plan (package, URL), then downloads, extracts and deletes the archive.

Popularity proxies (Maven Central, Hackage, opam and LuaRocks do not publish
per-package download counts):

* **haskell** — Hackage index (`index.tar.gz`), ranked by the number of packages
  that list it in `build-depends`, i.e. reverse dependencies.
* **ocaml**   — opam `index.tar.gz`, ranked by reverse dependencies from the
  `depends:` fields.
* **lua**     — LuaRocks `manifest`, ranked by the number of published versions
  (the only activity signal the manifest carries).
* **java**    — Maven Central, all `org/apache/**` artifacts with a
  `-sources.jar` (source, not bytecode), capped at `--limit`.

Usage:
    python3 scripts/harvest_packages.py plan haskell --limit 2000
    python3 scripts/harvest_packages.py fetch haskell --limit 2000 --jobs 8

`plan` writes `work/plans/<lang>.tsv`; `fetch` downloads into `work/<lang>_dl/`,
extracts into `work/<lang>_src/<name>/` and removes the archive.  Both are
resumable: existing plan lines and existing source directories are kept.
"""
import argparse
import io
import os
import re
import shutil
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANS = os.path.join(ROOT, 'work', 'plans')
UA = {'User-Agent': 'varnames-corpus-harvester/1.0'}


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read()


def plan_path(lang):
    return os.path.join(PLANS, f'{lang}.tsv')


# ------------------------------------------------------------------ planners --

def _cabal_field(text, field):
    """Value of a cabal field, joining continuation lines."""
    out, on = [], False
    for line in text.splitlines():
        if re.match(rf'^\s*{field}\s*:', line):
            on = True
            out.append(line.split(':', 1)[1])
            continue
        if on:
            if not line.strip():
                continue
            if line[:1].isspace():
                out.append(line)
            else:
                break
    return ' '.join(x.strip() for x in out).strip()


def _dep_names(spec):
    names = []
    for part in spec.split(','):
        m = re.match(r'\s*([A-Za-z][A-Za-z0-9_.-]*)', part)
        if m:
            names.append(m.group(1))
    return names


def _verkey(ver):
    """Sortable key for a version string ('1.2.10-1' -> (1, 2, 10, 1))."""
    out = []
    for part in re.split(r'[.\-+]', ver):
        p = part[1:] if part[:1] in 'vV' and part[1:2].isdigit() else part
        out.append((0, int(p)) if p.isdigit() else (1, p))
    return out


def plan_haskell(limit):
    root = os.path.join(PLANS, 'hackage-index')
    if not os.path.isdir(root):
        raise SystemExit(f'missing {root}; unpack the Hackage index first')
    latest, deps = {}, {}
    for pkg in os.listdir(root):
        pdir = os.path.join(root, pkg)
        if not os.path.isdir(pdir):
            continue
        vers = [v for v in os.listdir(pdir)
                if os.path.isdir(os.path.join(pdir, v))]
        if not vers:
            continue
        ver = max(vers, key=_verkey)
        cabal = os.path.join(pdir, ver, f'{pkg}.cabal')
        if not os.path.isfile(cabal):
            hits = [f for f in os.listdir(os.path.join(pdir, ver))
                    if f.endswith('.cabal')]
            if not hits:
                continue
            cabal = os.path.join(pdir, ver, hits[0])
        with open(cabal, encoding='utf-8', errors='replace') as fh:
            txt = fh.read()
        names = set()
        for f in ('build-depends', 'setup-depends'):
            names |= set(_dep_names(_cabal_field(txt, f)))
        latest[pkg] = ver
        deps[pkg] = names
    revdeps = {}
    for pkg, ds in deps.items():
        for d in ds:
            if d != pkg and d in latest:
                revdeps[d] = revdeps.get(d, 0) + 1
    order = sorted(latest, key=lambda p: (-revdeps.get(p, 0), p))
    order = [p for p in order if revdeps.get(p, 0) >= 1][:limit]
    rows = []
    for pkg in order:
        ver = latest[pkg]
        url = (f'https://hackage.haskell.org/package/{pkg}-{ver}/'
               f'{pkg}-{ver}.tar.gz')
        rows.append((pkg, url))
    return rows, 'revdeps'


def plan_ocaml(limit):
    root = os.path.join(PLANS, 'opam-index', 'packages')
    if not os.path.isdir(root):
        raise SystemExit(f'missing {root}; unpack the opam index first')
    latest, deps, urls = {}, {}, {}
    for pkg in os.listdir(root):
        pdir = os.path.join(root, pkg)
        if not os.path.isdir(pdir):
            continue
        best = None
        for pkgver in os.listdir(pdir):
            if not pkgver.startswith(pkg + '.'):
                continue
            ver = pkgver[len(pkg) + 1:]
            opam = os.path.join(pdir, pkgver, 'opam')
            if not os.path.isfile(opam):
                continue
            if best is None or _verkey(ver) > _verkey(best[0]):
                best = (ver, opam)
        if best is None:
            continue
        ver, opam = best
        with open(opam, encoding='utf-8', errors='replace') as fh:
            txt = fh.read()
        mm = re.search(r'^depends:\s*\[(.*?)^\]', txt, re.S | re.M)
        names = set(re.findall(r'"([A-Za-z0-9_.-]+)"', mm.group(1))) if mm else set()
        names.discard('ocaml')
        um = re.search(r'src:\s*"([^"]+)"', txt)
        latest[pkg] = ver
        deps[pkg] = names
        urls[pkg] = um.group(1) if um else ''
    revdeps = {}
    for pkg, ds in deps.items():
        for d in ds:
            if d != pkg and d in latest:
                revdeps[d] = revdeps.get(d, 0) + 1
    order = sorted(latest, key=lambda p: (-revdeps.get(p, 0), p))[:limit]
    rows = [(pkg, urls.get(pkg, '')) for pkg in order if urls.get(pkg)]
    return rows, 'revdeps'


LUA_KEY_RE = re.compile(r'^(\s*)\["([^"]+)"\]\s*=\s*\{', re.M)


def plan_lua(limit):
    """All LuaRocks packages (the ecosystem is smaller than the cap).

    The manifest nests `repository[rock][version] = {...}`; the parser reads the
    two key depths by indentation (3 spaces = rock, 6 = version), which is how
    the file is generated.
    """
    path = os.path.join(PLANS, 'luarocks_manifest')
    rocks, cur, block = {}, None, None
    with open(path, encoding='utf-8', errors='replace') as fh:
        for ln in fh:
            m = LUA_KEY_RE.match(ln)
            if m:
                ind, name = len(m.group(1)), m.group(2)
                if ind == 3:
                    cur, block = name, None
                    rocks.setdefault(name, {})
                elif ind == 6 and cur is not None:
                    block = name
                    rocks[cur].setdefault(block, '')
                else:
                    block = None
                continue
            if block is not None and 'arch = "src"' in ln:
                rocks[cur][block] = 'src'
    order = sorted((r for r in rocks if any(v == 'src' for v in rocks[r].values())),
                   key=lambda r: (-len(rocks[r]), r))[:limit]
    rows = []
    for rock in order:
        vers = [v for v, kind in rocks[rock].items() if kind == 'src']
        ver = max(vers, key=_verkey)
        rows.append((rock, f'https://luarocks.org/{rock}-{ver}.src.rock'))
    return rows, 'full-ecosystem'


def _maven_list(url):
    return re.findall(r'href="([^"]+)/"', get(url).decode('utf-8', 'replace'))


def plan_java(limit):
    base = 'https://repo1.maven.org/maven2/'
    rows = []
    for group in _maven_list(base + 'org/apache/'):
        if len(rows) >= limit:
            break
        gurl = f'{base}org/apache/{group}/'
        try:
            arts = _maven_list(gurl)
        except (urllib.error.URLError, TimeoutError):
            continue
        for art in arts:
            if len(rows) >= limit:
                break
            aurl = f'{gurl}{art}/'
            try:
                meta = get(aurl + 'maven-metadata.xml').decode('utf-8', 'replace')
            except (urllib.error.URLError, TimeoutError):
                continue
            ver = re.search(r'<release>([^<]+)</release>', meta)
            if not ver:
                continue
            v = ver.group(1)
            jar = f'{aurl}{v}/{art}-{v}-sources.jar'
            rows.append((f'{group}.{art}-{v}', jar))
    return rows[:limit], 'apache'


PLANNERS = {'haskell': plan_haskell, 'ocaml': plan_ocaml,
            'lua': plan_lua, 'java': plan_java}


# --------------------------------------------------------------------- fetch --

def _safe_name(name):
    return re.sub(r'[^A-Za-z0-9_.+-]', '_', name)


def extract(archive, dest):
    """Extract a .tar.gz / .tgz / .zip / .rock archive into `dest`."""
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest)
        return
    try:
        with tarfile.open(archive) as tf:
            for m in tf.getmembers():
                if m.isfile() and '..' not in m.name:
                    tf.extract(m, dest, filter='data')
        return
    except tarfile.TarError:
        pass
    # a LuaRock is a zip with the rockspec plus sources; fall back to zip
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(dest)


def fetch_one(args):
    name, url = args
    dl_dir, src_dir = fetch_one.dl, fetch_one.src
    tag = _safe_name(name)
    dest = os.path.join(src_dir, tag)
    if os.path.isdir(dest) and any(os.scandir(dest)):
        return ('skip', name)
    os.makedirs(dl_dir, exist_ok=True)
    # unique temporary per URL: two packages may share an archive basename
    tmp = os.path.join(dl_dir, f'{tag}-{abs(hash(url)):x}.bin')
    try:
        data = get(url, timeout=120)
        with open(tmp, 'wb') as fh:
            fh.write(data)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return ('fail', f'{name}: {e}')
    os.makedirs(dest, exist_ok=True)
    try:
        extract(tmp, dest)
    except Exception as e:                                  # noqa: BLE001
        shutil.rmtree(dest, ignore_errors=True)
        return ('fail', f'{name}: extract {e}')
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return ('ok', name)


def cmd_plan(args):
    rows, how = PLANNERS[args.lang](args.limit)
    os.makedirs(PLANS, exist_ok=True)
    with open(plan_path(args.lang), 'w', encoding='utf-8') as fh:
        for name, url in rows:
            fh.write(f'{name}\t{url}\n')
    print(f'{args.lang}: {len(rows)} packages written to {plan_path(args.lang)} '
          f'(ranked by {how})')


def cmd_fetch(args):
    lang = args.lang
    fetch_one.lang = lang
    fetch_one.dl = os.path.join(ROOT, 'work', f'{lang}_dl')
    fetch_one.src = os.path.join(ROOT, 'work', f'{lang}_src')
    os.makedirs(fetch_one.dl, exist_ok=True)
    os.makedirs(fetch_one.src, exist_ok=True)
    rows = []
    with open(plan_path(lang), encoding='utf-8') as fh:
        for line in fh:
            name, url = line.rstrip('\n').split('\t')
            rows.append((name, url))
    if args.limit:
        rows = rows[:args.limit]
    ok = fail = skip = 0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for i, (status, msg) in enumerate(pool.map(fetch_one, rows), 1):
            if status == 'ok':
                ok += 1
            elif status == 'skip':
                skip += 1
            else:
                fail += 1
                if fail <= 20:
                    print(f'  fail {msg}', file=sys.stderr)
            if i % 200 == 0:
                print(f'  {i}/{len(rows)}: ok {ok}, skip {skip}, fail {fail}',
                      file=sys.stderr)
    print(f'{lang}: {ok} fetched, {skip} already present, {fail} failed')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('plan', 'fetch'):
        p = sub.add_parser(name)
        p.add_argument('lang', choices=sorted(PLANNERS))
        p.add_argument('--limit', type=int, default=2000)
        p.add_argument('--jobs', type=int, default=8)
        p.set_defaults(func=cmd_plan if name == 'plan' else cmd_fetch)
    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
