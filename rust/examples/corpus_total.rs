//! Throwaway: the corpus totals the docs quote.
use varnames::standard::standard;

fn main() {
    let codec = standard().expect("tables");
    let text = std::fs::read_to_string("../corpus/identifiers.multilang.txt").expect("corpus");
    let (mut ids, mut bits) = (0u64, 0u64);
    for name in text.lines() {
        ids += 1;
        bits += codec.encode_bits(name).expect("encodable").len() as u64;
    }
    println!(
        "{ids} identifiers, {bits} bits, {:.4} bits/id",
        bits as f64 / ids as f64
    );
}
