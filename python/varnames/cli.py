"""``varnames`` on the command line: encode, decode, inspect.

Examples::

    $ varnames encode getUserName
    getUserName  124101637  27 bits
    $ varnames decode 124101637
    getUserName  27 bits
    $ varnames info
    standard model 976670d7  V=8191 k=32 q=1 alphabet=63 rules=8128

The standard tables ship with the package.  ``--model PATH`` reads any
``NVM1`` file instead, which is how a project pins its own tables (``E9``).
"""

import argparse
import sys

from . import __version__
from .codec import Codec, DecodeError, EncodeError
from .model import Model, ModelError
from .standard import standard


def _codec(args):
    if args.model is None:
        return standard()
    return Codec(Model.from_path(args.model))


def cmd_encode(args):
    codec = _codec(args)
    width = len("identifier")
    status = 0
    for name in args.identifier:
        try:
            value, bits = codec.encode(name)
        except EncodeError as exc:
            print(f"{name}: {exc}", file=sys.stderr)
            status = 1
            continue
        if args.integer:
            print(value)
        elif args.bits:
            print(bits)
        else:
            print(f"{name:<{width}}  {value}  {bits} bits")
    return status


def cmd_decode(args):
    codec = _codec(args)
    width = len("identifier")
    status = 0
    for text in args.code:
        try:
            value = int(text, 0)
        except ValueError:
            print(f"{text}: not an integer", file=sys.stderr)
            status = 1
            continue
        try:
            name = codec.decode(value, args.length)
        except DecodeError as exc:
            print(f"{text}: {exc}", file=sys.stderr)
            status = 1
            continue
        if args.bits:
            print(name.bit_length())
        else:
            print(f"{name:<{width}}  {value.bit_length()} bits")
    return status


def cmd_info(args):
    codec = _codec(args)
    model = codec.model
    digest = getattr(codec, "sha256", "custom")
    print(f"{'standard' if args.model is None else 'custom'} model "
          f"{digest[:8]}  {model.info()}")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(
        prog="varnames",
        description="Encode identifiers as integers with the name code.")
    ap.add_argument("--version", action="version",
                    version=f"%(prog)s {__version__}")
    ap.add_argument("--model", metavar="PATH",
                    help="an NVM1 model file to use instead of the standard "
                         "tables")
    sub = ap.add_subparsers(dest="command", required=True)

    enc = sub.add_parser("encode", help="identifier -> integer")
    enc.add_argument("identifier", nargs="+")
    enc.add_argument("-i", "--integer", action="store_true",
                     help="print only the integer")
    enc.add_argument("-b", "--bits", action="store_true",
                     help="print only the bit length")
    enc.set_defaults(func=cmd_encode)

    dec = sub.add_parser("decode", help="integer -> identifier")
    dec.add_argument("code", nargs="+", help="decimal, or hex with 0x")
    dec.add_argument("-l", "--length", type=int, metavar="BITS",
                     help="reject codes with bits above this length")
    dec.add_argument("-b", "--bits", action="store_true",
                     help="print only the bit length")
    dec.set_defaults(func=cmd_decode)

    info = sub.add_parser("info", help="describe the model in use")
    info.set_defaults(func=cmd_info)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ModelError, OSError) as exc:
        print(f"varnames: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
