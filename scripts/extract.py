#!/usr/bin/env python3
"""Streaming identifier extractor for the varnames corpus.

Walks source trees and collects the *distinct* set of programming-language
identifiers matching ``[A-Za-z_][A-Za-z0-9_]*`` (ASCII only), writing shards to
disk so memory stays bounded (~``threshold`` strings).

Lexical noise filtering
-----------------------
A naive tokenizer harvests words from string literals, comments, heredocs and
other non-code text.  That floods the corpus with base64 blobs, PEM
certificates, hex dumps, unicode escape sequences, URLs and English prose.  To
avoid this each file is scrubbed lexically *before* identifiers are collected.
The following regions are recognised and blanked (replaced by spaces, length
preserved):

  strings
    * triple-quoted      \"\"\"...\"\"\"  /  '''...'''
    * ordinary quoted    "..."  /  '...'   (backslash escapes understood)
    * backtick/template  `...`             (JS, Go raw strings, shell)
    * Rust raw strings   r"..."  r#"..."#  br#"..."#
    * Ruby percent       %q(...) %Q[...] %w{...} %i<...> %r|...| etc.
  heredocs
    <<EOS  <<-EOS  <<~EOS  <<'EOS'  <<"EOS"  ... EOS   (Ruby/shell/Perl/PHP)
  comments
    * C-style            // ...   /* ... */
    * hash-style         # ...                      (Python/Ruby/Perl/shell)
  mixed-content markup
    everything outside ``<% %>`` (ERB), ``<script>``/``{{ }}`` (Vue/Svelte)
    or ``<?php ?>`` (PHP) is markup, not source code.

Which constructs are enabled depends on the file extension, so Rust's
``#[derive(Debug)]`` attributes are *not* mistaken for comments, and heredocs
are only looked for in languages that have them.

Numeric literals are blanked whole before tokenising, so the leading digit is
not dropped and its tail does not survive as a bogus identifier
(``0x1f`` -> ``x1f``, ``0b1010`` -> ``b1010``, ``1e6`` -> ``e6``,
``1_000`` -> ``_000``, ``1.0f32`` -> ``f32``).  This removes hexadecimal /
binary / octal data spills and GUID-style constants from generated bindings.

Heredocs are handled in two stages: a cheap first pass finds ``<<TAG`` markers
and their terminator lines and blanks those regions, then the string/comment
scrubber runs over the cleaned bytes.  This avoids rescanning to EOF at every
``<<`` shift operator (Ruby's ``array << item`` idiom).

After scrubbing, identifiers are collected with ``re.findall`` (C speed) instead
of a combined skip|ident alternation, which measured ~2x faster.  Tokens
adjacent to non-ASCII bytes are dropped, so a UTF-8 identifier such as ``café``
does not leak its ASCII prefix ``caf`` into the corpus.

Usage:
    python3 extract.py OUT.shards ROOT [ROOT ...] [--exts ...] [--threshold N]
                                     [--keep-strings] [--keep-comments]
"""
import os
import re
import sys
import argparse

# --- extension families -------------------------------------------------------

RUBY_EXTS = {".rb", ".rake", ".gemspec", ".erb"}
HEREDOC_EXTS = RUBY_EXTS | {
    ".sh", ".bash", ".zsh", ".fish",
    ".pl", ".pm",
    ".php", ".php3", ".php4", ".php5", ".phtml",
}
HASH_COMMENT_EXTS = {
    ".py", ".pyi", ".pyx", ".pxd",
    ".rb", ".rake", ".gemspec", ".erb",
    ".pl", ".pm",
    ".php", ".php3", ".php4", ".php5", ".phtml",
    ".sh", ".bash", ".zsh", ".fish",
    ".r", ".ex", ".exs",
}
C_COMMENT_EXTS = {
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue", ".svelte",
    ".java", ".kt", ".kts", ".scala", ".groovy", ".cs",
    ".go", ".rs", ".swift", ".dart",
    ".php", ".php3", ".php4", ".php5", ".phtml",
}
RUST_EXTS = {".rs"}
PY_EXTS = {".py", ".pyi", ".pyx", ".pxd"}
SHELL_PERL_EXTS = {".sh", ".bash", ".zsh", ".fish", ".pl", ".pm"}

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

# --- lexical fragments (bytes) ------------------------------------------------

IDENT = rb"[A-Za-z_][A-Za-z0-9_]*"
IDENT_RX = re.compile(IDENT)
NONASCII_RUN = re.compile(rb"[A-Za-z0-9_]*[^\x00-\x7f]+[A-Za-z0-9_]*")

_TRIPLE = (
    rb'"""(?:\\[\s\S]|[^\\])*?"""'
    rb"|'''(?:\\[\s\S]|[^\\])*?'''"
)
_QUOTED_SL = (
    rb'"[^"\\\n]*(?:\\[\s\S][^"\\\n]*)*"'
    rb"|'[^'\\\n]*(?:\\[\s\S][^'\\\n]*)*'"
)
_QUOTED_ML = (
    rb'"[^"\\]*(?:\\[\s\S][^"\\]*)*"'
    rb"|'[^'\\]*(?:\\[\s\S][^'\\]*)*'"
)
# Rust has three things with a leading quote: byte/str literals (``b"..."``),
# char literals (``b'\x41'``, ``'\u{1F600}'``) and lifetimes/labels
# (``'a``, ``'_``, ``'static``).  Treating ``'`` as a plain string delimiter
# desynchronises on lifetimes -- ``Cow<'_, [u8]>>(..., "'\\x01020304'::BYTEA")``
# pairs the lifetime quote with the quote inside the string and lets the string
# body leak.  So the single-quote side is split into an exactly-one-char char
# literal and a lifetime token instead.
_RUST_STR = rb'b?"[^"\\]*(?:\\[\s\S][^"\\]*)*"'
_RUST_CHAR = rb"b?'(?:\\(?:x[0-9A-Fa-f]{2}|u\{[0-9A-Fa-f_]+\}|[\s\S])|[^'\\\n])'"
_RUST_LIFETIME = rb"'[A-Za-z_][A-Za-z0-9_]*"
_QUOTED_RUST = _RUST_STR + rb"|" + _RUST_CHAR + rb"|" + _RUST_LIFETIME
_BACKTICK = rb'`(?:\\[\s\S]|[^`\\])*`'
_RUST_RAW = rb'(?<![A-Za-z0-9_])(?:br|r)(?P<rh>#{0,255})"[\s\S]*?"(?P=rh)'
_RUBY_PCT = (
    rb'%[qQwWiIrsx]?\((?:\\[\s\S]|[^)\\])*\)'
    rb'|%[qQwWiIrsx]?\[(?:\\[\s\S]|[^\]\\])*\]'
    rb'|%[qQwWiIrsx]?\{(?:\\[\s\S]|[^}])*\}'
    rb'|%[qQwWiIrsx]?<(?:\\[\s\S]|[^>])*>'
    rb'|%[qQwWiIrsx]?\|(?:\\[\s\S]|[^|\\])*\|'
    rb'|%[qQwWiIrsx]?!(?:\\[\s\S]|[^!\\])*!'
    rb'|%[qQwWiIrsx]?/(?:\\[\s\S]|[^/\\])*/'
)
_C_LINE = rb'//[^\n]*'
_C_BLOCK = rb'/\*(?:[^*]|\*(?!/))*\*/'
_HASH = rb'#[^\n]*'

# Numeric literals whose leading digit is dropped by tokenisation, leaving a
# spurious identifier for the tail of the literal.  A whole literal is blanked
# at the source, which removes both hexadecimal/binary/octal data noise and the
# decimal artefacts:
#
#   0x2a65 -> x2a65   0b1010 -> b1010   0o777 -> o777
#   0x_FF  -> x_FF    0b_1   -> b_1     0o_7  -> o_7     (separator after base)
#   1_000  -> _000    1e6    -> e6      1.5e-10 -> e      (decimal separators,
#   1.e6   -> e6      1.0f32 -> f32    123n -> n           exponents, suffixes)
#   1.0_f32 -> _f32   1_000.000_1 -> _000, _1f64
#
# ``(?<![A-Za-z0-9_])`` keeps identifiers such as ``array1e6`` or ``_1e6``
# intact.  A bare trailing dot (Ruby's ``1.to_s``) is deliberately *not* matched
# unless an exponent follows, so method names after integers are preserved.
_NUMERIC_LITERAL = re.compile(
    rb'(?<![A-Za-z0-9_])'
    rb'(?:'
    rb'0[xX]_?[0-9A-Fa-f][0-9A-Fa-f_]*'                              # 0x1f 0x_FF
    rb'|0[bB]_?[01][01_]*'                                            # 0b1010 0b_1
    rb'|0[oO]_?[0-7][0-7_]*'                                          # 0o777 0o_7
    rb'|(?:[0-9][0-9_]*)?\.[0-9][0-9_]*(?:[eE][+-]?[0-9][0-9_]*)?'    # .5 1.5 1.5e6
    rb'|[0-9][0-9_]*\.[eE][+-]?[0-9][0-9_]*'                          # 1.e6
    rb'|[0-9][0-9_]*(?:[eE][+-]?[0-9][0-9_]*)?'                       # 1 1e6 1_000
    rb')'
    rb'(?:[_A-Za-z][A-Za-z0-9_]*)?'                                   # u8 f32 _u64
)

# --- regex literals (Ruby / Perl) --------------------------------------------
# A bare /.../ or an operator-prefixed m// qr// s/// tr/// y/// form.  Only
# single-line candidates are considered, so a missed close slash cannot swallow
# the rest of the file.  Literal text inside a regex is pattern data, not
# source identifiers, so blanking it is both safe and desirable.  Critically,
# an escaped quote inside a regex (Ruby's ``gsub(/\"/, '')``) would otherwise
# start a runaway multi-line string match and expose distant comments as code.
_REGEX_CAND = re.compile(
    rb'(?<![\w)\]])'
    rb'(?:[msy]|tr|qr)?'
    rb'/(?![/*\n])([^/\n\\]*(?:\\.[^/\n\\]*)*)/[a-z]*'
)
_PERL_SUBST_CAND = re.compile(
    rb'(?<![\w)\]])[sty]r?/'
    rb'([^/\n\\]*(?:\\.[^/\n\\]*)*)/'
    rb'([^/\n\\]*(?:\\.[^/\n\\]*)*)/[a-z]*'
)
_REGEX_SPECIAL = re.compile(rb'[\\\[\]{}|^$*+?]')
_REGEX_LONGRUN = re.compile(rb'[A-Za-z0-9]{12,}')
_REGEX_EXTS = RUBY_EXTS | {".pl", ".pm"}


def _blank_spans(data, spans):
    if not spans:
        return data
    buf = bytearray(data)
    for a, b in spans:
        buf[a:b] = _BLANK.sub(b" ", data[a:b])
    return bytes(buf)


def _looks_like_regex(content):
    """Gate on content so ordinary division is not mistaken for a regex."""
    return bool(_REGEX_SPECIAL.search(content) or _REGEX_LONGRUN.search(content))


def blank_regex_literals(data, ext):
    """Blank single-line regex literals for languages that have them."""
    spans = []
    if ext in {".pl", ".pm"}:
        for m in _PERL_SUBST_CAND.finditer(data):
            if _looks_like_regex(m.group(1)) or _looks_like_regex(m.group(2)):
                spans.append(m.span())
    for m in _REGEX_CAND.finditer(data):
        if _looks_like_regex(m.group(1)):
            spans.append(m.span())
    if not spans:
        return data
    spans.sort()
    merged = [list(spans[0])]
    for a, b in spans[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return _blank_spans(data, [(a, b) for a, b in merged])
_RUBY_BLOCK = (
    rb'(?m:^=begin[^\n]*\n[\s\S]*?^=end[^\n]*)'
    rb'|(?m:^__END__[ \t]*\r?\n[\s\S]*)'
)
_PERL_POD = rb'(?m:^=[A-Za-z][^\n]*\n[\s\S]*?^=cut[^\n]*)'
_PERL_END = rb'(?m:^__(?:END|DATA)__[ \t]*\r?\n[\s\S]*)'

# Mixed-content formats: only these regions contain real source code.  Everything
# outside is markup (HTML/XML/CSS text) whose words are not identifiers.
KEEP_REGION = {
    ".erb": re.compile(rb"<%(?!#)[\s\S]*?%>"),
    ".vue": re.compile(rb"<script\b[\s\S]*?</script>|\{\{[\s\S]*?\}\}"),
    ".svelte": re.compile(rb"<script\b[\s\S]*?</script>|\{\{[\s\S]*?\}\}"),
    ".php": re.compile(rb"<\?(?:php|=)?[\s\S]*?\?>"),
    ".php3": re.compile(rb"<\?(?:php|=)?[\s\S]*?\?>"),
    ".php4": re.compile(rb"<\?(?:php|=)?[\s\S]*?\?>"),
    ".php5": re.compile(rb"<\?(?:php|=)?[\s\S]*?\?>"),
    ".phtml": re.compile(rb"<\?(?:php|=)?[\s\S]*?\?>"),
}

_SKIPPERS = {}

# heredoc marker: <<TAG, <<-TAG, <<~TAG, <<'TAG', <<"TAG"  (no space after <<).
# Trailing code may follow the marker on the same line, e.g. Perl's
# ``return <<'END_BUILTIN_DATA' }`` or shell's ``cat <<EOF > file``.
_HEREDOC_START = re.compile(
    rb'(?<![A-Za-z0-9_])<<[-~]?(["\']?)([A-Za-z_][A-Za-z0-9_]*)\1(?=[^\n]*\r?\n)'
)
_BLANK = re.compile(rb'[^\n]')
_RUBY_BLOCK_RX = re.compile(_RUBY_BLOCK)
_PERL_BLOCK_RX = re.compile(_PERL_POD + rb"|" + _PERL_END)


def blank_matches(data, rx):
    """Blank every region matched by rx (preserve newlines)."""
    spans = [m.span() for m in rx.finditer(data)]
    if not spans:
        return data
    buf = bytearray(data)
    for a, b in spans:
        buf[a:b] = _BLANK.sub(b" ", data[a:b])
    return bytes(buf)


def build_skipper(ext, strip_strings=True, strip_comments=True):
    """Return a regex matching regions to blank, or None if nothing to skip."""
    key = (ext, strip_strings, strip_comments)
    if key in _SKIPPERS:
        return _SKIPPERS[key]

    skip = []
    if strip_strings:
        if ext in PY_EXTS:
            skip.append(_TRIPLE)
            skip.append(_QUOTED_SL)
        elif ext in RUBY_EXTS:
            skip.append(_RUBY_PCT)
            skip.append(_QUOTED_ML)
        elif ext in RUST_EXTS:
            skip.append(_RUST_RAW)
            skip.append(_QUOTED_RUST)
        elif ext in SHELL_PERL_EXTS:
            skip.append(_QUOTED_ML)
        else:
            skip.append(_QUOTED_SL)
        skip.append(_BACKTICK)
    if strip_comments:
        if ext in HASH_COMMENT_EXTS:
            skip.append(_HASH)
        if ext in C_COMMENT_EXTS:
            skip += [_C_BLOCK, _C_LINE]

    rx = re.compile(rb"|".join(skip)) if skip else None
    _SKIPPERS[key] = rx
    return rx


def keep_only(data, rx):
    """Blank every byte outside the regions matched by rx (preserve newlines)."""
    out = bytearray(_BLANK.sub(b" ", data))
    for m in rx.finditer(data):
        a, b = m.span()
        out[a:b] = data[a:b]
    return bytes(out)


def _line_start(data, i):
    j = data.rfind(b"\n", 0, i)
    return 0 if j < 0 else j + 1


def _line_end(data, i):
    j = data.find(b"\n", i)
    return len(data) if j < 0 else j


def find_heredoc_intervals(data):
    """Return sorted, merged [start,end) spans covering heredoc bodies."""
    spans = []
    pos = 0
    n = len(data)
    while pos < n:
        m = _HEREDOC_START.search(data, pos)
        if not m:
            break
        tag = m.group(2)
        start = m.start()
        # terminator: a line that is optional whitespace + tag + optional ws
        search = m.end()
        term_end = None
        while search < n:
            hit = data.find(tag, search)
            if hit < 0:
                break
            ls = _line_start(data, hit)
            le = _line_end(data, hit)
            prefix = data[ls:hit]
            suffix = data[hit + len(tag):le].rstrip(b"\r")
            if prefix.strip() == b"" and suffix.strip() == b"":
                term_end = le
                break
            search = hit + len(tag)
        if term_end is not None:
            spans.append((start, term_end))
            pos = term_end
        else:
            pos = m.end()

    if not spans:
        return spans
    spans.sort()
    merged = [list(spans[0])]
    for a, b in spans[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged]


def scrub(data, ext, strip_strings, strip_comments):
    """Return a same-length copy with non-code regions replaced by spaces."""
    keep = KEEP_REGION.get(ext)
    if keep is not None:
        data = keep_only(data, keep)
    if strip_comments and ext in RUBY_EXTS and (b"=begin" in data or b"__END__" in data):
        data = blank_matches(data, _RUBY_BLOCK_RX)
    if strip_comments and ext in {".pl", ".pm"} and (
            b"=cut" in data or b"__END__" in data or b"__DATA__" in data):
        data = blank_matches(data, _PERL_BLOCK_RX)
    if strip_strings and ext in HEREDOC_EXTS and b"<<" in data:
        intervals = find_heredoc_intervals(data)
        if intervals:
            buf = bytearray(data)
            for a, b in intervals:
                buf[a:b] = _BLANK.sub(b" ", data[a:b])
            data = bytes(buf)
    if strip_strings and ext in _REGEX_EXTS:
        data = blank_regex_literals(data, ext)
    skip_rx = build_skipper(ext, strip_strings, strip_comments)
    if skip_rx is not None:
        data = skip_rx.sub(b" ", data)
    # Numeric literals are blanked *after* strings/comments so that digits
    # inside literals (Rust's ``'\u{1F600}'``, ``b"\x00"``) are not mistaken for
    # code-level numbers -- but before tokenising, so ``0x1f``/``1e6``/``1_000``
    # do not leave ``x1f``/``e6``/``_000`` behind.
    data = blank_matches(data, _NUMERIC_LITERAL)
    if not data.isascii():
        data = NONASCII_RUN.sub(b" ", data)
    return data


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
    ap.add_argument("--keep-strings", dest="strip_strings", action="store_false",
                    help="also harvest identifiers found inside string literals")
    ap.add_argument("--keep-comments", dest="strip_comments", action="store_false",
                    help="also harvest identifiers found inside comments")
    ap.set_defaults(strip_strings=True, strip_comments=True)
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
            for tok in seen:
                shard_fh.write(tok.decode("ascii") + "\n")
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
        ext = os.path.splitext(path)[1].lower()
        clean = scrub(data, ext, args.strip_strings, args.strip_comments)
        found = set(IDENT_RX.findall(clean))
        total_tokens += len(found)
        seen |= found
        if len(seen) >= args.threshold:
            flush()
        if files % 20000 == 0:
            print(f"  scanned {files} files, shard set={len(seen)}", file=sys.stderr)

    flush()
    shard_fh.close()
    print(f"scanned {files} files from {len(args.roots)} roots", file=sys.stderr)


if __name__ == "__main__":
    main()