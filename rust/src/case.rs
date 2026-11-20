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
//! The transform is exact: every cased character maps to exactly one character
//! and every other character is copied unchanged, so conversion changes an
//! identifier's length only by the separators it swallows — and within a case
//! class [`from_camel`] inverts [`to_camel`].  Only the class has to travel
//! along with the name, because it is the one thing the normal form drops.
//!
//! The cased characters are the ASCII letters and the letters of
//! `U+00C0–U+017F` and `U+0400–U+052F` that have a 1:1 upper/lower pair; they
//! are listed in `data/case-pairs.txt` (266 pairs, `CC0-1.0`).  Everything
//! else — including the five letters those ranges exclude (`ß İ ı ŉ ſ`),
//! Greek, and every script without case — is **inert**: copied through
//! unchanged and never mapped.

use std::sync::OnceLock;

/// The case class of an identifier, as [`to_camel`] and [`from_camel`] use it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Class {
    /// Cased characters, none of them upper-case.
    Lower,
    /// Cased characters, all of them upper-case.
    Upper,
    /// Already in the normal form: both cases present, or no cased characters.
    Camel,
}

/// The published pair table, compiled into the crate.
const PAIRS: &str = include_str!("../data/case-pairs.txt");

struct Table {
    /// cased character -> XOR of its upper- and lower-case forms, or `0`.
    ///
    /// `0x530` is one past the largest cased code point, `U+052F`.  A pair is
    /// stored only if its two forms differ in their low byte alone, so the XOR
    /// fits in a `u8`; the one exception, `('Ÿ', 'ÿ')`, is left out of the
    /// table and handled by `to_upper_lower`.
    case_xor: [u8; 0x530],
}

impl Table {
    /// The table, parsed from the published pairs on first use.
    fn get() -> &'static Self {
        static TABLE: OnceLock<Table> = OnceLock::new();
        TABLE.get_or_init(|| {
            let mut case_xor = [0u8; 0x530];
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
                if u == 'Ÿ' && l == 'ÿ' {
                    continue;
                }
                assert!(u < l, "{u} < {l}");
                let x = u as u32 ^ l as u32;
                assert!(x < 0x100, "{u} ^ {l} does not fit in a byte");
                case_xor[u as usize] = x as u8;
                case_xor[l as usize] = x as u8;
            }
            Table { case_xor }
        })
    }

    /// `ch` as `(upper-case form, lower-case form)`; an inert character is
    /// returned unchanged as both.
    pub fn to_upper_lower(&self, ch: char) -> (char, char) {
        if ch == 'ÿ' || ch == 'Ÿ' { return ('Ÿ', 'ÿ'); }
        if ch as usize >= self.case_xor.len() { return (ch, ch); }
        let x = self.case_xor[ch as usize] as u32;
        let other = char::from_u32((ch as u32) ^ x).expect("Invalid char");
        if ch < other { (ch, other) } else { (other, ch) }
    }

    /// True when `ch` has a 1:1 case partner, i.e. this module maps it.
    pub fn is_cased(&self, ch: char) -> bool {
        let (u, l) = self.to_upper_lower(ch);
        u != l
    }
}

/// True when `ch` has a 1:1 case partner, i.e. this module maps it.
pub fn cased(ch: char) -> bool {
    Table::get().is_cased(ch)
}

/// Classify an identifier by its cased characters alone.
///
/// Inert characters do not vote: `ßabc` is `Lower`, `Aß` is `Upper` and `aßA`
/// is `Camel`.  A name with no cased characters is `Camel` as well: it is
/// already in the normal form, so there is nothing to convert.
pub fn classify(s: &str) -> Class {
    let table = Table::get();
    let (mut lower, mut upper) = (false, false);
    for ch in s.chars() {
        let (u, l) = table.to_upper_lower(ch);
        lower |= ch != u;
        upper |= ch != l;
    }
    match (lower, upper) {
        (true, false) => Class::Lower,
        (false, true) => Class::Upper,
        _ => Class::Camel,
    }
}

/// Rewrite a `Lower` or `Upper` identifier in CamelCase; `Camel` is unchanged.
///
/// A cased character immediately preceded by an underscore is upper-cased and
/// every other cased character, the leading one included, is lower-cased: `a`
/// stays `a`, and `_a` becomes `A` — upper-cased, and its separator dropped by
/// the next rule — while `__3a` is unchanged because the digit is what precedes
/// the `a`.  A run of underscores followed by a cased character gives up
/// exactly one underscore, its word separator, and keeps the rest, so `a_b`
/// becomes `aB` and `a__b` becomes `a_B`; an underscore not followed by a
/// cased character (before a digit, before an inert character, or at the end)
/// is kept as it is.
pub fn to_camel(s: &str) -> String {
    if classify(s) == Class::Camel {
        return s.to_string();
    }
    let table = Table::get();
    let mut out = String::with_capacity(s.len());
    let mut follows_underscore = false;
    for c in s.chars() {
        let (u, l) = table.to_upper_lower(c);
        if u != l {
            // `c` is cased.
            out.push(if follows_underscore { u } else { l });
        } else {
            // `c` is uncased.
            if follows_underscore {
                out.push('_');
            }
            if c != '_' {
                out.push(c);
            }
        }
        follows_underscore = c == '_';
    }
    if follows_underscore {
        out.push('_');
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
    let is_upper = match class {
        Class::Upper => true,
        Class::Lower => false,
        Class::Camel => { return s.to_string(); },
    };
    let table = Table::get();
    let mut out = String::with_capacity(s.len() + 4);
    for c in s.chars() {
        let (u, l) = table.to_upper_lower(c);
        if c != l {
            // Upper-case letter indicates a separator was removed.
            out.push('_');
        }
        out.push(if is_upper { u } else { l });
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
        let table = Table::get();
        for &(u, l) in &p {
            assert_eq!(table.to_upper_lower(u), (u, l), "to_upper_lower({u})");
            assert_eq!(table.to_upper_lower(l), (u, l), "to_upper_lower({l})");
        }
        // the five letters the range excludes, plus the caseless kra
        for c in ['ß', 'İ', 'ı', 'ŉ', 'ſ', 'ĸ'] {
            assert!(!cased(c), "{c} is inert");
        }
        // and nothing outside the three ranges
        for c in ['Σ', 'σ', 'ς', 'ǅ', 'あ', 'א'] {
            assert!(!cased(c), "{c} is inert");
        }
    }

    /// Test:
    /// - `cased` has class `class`.
    /// - `cased` maps to `camel`.
    /// - `camel` maps to `cased`.
    /// - The number of swallowed underscores is as expected.
    fn classify_and_round_trip(cased: &str, class: Class, camel: &str) {
        assert_eq!(classify(cased), class, "classify({cased})");
        assert_eq!(to_camel(cased), camel, "to_camel({cased})");
        assert_eq!(from_camel(camel, class), cased, "from_camel({camel}, {class:?})");
        if class == Class::Camel {
            assert_eq!(cased, camel);
        } else {
            let table = Table::get();
            let is_upper = |c| c != table.to_upper_lower(c).1;
            let num_swallowed = camel.matches(is_upper).count();
            assert_eq!(
                camel.chars().count() + num_swallowed,
                cased.chars().count(),
                "{cased}: one swallowed underscore per upper-case letter"
            );
        }
    }

    /// Examples of lower- and upper-case names.
    #[test]
    fn upper_and_lower() {
        for (upper, lower, camel) in [
            ("A_B", "a_b", "aB"),
            ("A__B", "a__b", "a_B"),
            ("A_3", "a_3", "a_3"),
            ("A_", "a_", "a_"),
            ("A_B_", "a_b_", "aB_"),
            ("A_3_", "a_3_", "a_3_"),
            ("_ABC", "_abc", "Abc"),
            ("__A", "__a", "_A"),
            ("__3A", "__3a", "__3a"),
            ("_3A", "_3a", "_3a"),
            ("A__3B", "a__3b", "a__3b"),
            ("_A_3B", "_a_3b", "A_3b"),
            ("GET_USER_NAME", "get_user_name", "getUserName"),
            ("FOO_BAR", "foo_bar", "fooBar"),
            ("FOO", "foo", "foo"),
            // accented and cyrillic examples
            ("ÄRGER", "ärger", "ärger"),
            ("_ÄRGER", "_ärger", "Ärger"),
            ("ПРИВЕТ_МИР", "привет_мир", "приветМир"),
            ("DONNÉES_BRUTES", "données_brutes", "donnéesBrutes"),
            // part-inert examples; the inert letters do not vote
            ("STRAßE", "straße", "straße"),
            ("A_日本", "a_日本", "a_日本"),
        ] {
            classify_and_round_trip(upper, Class::Upper, camel);
            classify_and_round_trip(lower, Class::Lower, camel);
        }
    }

    /// Examples of camel-case names.
    #[test]
    fn camel() {
        for camel in [
            "fooBar",
            "Foo",
            "Ärger",
            "_Ärger",
            "ПриветМир",
            "DonnéesBrutes",
            "Straße",
            "Abc",
        ] {
            classify_and_round_trip(camel, Class::Camel, camel);
        }
    }

    /// Examples of caseless names, which are already in the normal form.
    #[test]
    fn caseless() {
        for caseless in [
            "_",
            "123_",
            "_123",
            "Ελληνικά",
        ] {
            classify_and_round_trip(caseless, Class::Camel, caseless);
        }
    }

    /// Synthetic examples of upper- and lower-case names.
    #[test]
    fn chars() {
        for (u, l) in pairs() {
            classify_and_round_trip(&format!("x_{l}y"), Class::Lower, &format!("x{u}y"));
            classify_and_round_trip(&format!("x{l}y"), Class::Lower, &format!("x{l}y"));
            classify_and_round_trip(&format!("X_{u}Y"), Class::Upper, &format!("x{u}y"));
            classify_and_round_trip(&format!("X{u}Y"), Class::Upper, &format!("x{l}y"));
        }
    }

    /// `to_camel` is defined up to the class, so it is not idempotent: `_a`
    /// normalises to `A`, which is upper, so a second pass gives `a`.
    #[test]
    fn to_camel_is_not_idempotent() {
        assert_eq!(to_camel("_a"), "A");
        assert_eq!(classify(&to_camel("_a")), Class::Upper);
        assert_eq!(to_camel("A"), "a");
        assert_eq!(to_camel("__a"), "_A");
    }
}
