//! Case conversion between `foo_bar`, `FOO_BAR` and `fooBar` (`STANDARD.md` §11).
//!
//! The model is trained on one case convention — the standard model on
//! CamelCase — so an identifier written in another convention codes less well
//! than the same name in the trained one.  This module rewrites the other two
//! conventions into CamelCase, and back:
//!
//! ```
//! use varnames::case::{classify, from_camel, to_camel};
//!
//! assert_eq!(to_camel("get_user_name"), "getUserName");
//! assert_eq!(from_camel("getUserName", classify("get_user_name")), "get_user_name");
//! ```
//!
//! The transform is exact: every cased character maps to exactly one
//! character, so conversion never changes an identifier's length, and within a
//! case class [`from_camel`] inverts [`to_camel`].  Only the class has to
//! travel along with the name.
//!
//! The cased characters are the ASCII letters and the letters of
//! `U+00C0–U+017F` and `U+0400–U+052F` that have a 1:1 upper/lower pair; they
//! are listed in `data/case-pairs.txt` (266 pairs, `CC0-1.0`).  Everything
//! else — including the five letters those ranges exclude (`ß İ ı ŉ ſ`),
//! Greek, and every script without case — is **inert**: copied through
//! unchanged and never mapped.

use std::collections::HashMap;
use std::sync::OnceLock;

/// The case class of an identifier, as [`to_camel`] and [`from_camel`] use it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Class {
    /// Cased characters, none of them upper-case (or no cased characters).
    Lower,
    /// Cased characters, all of them upper-case.
    Upper,
    /// Both an upper-case and a lower-case cased character.
    Camel,
}

/// The published pair table, compiled into the crate.
const PAIRS: &str = include_str!("../data/case-pairs.txt");

struct Table {
    /// cased character -> its upper-case form
    upper: HashMap<char, char>,
    /// cased character -> its lower-case form
    lower: HashMap<char, char>,
}

fn table() -> &'static Table {
    static TABLE: OnceLock<Table> = OnceLock::new();
    TABLE.get_or_init(|| {
        let mut upper = HashMap::with_capacity(532);
        let mut lower = HashMap::with_capacity(532);
        for line in PAIRS.lines() {
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let mut fields = line.split_whitespace();
            let (u, l) = match (fields.next(), fields.next(), fields.next()) {
                (Some(u), Some(l), None) => (u, l),
                _ => panic!("every line of case-pairs.txt is `upper lower`"),
            };
            let (u, l) = (
                u.chars().next().expect("one character"),
                l.chars().next().expect("one character"),
            );
            upper.insert(u, u);
            lower.insert(u, l);
            upper.insert(l, u);
            lower.insert(l, l);
        }
        Table { upper, lower }
    })
}

/// True when `ch` has a 1:1 case partner, i.e. this module maps it.
pub fn cased(ch: char) -> bool {
    table().upper.contains_key(&ch)
}

/// True when `ch` is cased and is its own upper-case form.
fn is_upper(ch: char) -> bool {
    table().upper.get(&ch) == Some(&ch)
}

/// Classify an identifier by its cased characters alone.
///
/// Inert characters do not vote: `ßabc` is `Lower`, `Aß` is `Upper` and `aßA`
/// is `Camel`.
pub fn classify(s: &str) -> Class {
    let table = table();
    let (mut lower, mut upper) = (false, false);
    for ch in s.chars() {
        if let Some(&u) = table.upper.get(&ch) {
            if u == ch {
                upper = true;
            } else {
                lower = true;
            }
        }
    }
    match (lower, upper) {
        (true, true) => Class::Camel,
        (false, true) => Class::Upper,
        _ => Class::Lower,
    }
}

/// Rewrite a `Lower` or `Upper` identifier in CamelCase; `Camel` is unchanged.
///
/// A cased character immediately preceded by an underscore is upper-cased and
/// every other cased character, the leading one included, is lower-cased: `a`
/// stays `a`, `_a` becomes `_A`, and `__3a` is unchanged because the digit is
/// what precedes the `a`.  A run of underscores followed by a cased character
/// gives up exactly one underscore, its word separator, and keeps the rest, so
/// `a_b` becomes `aB` and `a__b` becomes `a_B`; an underscore not followed by
/// a cased character (before a digit, before an inert character, or at the
/// end) is kept as it is.
pub fn to_camel(s: &str) -> String {
    if classify(s) == Class::Camel {
        return s.to_string();
    }
    let table = table();
    let chars: Vec<char> = s.chars().collect();
    let mut out = String::with_capacity(s.len());
    let mut upper_next = false;      // the leading character is *not* capitalised
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        if c == '_' {
            let mut j = i;
            while j < chars.len() && chars[j] == '_' {
                j += 1;
            }
            if j < chars.len() && cased(chars[j]) {
                for _ in 0..(j - i - 1) {
                    out.push('_');      // keep all but one underscore
                }
                upper_next = true;      // next character upper-case
            } else {
                for _ in 0..(j - i) {
                    out.push('_');
                }
                upper_next = false;
            }
            i = j;
            continue;
        }
        match table.upper.get(&c) {
            Some(&u) if upper_next => out.push(u),
            Some(_) => out.push(table.lower[&c]),
            None => out.push(c),
        }
        upper_next = false;
        i += 1;
    }
    out
}

/// Invert [`to_camel`] given the identifier's case class.
///
/// In the normalised form an upper-case cased character always marks a
/// (possibly invisible, length-1) underscore run directly before it, so the
/// class is the only thing the caller must remember.  `Class::Camel` is the
/// identity, which makes `from_camel(&to_camel(x), classify(&x)) == x` hold for
/// every identifier.
pub fn from_camel(s: &str, class: Class) -> String {
    if class == Class::Camel {
        return s.to_string();
    }
    let table = table();
    let fix = if class == Class::Lower {
        &table.lower
    } else {
        &table.upper
    };
    let chars: Vec<char> = s.chars().collect();
    let mut out = String::with_capacity(s.len() + 4);
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        if c == '_' {
            let mut j = i;
            while j < chars.len() && chars[j] == '_' {
                j += 1;
            }
            let m = j - i;
            if j < chars.len() && is_upper(chars[j]) {
                for _ in 0..=m {
                    out.push('_');      // the run swallowed one separator
                }
                out.push(fix[&chars[j]]);
                i = j + 1;
            } else {
                for _ in 0..m {
                    out.push('_');
                }
                i = j;
            }
        } else if is_upper(c) {
            out.push('_');              // capitalised: a run hid here
            out.push(fix[&c]);
            i += 1;
        } else {
            out.push(*fix.get(&c).unwrap_or(&c));
            i += 1;
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pairs() -> Vec<(char, char)> {
        PAIRS
            .lines()
            .filter(|l| !l.is_empty() && !l.starts_with('#'))
            .map(|l| {
                let mut f = l.split_whitespace();
                (
                    f.next().unwrap().chars().next().unwrap(),
                    f.next().unwrap().chars().next().unwrap(),
                )
            })
            .collect()
    }

    #[test]
    fn the_table_is_the_published_one() {
        let p = pairs();
        assert_eq!(p.len(), 266);
        assert!(p.contains(&('A', 'a')));
        assert!(p.contains(&('Ä', 'ä')));
        assert!(p.contains(&('Ÿ', 'ÿ')));
        assert!(p.contains(&('А', 'а')));
        // the five letters the range excludes, plus the caseless kra
        for c in ['ß', 'İ', 'ı', 'ŉ', 'ſ', 'ĸ'] {
            assert!(!cased(c), "{c} is inert");
        }
        // and nothing outside the three ranges
        for c in ['Σ', 'σ', 'ς', 'ǅ', 'あ', 'א'] {
            assert!(!cased(c), "{c} is inert");
        }
    }

    #[test]
    fn ascii_behaves_as_before() {
        for (s, want) in [
            ("a_b", "aB"),
            ("a__b", "a_B"),
            ("a_3", "a_3"),
            ("a_", "a_"),
            ("FOO_BAR", "fooBar"),
            ("A_B", "aB"),
            ("_ABC", "Abc"),
            ("__a", "_A"),
            ("__3a", "__3a"),
            ("_3a", "_3a"),
            ("a__3b", "a__3b"),
            ("get_user_name", "getUserName"),
            ("fooBar", "fooBar"),
        ] {
            assert_eq!(to_camel(s), want, "to_camel({s:?})");
        }
        assert_eq!(classify("fooBar"), Class::Camel);
        assert_eq!(classify("FOO"), Class::Upper);
        assert_eq!(classify("foo"), Class::Lower);
        assert_eq!(classify("123_"), Class::Lower);
    }

    #[test]
    fn accented_and_cyrillic_identifiers_convert() {
        assert_eq!(to_camel("ÄRGER"), "ärger");
        assert_eq!(to_camel("_ÄRGER"), "Ärger");
        assert_eq!(to_camel("ПРИВЕТ_МИР"), "приветМир");
        assert_eq!(to_camel("données_brutes"), "donnéesBrutes");
        // a part-inert script is consistent: the inert letter does not vote
        assert_eq!(classify("straße"), Class::Lower);
        assert_eq!(to_camel("straße"), "straße");
        assert_eq!(classify("Ελληνικά"), Class::Lower);
        assert_eq!(to_camel("Ελληνικά"), "Ελληνικά");
        assert_eq!(to_camel("a_日本"), "a_日本");
    }

    #[test]
    fn the_round_trip_is_exact() {
        for (u, l) in pairs() {
            for (name, class) in [
                (format!("x_{l}y"), Class::Lower),
                (format!("x{l}y"), Class::Lower),
                (format!("X_{u}Y"), Class::Upper),
                (format!("X{u}Y"), Class::Upper),
            ] {
                let camel = to_camel(&name);
                assert_eq!(
                    camel.chars().count() + name.matches('_').count(),
                    name.chars().count(),
                    "{name}: one underscore per swallowed separator"
                );
                assert_eq!(from_camel(&camel, class), name);
            }
        }
    }

    #[test]
    fn to_camel_is_idempotent() {
        for s in ["a_b", "A_B", "fooBar", "_ABC", "ÄRGER", "straße", "a_日本"] {
            let once = to_camel(s);
            assert_eq!(to_camel(&once), once, "{s}");
        }
    }
}
