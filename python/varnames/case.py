"""Convert between ``foo_bar``, ``FOO_BAR`` and ``fooBar`` (``STANDARD.md`` §11).

The model is trained on one case convention — the standard model on CamelCase —
so an identifier written in another convention codes less well than the same
name in the trained one.  This module rewrites the other two conventions into
CamelCase, and back, so a caller can meet the model where it is:

    >>> from varnames.case import classify, from_camel, to_camel
    >>> to_camel("get_user_name")
    'getUserName'
    >>> from_camel("getUserName", classify("get_user_name"))
    'get_user_name'

The transform is exact.  Every cased character maps to exactly one character,
so conversion never changes an identifier's length, and within a case class
`from_camel` inverts `to_camel`; only the class has to travel along with the
name.  That is why a case class (`'lower'`, `'upper'`, `'camel'`) is an
argument to the inverse and not information hidden in the output.

The cased characters are the ASCII letters and the letters of ``U+00C0–U+017F``
and ``U+0400–U+052F`` that have a 1:1 upper/lower pair; they are listed in
``data/case-pairs.txt`` (266 pairs, ``CC0-1.0``).  Everything else — including
the five letters those ranges exclude (``ß İ ı ŉ ſ``), Greek, and every script
without case — is **inert**: copied through unchanged and never mapped.  A
partly-cased identifier therefore converts consistently rather than half-way,
and a name written in Han or Devanagari is unchanged.
"""

import os

#: ``cased character -> its upper-case form``, and likewise for lower case.
_UPPER = {}
_LOWER = {}


def _load(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            up, lo = line.split()
            _UPPER[up], _LOWER[up] = up, lo
            _UPPER[lo], _LOWER[lo] = up, lo


_load(os.path.join(os.path.dirname(__file__), "data", "case-pairs.txt"))


def cased(ch):
    """True when `ch` has a 1:1 case partner, i.e. this module maps it."""
    return ch in _UPPER


def is_upper(ch):
    """True when `ch` is cased and is its own upper-case form."""
    return _UPPER.get(ch) == ch


def classify(s):
    """Return ``'lower'``, ``'upper'`` or ``'camel'`` for an identifier.

    A class is decided by the cased characters alone: ``'camel'`` has both an
    upper and a lower one, ``'upper'`` has upper ones and no lower ones, and
    everything else — no cased characters at all included — is ``'lower'``.
    Inert characters do not vote.
    """
    lower = upper = False
    for ch in s:
        if ch in _UPPER:
            if _UPPER[ch] == ch:
                upper = True
            else:
                lower = True
    if lower and upper:
        return 'camel'
    if upper:
        return 'upper'
    return 'lower'


def to_camel(s):
    """Rewrite a ``lower`` or ``upper`` identifier in CamelCase.

    The first cased character after a run of underscores is upper-cased and
    every other cased character, the leading one included, is lower-cased.  A
    run of underscores followed by a cased character gives up exactly one
    underscore, its word separator, and keeps the rest, so ``a_b`` → ``aB`` and
    ``a__b`` → ``a_B``; an underscore not followed by a cased character (before
    a digit, before an inert character, or at the end) is kept as it is.  A
    ``camel`` identifier is already in the target form and is returned
    unchanged.
    """
    if classify(s) == 'camel':
        return s
    out = []
    upper = False         # the leading character is *not* capitalised
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == '_':
            j = i
            while j < n and s[j] == '_':
                j += 1
            if j < n and cased(s[j]):
                out.append('_' * (j - i - 1))   # keep all but one underscore
                upper = True                    # next character upper-case
                i = j
                continue
            out.append('_' * (j - i))
            upper = False
            i = j
            continue
        if c in _UPPER:
            out.append(_UPPER[c] if upper else _LOWER[c])
            upper = False
        else:
            out.append(c)
            upper = False
        i += 1
    return ''.join(out)


def from_camel(s, cls):
    """Invert :func:`to_camel` given the identifier's case class.

    In the normalised form an upper-case cased character always marks a
    (possibly invisible, length-1) underscore run directly before it: a run
    followed by a cased character swallowed one underscore and upper-cased that
    character, and a bare upper-case character *is* a swallowed underscore.
    ``'camel'`` is the identity, so ``from_camel(to_camel(x), classify(x)) == x``
    for every identifier.
    """
    if cls == 'camel':
        return s
    if cls not in ('lower', 'upper'):
        raise ValueError("the case class is 'lower', 'upper' or 'camel'")
    fix = _LOWER if cls == 'lower' else _UPPER
    out = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == '_':
            j = i
            while j < n and s[j] == '_':
                j += 1
            m = j - i
            if j < n and is_upper(s[j]):      # run that swallowed a separator
                out.append('_' * (m + 1))
                out.append(fix[s[j]])
                i = j + 1
            else:                             # run not followed by a cased char
                out.append('_' * m)
                i = j
        elif is_upper(c):                     # capitalised: a run hid here
            out.append('_')
            out.append(fix[c])
            i += 1
        else:
            out.append(fix.get(c, c))
            i += 1
    return ''.join(out)
