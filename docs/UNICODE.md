# Identifiers outside ASCII

Status: **a survey, not an experiment.** The corpus is ASCII by construction
([`CORPUS.md`](CORPUS.md)), so this note records what that exclusion costs:
two large published studies of how often real code names something outside
ASCII, one local scan that repeats the measurement on a Python tree, and a
read of what the excluded names would take to support. Nothing here changes
the design; the decision and its one-line justification are in
[`ALTERNATIVES.md`](ALTERNATIVES.md).

## 1. What the corpus excludes

An identifier in the corpus matches `[A-Za-z_][A-Za-z0-9_]*`, and the
extractor blanks any run that touches a non-ASCII byte before tokenising, so
`café` disappears whole rather than leaving `caf` behind
([`extract.py`](../scripts/extract.py)). The shipped model therefore carries a
63-character alphabet, and an identifier written in Cyrillic, Han, kana or
accented Latin cannot be coded at all — it has to fall through to the hash
fallback ([`STANDARD.md`](STANDARD.md) §10).

Nothing in the **format** forces this.  The alphabet is a list of characters
stored as UTF-8 ([`MODEL_FORMAT.md`](MODEL_FORMAT.md) §3), and
`build_tables.py` takes its alphabet from every character in the corpus, so a
corpus of your own may contain any of these names: they get ids, rules and
codewords like ASCII ones.  What a non-ASCII alphabet costs is bytes — two a
character for accented Latin, Greek and Cyrillic, three for Han, kana and
Hangul, four for emoji — plus the word list it displaces from `V`.  The
**standard** corpus is ASCII because the extractor blanks non-ASCII runs, and
the shipped model is built from that corpus; that choice is what this note
measures the cost of.

The question this note answers is how large that population is. The short
answer: non-ASCII is common in comments and string literals, uncommon in
identifiers, and rare even in projects whose developers are not writing in
English — because most of them transliterate.

## 2. The trend, in five languages

The largest recent measurement is a 2026 ICSE study of **62,500 GitHub
repositories** in JavaScript, Python, TypeScript, Java and C#, 2015 to May
2025, with language detection over 9.14 billion messages and over the code
itself ([`arXiv:2602.19446`](https://arxiv.org/pdf/2602.19446)). Share of
*files* containing non-English text:

| element | 2015 | 2025 |
|---|---:|---:|
| comments | 3.6 % | 11.9 % |
| string literals | 3.2 % | 9.6 % |
| **identifiers** | **0.14 %** | **0.28 %** |
| variables alone | 0.09 % | 0.28 % |

Function names "remained almost entirely in English" and class names showed
"no measurable use of non-English terms" across the decade. The authors'
explanation is the one that matters here: comments and literals are free
text, while identifiers carry tooling constraints — JavaScript only gained
Unicode identifiers in ES6 (2015), older C++ compilers were incomplete,
keyboards need a layout switch — and review norms push the other way.

Two things make 0.28 % an **upper bound** on non-ASCII identifiers: the
measure is language, not script, so an ASCII name in Spanish (`numero`)
counts as non-English; and their detector was chosen partly because it
recognises transliterations as the language they spell.

Their sample of repositories whose discussion language is Chinese or Russian
(n = 30 each) sharpens the picture: 70 % / 68 % had documentation in the local
language and 40 % / 40 % local-language comments, but local language in *code
elements* appeared mostly in **string literals** — 60 % of the Chinese sample,
28 % of the Russian one. The names stayed English.

## 3. What speakers of non-Latin scripts do

The question "would people use a non-ASCII name if the language allowed it?"
is best answered in Java, which has admitted any Unicode script in identifiers
for decades. Piech and Abu-El-Haija, *Human Languages in Source Code* (L@S
2020, [`arXiv:1909.04556`](https://arxiv.org/pdf/1909.04556)), analysed
**2.9 million public Java repositories** from 1.1 million users:

* 12.7 % of users wrote commit messages in a non-English language; Chinese was
  the largest group, 28.6 % of non-English committers, then Spanish,
  Portuguese, French and Japanese.
* **93 % of projects from Chinese-speaking users have ASCII-only
  identifiers**; among Spanish speakers, 88 %.
* Of those projects that do use their own language, the split between script
  and transliteration is stark: Chinese identifiers are **7 % in Han script,
  93 % transliterated** (pinyin); Spanish identifiers are **11 % accented,
  88 % plain**. Comments are the mirror image — 99 % of Chinese projects have
  non-ASCII comments, 53 % of Spanish ones.
* 82 % of projects from users of non-Latin scripts have only English
  identifiers, against 12 % of projects from Latin-alphabet users: Latin-script
  speakers do write in their own language, but in ASCII.
* Concrete ratios: `numero` is 3.8× more common than `número`; in comments
  `计数` is 4.0× more common than `jishu`, while in identifiers `jishu` is
  4.8× more common than `计数`.

So the dominant behaviour is not "ASCII or nothing" but **transliteration**:
the name is in the developer's language, spelling it in ASCII. That is what
makes an ASCII corpus cheap — it keeps the words and loses only the accents.

## 4. A local scan

To have a number of our own, [`nonascii_scan.py`](../scripts/nonascii_scan.py)
tokenises every `.py` file under a root and counts NAME tokens — the
identifiers exactly, since comments and strings are not NAME tokens — that
contain any non-ASCII character, classifying each by script.

On the Python installed on this machine (132 Debian packages plus the standard
library, **4,605 files**):

| | |
|---|---:|
| identifier tokens | 3,743,600 |
| non-ASCII identifiers | **12** |
| share | 0.0003 % |

All twelve are in one file, `pyparsing/unicode.py`, a Unicode-set library that
aliases three of its classes to `漢字`, `カタカナ` and `ひらがな` and whose
examples name one script each: `中文`, `日本語`, `한국어`, `العربية`,
`Ελληνικά`, `עִברִית`, `ไทย`, `देवनागरी`, `кириллица`. Not one real name in
3.7 million.

The caveat is the corpus, not the method: a Debian server install is
Western-skewed, so this is a floor. It is consistent with the published
numbers — 0.28 % of files, with a few names each, is a fraction of a
percent of identifiers, and here it is three thousandths of one.

## 5. By script

No public census breaks non-ASCII identifiers down by script, so this is the
ranking the evidence supports, with the numbers that exist:

| script | where it appears in code | what the measurements say |
|---|---|---|
| Han, kana | Chinese and Japanese projects | the largest group; 7 % of Chinese-speaker Java projects name in Han, the rest in pinyin or English |
| Hangul | Korean projects | local-language comments rose from 0.27 % to 1.7 % of files in 2015–2025; identifiers stay ASCII |
| Cyrillic | Russian, Ukrainian, Bulgarian | 28 % of the sampled Russian-dominant repos had local language in code elements, "especially literals" |
| Latin with diacritics | Spanish, Portuguese, French, German | 11–12 % of Spanish projects use them in names; 88 % write `numero` instead of `número` |
| Greek | numerical and scientific code | almost always single letters (`α`, `β`, `π`) as mathematics, not natural-language names |
| Arabic, Hebrew | their communities | rare, and right-to-left text in a mixed line is a known rendering hazard |
| Devanagari, Thai, others | their communities | rare; each is a small share even of non-English committers |
| non-letter symbols, emoji | jokes and demonstrations | nearly absent — see below |

## 6. Emoji and other symbols

Emoji are legal identifiers in very few languages, and the constraint is the
character category. Languages that accept "Unicode identifiers" usually mean
**letters and digits** as Unicode defines them — XID_Start and XID_Continue,
which is Python's rule since [PEP 3131](https://peps.python.org/pep-3131/),
JavaScript's since ES6, and Go's. Emoji are symbols, not letters, so they are
excluded. Julia is the conspicuous exception: its identifier rules admit
symbol characters, and `🐱 = 3` compiles. APL-family languages admit their own
symbols for the same reason.

Where emoji names exist they are demonstrations — an "emoji variables" demo
repository, a Stack Overflow question about which emoji a compiler accepts —
and no measurement I could find puts them at even a rounding error of real
code. Supporting them would mean adding the whole `So` category (several
thousand code points, plus modifiers and zero-width joiners) for a population
that is, as far as anyone can measure, zero.

## 7. Why it stays rare

Three forces, all visible in the numbers above:

* **Tooling.** Identifiers are read by editors, diff viewers, debuggers,
  grep, and review tools; a keyboard layout switch interrupts coding; some
  compilers and linters warned against non-ASCII names for years.
* **Review norms.** Open-source projects converge on English APIs and
  ASCII names even when their discussion is in another language, which is the
  82 %-versus-12 % split in §3.
* **Security.** Non-ASCII names can be confusable with ASCII ones: Cyrillic
  `а` in `аpple`, `арр` for `app`. Rust ships `confusable_idents`,
  `mixed_script_confusables` and `uncommon_codepoints` lints for exactly this,
  and [RFC 2457](https://rust-lang.github.io/rfcs/2457-non-ascii-idents.html)
  recommends ASCII identifiers and ASCII-only APIs even while allowing
  Unicode ones.

## 8. What a wider alphabet costs

The format and the builder carry it already (§1); these are the sizes, not a
question of whether it is possible.  The cost is not uniform across scripts:

* **Accented Latin, Greek, Cyrillic** — on the order of a few hundred
  characters (about 60 in Latin-1's letter range, 128 in Latin Ext.-A, 144
  Greek, 256 Cyrillic).  Two bytes each in the alphabet, plus the membership
  label and the depth that every symbol carries — about 1.1 bytes at the
  operating point — so a few hundred characters is 1–2 kB, taken from the
  word list because `V` is fixed.  A 30 kB model absorbs it.
* **Han, kana, Hangul** — 20,992 code points in the base CJK block plus 6,592
  in Extension A, 11,172 Hangul syllables, about 90 kana each.  Three bytes
  each in the alphabet and the same 1.1 bytes of tables, but the count is the
  problem: a modest 3,000 Han would cost about 12 kB and displace a third of
  the word list of a 30 kB model.
* **The dictionary model itself** — a pair-merge dictionary assumes a word is
  a few characters, and an identifier a few words.  In Han, a *word* is one to
  three characters and the alphabet is the vocabulary; the merge rule
  degenerates and the adjacency matrix becomes the model.

Case conversion is a separate question from the alphabet, and it does not
wait for one: `STANDARD.md` §11 defines it over accented Latin and Cyrillic
already, on the caller's corpus and before encoding, so a build from a
non-ASCII corpus can be normalised today.  The alphabet is what the *code* can
spell; the case pairs are what the *builder* can rewrite.

Three names in three scripts are enough to see the alphabet section grow:

```console
$ printf 'café\nкириллица\n日本語\n' > /tmp/ids.txt
$ python3 scripts/build_tables.py --corpus /tmp/ids.txt --out /tmp/uni \
    --V 64 --k 4 --skip-normalise --holdout-stride 0
  …
    alphabet              26
```

That model is 56 bytes and its 13 characters take 26 bytes.  With no repeated
pair in three identifiers there is no rule at all, which the format allows: a
character-only model (`MODEL_FORMAT.md` §2).

## 9. What it means for the standard

The exclusion costs coverage only at the margin: identifiers the model cannot
code fall through to the hash fallback, so nothing becomes unencodable, at the
price of a lookup entry ([`STANDARD.md`](STANDARD.md) §10). The compression
claim is about the other 99.99 %.

## 10. Reproducing the scan

```console
$ python3 scripts/nonascii_scan.py /usr/lib/python3/dist-packages /usr/lib/python3.13
4,605 files under /usr/lib/python3/dist-packages, /usr/lib/python3.13
NAME tokens       3,743,600
non-ASCII NAMEs   12  (0.0003 %)
by script (one count per identifier per script it uses):
  han                      3
  kana                     2
  arabic                   1
  …
```

The script skips `test`, `tests` and `__pycache__` directories, because a test
suite may spell one identifier per script on purpose. Any Python tree works;
point it at a corpus you care about to get that corpus's number.

## 11. Two spellings of one name

`café` is four characters when the `é` is U+00E9 and five when it is `e`
followed by U+0301.  Unicode calls the two spellings canonically equivalent,
and NFC is the transform that composes them.  Whether the compiler agrees is a
property of the host language, and the hosts disagree:

| host | `café` vs `cafe` + U+0301 | why |
|---|---|---|
| Python 3 | **one name** | PEP 3131 normalises identifiers to NFKC |
| Rust | **one name** | `rustc` normalises identifiers to NFC |
| GCC (C) | **two names** | no normalisation; warns by default, `'cafe\U00000301' is not in NFC [-Wnormalized=]` |
| Perl | **two names** | no normalisation |
| Java | **two identifiers** | JLS §3.8: "Unicode composite characters are different from their canonical equivalent decomposed characters" |
| C# | **not a legal identifier** | ECMA-334 requires source identifiers to be in NFC |
| ECMAScript | **two names** | identity is the code-unit sequence; the language normalises nothing |

Python, Rust, GCC and Perl were tested on two spellings of one assignment.
The Java, C# and ECMAScript entries are from their specifications: the JLS
states the rule outright, C# makes the decomposed spelling illegal rather than
a second name, and ECMAScript defines identity as the code-unit sequence.

Two consequences, and they point the same way.

* **NFC is many-to-one, so normalising here would break the bijection.**  The
  claim of `STANDARD.md` §1 is that an identifier has exactly one integer;
  composing the input first would give two spellings one integer and lose the
  distinction silently.  The code is exact or it is nothing, so normalisation
  is the caller's, done before encoding.
* **There is no single host behaviour to adopt.**  Even if the transform were
  invertible, adopting one host's answer would mean choosing between Python's,
  Java's and C#'s, and none of them is *the* answer.

That is why `STANDARD.md` §10 puts identity and normalisation out of scope and
its §11 specifies only case conversion, which is 1:1 on its cased set and therefore
invertible.  A program that needs `café` and `cafe` + U+0301 to be one name
normalises to NFC (or NFD) before it encodes; the code then sees one string, as
it should.
