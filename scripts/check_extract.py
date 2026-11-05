#!/usr/bin/env python3
"""Regression tests for the lexical scrubber in `scripts/extract.py`.

Each case is a small source snippet plus the tokens that must **not** survive
(they are inside a literal, comment, heredoc or regex) and the tokens that
**must** survive (they are code).  The cases are the constructs that have leaked
literal data into the corpus at some point — a missed heredoc, a regex with an
apostrophe in it (which flips the quote parity for the rest of the file), a
multi-line `/x` regex, a quoted heredoc tag that is not an identifier, a string
nested inside `#{...}`, and leftover merge-conflict markers.

Usage:
    python3 scripts/check_extract.py            # run all cases
    python3 scripts/check_extract.py -v         # show each case
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract as ex                                            # noqa: E402

CASES = []


def case(ext, source, forbidden, required=(), name=''):
    CASES.append((name or ext, ext, source.encode(), forbidden, required))


# --- Ruby ---------------------------------------------------------------------

case('.rb', r"""
}.to raise_error( /can't modify frozen/i )
UUID = '3f73981a-07bb-11e0-b21a-fb56fb48ba42'
""", ['3f73981a'], ['raise_error', 'UUID'], 'regex with apostrophe, then a string')

case('.rb', r"""
ID = /\A
      (?:[0-9a-f]{8}-[0-9a-f]{4}
      | ffffffff-ffff-ffff-ffff-ffffffffffff
      )\z/ix
value = 1
""", ['ffffffff', 'ffffffffffff'], ['ID', 'value'], 'multi-line /x regex')

case('.rb', r"""
DATA_PATH = 'test/test-data/valid/'
# see http://bugs.example.org/browser/mmd-schema/trunk for the schemas
# License[file:../LICENSE.html] for permissions.
require 'test/unit'
assert_equal '69ee3720-a7cb-4402-b48d-a02c366f2bcf', rg.artist.id.uuid
""", ['69ee3720', 'a02c366f2bcf', 'schemas', 'LICENSE'],
     ['DATA_PATH', 'assert_equal', 'require'],
     'slash-bearing strings and comments must not un-string later code')

case('.rb', r"""
Repo.expects(:fork_bare).with({:bare => true, :template => '/awesome'},
      "#{path}/.git",
      "/foo/bar.git").returns(nil)
assert_equal 'ab25fd8483882c3bda8a458ad2965d2248654335', log.last.id
""", ['ab25fd8483882c3bda8a458ad2965d2248654335', 'awesome'],
     ['assert_equal', 'fork_bare'],
     'regex matcher must not open inside a quoted path')

case('.rb', r"""
rval = YAML.load <<-'5032c8a5-9c5e-ba7a-3804-832a03e16381'
---
uuid: 42329da7-e8ab-29ec-1892-d6a4a964912a
--- 
            5032c8a5-9c5e-ba7a-3804-832a03e16381
after = 2
""", ['42329da7', 'd6a4a964912a'], ['rval', 'after'], 'quoted heredoc tag (UUID)')

case('.rb', r"""
q = "a#{CGI.escape('>=') + "deadbeefdeadbeefdeadbeefdead0"}b"
n = 1
""", ['deadbeefdeadbeefdeadbeefdead0'], ['q', 'n'],
     'string nested in #{...}')

case('.rb', r"""
<<<<<<< HEAD
some_topic = 1
=======
>>>>>>> ccf863516cd6c75a59a22dde092099839482274b
""", ['ccf863516cd6c75a59a22dde092099839482274b'], ['some_topic'],
     'merge-conflict markers')

case('.rb', r"""
entry = {
  'apple-computers' => %w[chernobyl beetlejuice],
  'apple-generateduid' => ['3f73981a-07bb-11e0-b21a-fb56fb48ba42'],
}
""", ['3f73981a', 'chernobyl'], ['entry'], '%w[] array then a quoted string')

case('.rb', r"""
text = <<~EOS
  SQL SELECT * FROM users WHERE id = 1
EOS
def real_method; end
""", ['SELECT', 'users'], ['real_method'], 'squiggly heredoc')

# --- Python -------------------------------------------------------------------

case('.py', '''
x = """not_an_identifier_here"""
y = f"value {real_var} and {other('inner_name')}"
# comment_word
''', ['not_an_identifier_here', 'comment_word', 'real_var', 'inner_name'],
     ['x'], 'triple-quoted string, f-string, comment')

# --- Rust ---------------------------------------------------------------------

case('.rs', r'''
let s = r#"raw string with words"#;
let c = '\u{1F600}';
fn parse_all<'a>(x: &'a str) -> &'a str { x }
''', ['raw', 'string', 'with', 'words'], ['parse_all', 'str'],
     'raw string, char literal, lifetime')

# --- JavaScript ---------------------------------------------------------------

case('.js', r'''
const t = `template ${getName(user)} text`;
// comment_word
function run() { return 1; }
''', ['template', 'text', 'comment_word', 'getName', 'user'],
     ['run'], 'template literal with interpolation')

# --- Perl ---------------------------------------------------------------------

case('.pl', r'''
my $x = <<'END';
data words only
END
sub real_sub { 1 }
=pod
pod words
=cut
''', ['data', 'words', 'pod'], ['real_sub'], 'quoted heredoc and POD')

# --- Shell --------------------------------------------------------------------

case('.sh', r'''
cat <<EOF > out.txt
some text here
EOF
for f in "$dir"/*; do echo "$f"; done
''', ['some', 'text', 'here'], ['out', 'echo'], 'heredoc in shell')

# --- Haskell / OCaml / Lua (harvested later) ----------------------------------

case('.hs', r"""
-- a comment with prose here
x = "string with words" ++ show y
f c = c /= 'a'
""", ['prose', 'string', 'with', 'words'], ['x', 'show', 'y', 'f'],
     'haskell line comment and string')

case('.ml', r"""
(* block comment with prose *)
let f (x : 'a) = "lit words" ^ String.make 1 'z'
""", ['prose', 'lit', 'words'], ['f', 'String', 'make'],
     'ocaml block comment, string, char literal, type variable')

case('.lua', r"""
-- line comment with prose
--[[ block prose here ]]
local s = "str words"
local t = [[long string words]]
local u = [==[ level two ]==]
print(t, u, s)
""", ['prose', 'str', 'long', 'string', 'level'], ['local', 'print'],
     'lua comments, long strings, quotes')

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args()
    bad = 0
    for name, ext, src, forbidden, required in CASES:
        clean = ex.scrub(src, ext, True, True)
        toks = {t.decode('ascii') for t in ex.IDENT_RX.findall(clean)}
        leaked = [t for t in forbidden if t in toks]
        missing = [t for t in required if t not in toks]
        ok = not leaked and not missing
        bad += 0 if ok else 1
        if args.verbose or not ok:
            print(f"{'ok  ' if ok else 'FAIL'} {name} [{ext}]")
            if leaked:
                print(f'       leaked: {leaked}')
            if missing:
                print(f'       lost:   {missing}')
    print(f'{len(CASES)} cases, {bad} failed')
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
