"""The standard tables, loaded once and shipped inside the package.

Both implementations default to the standardised tables but accept a custom
model file.  This module is the "default" half; pass
``Codec(Model.from_path(path))`` for the other.
"""

import hashlib
import os
import threading

from .codec import Codec
from .model import Model

#: SHA-256 of ``data/model.nvm1``, the standard model of ``docs/STANDARD.md``.
STANDARD_SHA256 = (
    "976670d71a1273a2506bb537183c4854523bec20eb0b2c9708b5934adbef3f79")

_LOCK = threading.Lock()
_STANDARD = None


class StandardCodec(Codec):
    """A :class:`~varnames.codec.Codec` for the standard tables."""

    def __init__(self, model, digest):
        super().__init__(model)
        self.sha256 = digest


def standard():
    """The standard codec, loaded on first use and cached."""
    global _STANDARD
    with _LOCK:
        if _STANDARD is None:
            path = os.path.join(os.path.dirname(__file__), "data", "model.nvm1")
            with open(path, "rb") as f:
                buf = f.read()
            digest = hashlib.sha256(buf).hexdigest()
            if STANDARD_SHA256 and digest != STANDARD_SHA256:
                raise RuntimeError(
                    "the packaged standard model does not match its checksum: "
                    f"{digest} != {STANDARD_SHA256}")
            _STANDARD = StandardCodec(Model.from_bytes(buf), digest)
    return _STANDARD
