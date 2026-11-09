"""varnames — encode programming-language identifiers as integers.

The model is a small Huffman code over the words an identifier is built from.
Encoding is a bijection on everything the model can spell; identifiers it
cannot (too long, or using characters outside the alphabet) are the caller's to
handle — the 64- and 128-bit sets are simply ``value < 2**64`` and
``value < 2**128``.

    >>> import varnames
    >>> codec = varnames.standard()
    >>> value, bits = codec.encode("getUserName")
    >>> codec.decode(value)
    'getUserName'

Both numbers matter: ``value`` is what you store, ``bits`` is where its highest
bit lands, which is what the 64-bit budget counts (``ENCODING.md`` §2).

The model is trained on CamelCase; :mod:`varnames.case` converts the other two
conventions to it and back, exactly (``STANDARD.md`` §11).
"""

from .case import cased, classify, from_camel, to_camel
from .codec import Codec, DecodeError, EncodeError
from .model import Model, ModelError
from .standard import STANDARD_SHA256, StandardCodec, standard

__all__ = [
    "Codec",
    "DecodeError",
    "EncodeError",
    "Model",
    "ModelError",
    "STANDARD_SHA256",
    "StandardCodec",
    "cased",
    "classify",
    "from_camel",
    "to_camel",
    "standard",
]
__version__ = "0.1.0"
