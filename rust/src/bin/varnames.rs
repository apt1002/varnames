//! `varnames` on the command line: encode, decode, inspect.

use std::process::ExitCode;

use varnames::{Code, Codec, Error, Model};

const USAGE: &str = "\
usage: varnames [--model PATH] <command> [args...]

commands:
  encode NAME...     identifier -> integer
  decode CODE...     integer -> identifier (decimal, or hex with 0x)
  info               describe the tables in use

options:
  --model PATH       use an NVM1 file instead of the standard tables
  -h, --help         this text
  -V, --version      the version";

fn load(path: Option<&str>) -> Result<Codec, String> {
    match path {
        Some(path) => {
            let buf = std::fs::read(path).map_err(|err| format!("{path}: {err}"))?;
            Model::from_bytes(&buf)
                .map(Codec::new)
                .map_err(|err| format!("{path}: {err}"))
        }
        None => varnames::standard()
            .cloned()
            .map_err(|err| err.to_string()),
    }
}

fn bit_length(value: u128) -> u32 {
    128 - value.leading_zeros()
}

fn main() -> ExitCode {
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    let mut model_path: Option<String> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--model" => {
                if i + 1 == args.len() {
                    eprintln!("varnames: --model needs a path");
                    return ExitCode::from(2);
                }
                model_path = Some(args.remove(i + 1));
                args.remove(i);
                continue;
            }
            _ => i += 1,
        }
    }

    let Some(command) = args.first().map(String::as_str) else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let rest = &args[1..];

    match command {
        "-h" | "--help" | "help" => {
            println!("{USAGE}");
            return ExitCode::SUCCESS;
        }
        "-V" | "--version" => {
            println!("varnames {}", env!("CARGO_PKG_VERSION"));
            return ExitCode::SUCCESS;
        }
        _ => {}
    }

    let codec = match load(model_path.as_deref()) {
        Ok(codec) => codec,
        Err(message) => {
            eprintln!("varnames: {message}");
            return ExitCode::from(2);
        }
    };

    match command {
        "info" => {
            let which = if model_path.is_some() {
                "custom"
            } else {
                "standard"
            };
            println!("{which} model  {}", codec.model().info());
            ExitCode::SUCCESS
        }
        "encode" if !rest.is_empty() => encode(&codec, rest),
        "decode" if !rest.is_empty() => decode(&codec, rest),
        _ => {
            eprintln!("{USAGE}");
            ExitCode::from(2)
        }
    }
}

fn encode(codec: &Codec, names: &[String]) -> ExitCode {
    let mut status = ExitCode::SUCCESS;
    for name in names {
        match codec.encode(name) {
            Ok(Code { value, bits }) => {
                println!("{name:<16}  {value}  {bits} bits")
            }
            Err(Error::CodeTooLong { bits }) => match codec.encode_bits(name) {
                Ok(code) => println!(
                    "{name:<16}  {} bytes  {bits} bits (above 128)",
                    code.as_bytes().len()
                ),
                Err(err) => {
                    eprintln!("{name}: {err}");
                    status = ExitCode::FAILURE;
                }
            },
            Err(err) => {
                eprintln!("{name}: {err}");
                status = ExitCode::FAILURE;
            }
        }
    }
    status
}

fn decode(codec: &Codec, texts: &[String]) -> ExitCode {
    let mut status = ExitCode::SUCCESS;
    for text in texts {
        let parsed = match text.strip_prefix("0x") {
            Some(hex) => u128::from_str_radix(hex, 16),
            None => text.parse::<u128>(),
        };
        let value = match parsed {
            Ok(value) => value,
            Err(_) => {
                eprintln!("{text}: not an integer");
                status = ExitCode::FAILURE;
                continue;
            }
        };
        match codec.decode(value) {
            Ok(name) => println!("{name:<16}  {} bits", bit_length(value)),
            Err(err) => {
                eprintln!("{text}: {err}");
                status = ExitCode::FAILURE;
            }
        }
    }
    status
}
