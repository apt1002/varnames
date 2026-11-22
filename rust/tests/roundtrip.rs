//! End-to-end tests against a golden file that the Python reference
//! implementation also reads: the two must agree code for code.

use varnames::{Codec, Error, Model};

/// `name value bits`, one per line, produced by the reference implementation.
const GOLDEN: &str = include_str!("../../standard/golden.txt");

fn rows() -> impl Iterator<Item = (&'static str, Option<u128>, usize)> {
    GOLDEN.lines().filter(|line| !line.trim().is_empty()).map(|line| {
        let mut parts = line.split_whitespace();
        let name = parts.next().expect("a name");
        let value = parts.next().expect("a value").parse().ok();
        let bits = parts.next().expect("a length").parse().expect("a number");
        (name, value, bits)
    })
}

#[test]
fn standard_tables_are_the_published_ones() {
    let codec = Codec::default();
    let model = &codec.0;
    assert_eq!(
        (model.num_words(), model.num_lefts(), model.num_rights_per_left()),
        (8_191, 32, 1)
    );
    assert_eq!(model.num_chars(), 63);
    assert_eq!(model.num_rules(), 8_128);
}

#[test]
fn every_golden_code_agrees() {
    let codec = Codec::default();
    let mut short = 0;
    for (name, value, bits) in rows() {
        let bits_value = codec.encode_bits(name).expect("an encodable name");
        assert_eq!(bits_value.len(), bits, "{name}: length");
        if let Some(value) = value {
            let code = codec.encode(name).expect("a code within 128 bits");
            assert_eq!(code, value, "{name}: value");
            assert_eq!(codec.decode(value).expect("a decodable code"), name);
            short += 1;
        }
        assert_eq!(
            codec.decode_bits(&bits_value).expect("a decodable bit string"),
            name,
            "{name}: round trip"
        );
    }
    assert!(short > 150, "only {short} of the golden rows fit in 128 bits");
}

#[test]
fn short_names_are_small() {
    let codec = Codec::default();
    assert!(codec.encode("a").unwrap() < 1 << 8);
    assert!(codec.encode_bits("foo").unwrap().len() < 16);
}

#[test]
fn unknown_characters_are_refused() {
    let codec = Codec::default();
    assert_eq!(codec.encode("hello world"), Err(Error::UnknownCharacter(' ')));
}

#[test]
fn a_custom_model_can_be_loaded() {
    let bytes = std::fs::read(concat!(env!("CARGO_MANIFEST_DIR"), "/data/model.nvm1"))
        .expect("the model file");
    let codec = Codec::new(Model::from_bytes(&bytes).expect("a valid model"));
    assert_eq!(codec.encode("getUserName").unwrap(), 124_101_637);
}

#[test]
fn broken_files_are_refused() {
    assert_eq!(Model::from_bytes(b"nope").unwrap_err(), Error::BadMagic);
    let bytes = std::fs::read(concat!(env!("CARGO_MANIFEST_DIR"), "/data/model.nvm1"))
        .expect("the model file");
    assert!(Model::from_bytes(&bytes[..bytes.len() - 1]).is_err());
    let mut extra = bytes.clone();
    extra.push(0);
    assert!(Model::from_bytes(&extra).is_err());
}
