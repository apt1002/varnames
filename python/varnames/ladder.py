"""The rule ladder and the variable-width integer (`MODEL_FORMAT.md` §4).

Both are *static*: the decoder derives every interval edge from `N` alone, so
nothing is stored for the code.
"""

LADDER_B = 3              # index bits; the ladder has 2**b intervals


def ceil_log2(n):
    """Bits needed to hold the values ``0 .. n-1``."""
    if n <= 1:
        return 0
    return (n - 1).bit_length()


def varint(n):
    """Base-128, little-endian (`V = 8191` is ``0xFF 0x3F``)."""
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def read_varint(buf, pos):
    value = shift = 0
    while True:
        b = buf[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            return value, pos


def variable_widths(N):
    """(L, s) for a variable-width integer over ``[0, N)``.

    Values below ``2**L`` take ``L`` bits; the top ``s`` of them also carry a
    zero flag, and the ``s`` values at or above ``2**L`` carry a one flag.
    """
    L = N.bit_length() - 1
    return L, N - (1 << L)


def variable_put(bw, x, N):
    if N <= 1:
        return
    L, s = variable_widths(N)
    if x < (1 << L):
        bw.put(x, L)
        if x >= (1 << L) - s:
            bw.put(0, 1)
    else:
        bw.put(x - s, L)
        bw.put(1, 1)


def variable_get(br, N):
    if N <= 1:
        return 0
    L, s = variable_widths(N)
    v = br.get(L)
    if v < (1 << L) - s:
        return v
    return v if br.get(1) == 0 else v + s


def variable_bits(x, N):
    """Bit count of ``variable_put``; used by the size oracle."""
    if N <= 1:
        return 0
    L, s = variable_widths(N)
    if x < (1 << L):
        return L + (1 if x >= (1 << L) - s else 0)
    return L + 1


def ladder_edges(N, b=LADDER_B):
    """Interval edges of the base-2 geometric ladder over ``[0, N)``.

    ``e_i = N (2**i - 1) // (2**B - 1)`` with ``B = 2**b``, in integers, so the
    decoder computes them from ``N`` and ``b`` with no stored table.
    """
    B = 1 << b
    den = (1 << B) - 1
    return [(N * ((1 << i) - 1)) // den for i in range(B + 1)]


def ladder_interval(x, N, b=LADDER_B):
    """The interval index that holds ``x`` (the last edge at or below it)."""
    edges = ladder_edges(N, b)
    for i in range(len(edges) - 2, -1, -1):
        if x >= edges[i]:
            return i
    return 0


def ladder_put(bw, x, N, b=LADDER_B):
    edges = ladder_edges(N, b)
    i = ladder_interval(x, N, b)
    bw.put(i, b)
    width = max(1, edges[i + 1] - edges[i])
    variable_put(bw, min(max(x - edges[i], 0), width - 1), width)


def ladder_get(br, N, b=LADDER_B):
    edges = ladder_edges(N, b)
    i = br.get(b)
    width = max(1, edges[i + 1] - edges[i])
    return edges[i] + variable_get(br, width)


def ladder_bits(x, N, b=LADDER_B):
    edges = ladder_edges(N, b)
    i = ladder_interval(x, N, b)
    width = max(1, edges[i + 1] - edges[i])
    return b + variable_bits(min(max(x - edges[i], 0), width - 1), width)
