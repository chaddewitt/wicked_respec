# src/cerimal/codec.py
"""Low-level CERIMAL encodings: 7-bit varint, xxHash64, primitive read/write."""

import struct

_M64 = (1 << 64) - 1
_P1 = 0x9E3779B185EBCA87; _P2 = 0xC2B2AE3D27D4EB4F; _P3 = 0x165667B19E3779F9
_P4 = 0x85EBCA77C2B2AE63; _P5 = 0x27D4EB2F165667C5

def _rol(x, r):
    return ((x << r) | (x >> (64 - r))) & _M64

def xxh64(data, seed=0):
    n = len(data); i = 0
    if n >= 32:
        v1 = (seed + _P1 + _P2) & _M64; v2 = (seed + _P2) & _M64
        v3 = seed & _M64; v4 = (seed - _P1) & _M64
        while i + 32 <= n:
            k1, k2, k3, k4 = struct.unpack_from('<QQQQ', data, i)
            v1 = (_rol((v1 + k1 * _P2) & _M64, 31) * _P1) & _M64
            v2 = (_rol((v2 + k2 * _P2) & _M64, 31) * _P1) & _M64
            v3 = (_rol((v3 + k3 * _P2) & _M64, 31) * _P1) & _M64
            v4 = (_rol((v4 + k4 * _P2) & _M64, 31) * _P1) & _M64
            i += 32
        h = (_rol(v1, 1) + _rol(v2, 7) + _rol(v3, 12) + _rol(v4, 18)) & _M64
        for v in (v1, v2, v3, v4):
            v = (_rol((v * _P2) & _M64, 31) * _P1) & _M64
            h = ((h ^ v) * _P1 + _P4) & _M64
    else:
        h = (seed + _P5) & _M64
    h = (h + n) & _M64
    while i + 8 <= n:
        k1 = struct.unpack_from('<Q', data, i)[0]
        k1 = (_rol((k1 * _P2) & _M64, 31) * _P1) & _M64
        h = (_rol(h ^ k1, 27) * _P1 + _P4) & _M64
        i += 8
    if i + 4 <= n:
        k1 = struct.unpack_from('<I', data, i)[0]
        h = (_rol(h ^ (k1 * _P1 & _M64), 23) * _P2 + _P3) & _M64
        i += 4
    while i < n:
        h = (_rol(h ^ (data[i] * _P5 & _M64), 11) * _P1) & _M64
        i += 1
    h ^= h >> 33; h = (h * _P2) & _M64
    h ^= h >> 29; h = (h * _P3) & _M64
    h ^= h >> 32
    return h

def read_varint(buf, pos):
    """LEB128-style 7-bit int, little-endian. Returns (value, new_pos)."""
    val = 0
    shift = 0
    while True:
        b = buf[pos]
        pos += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            return val, pos
        shift += 7

# wk_id -> (size_bytes, signed, scale)
WELLKNOWN = {
    0: (1, False, 1),   # bool
    1: (1, True, 1),    # sbyte
    2: (1, False, 1),   # byte
    3: (2, True, 1),    # short
    4: (2, False, 1),   # ushort
    5: (4, True, 1),    # int
    6: (4, False, 1),   # uint
    7: (8, True, 1),    # long
    8: (8, False, 1),   # ulong
    9: (8, True, 1),    # nint
    10: (8, False, 1),  # nuint
    11: (2, False, 1),  # char
    12: (8, True, 1),   # double (bytes only; not used as target)
    13: (4, True, 1),   # float  (bytes only; not used as target)
    14: (16, False, 1), # decimal
    15: (16, False, 1), # Guid
    17: (8, True, 65536),  # FP
    18: (8, False, 1),     # AssetGuid
    19: (4, True, 65536),  # LFP
}

def decode_primitive(wk_id, raw):
    size, signed, scale = WELLKNOWN[wk_id]
    return int.from_bytes(raw[:size], "little", signed=signed) // scale

def encode_primitive(wk_id, value):
    size, signed, scale = WELLKNOWN[wk_id]
    return int(value * scale).to_bytes(size, "little", signed=signed)
