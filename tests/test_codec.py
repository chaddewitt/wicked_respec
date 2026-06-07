# tests/test_codec.py
from src.cerimal.codec import read_varint
from src.cerimal.codec import xxh64
from src.cerimal.codec import WELLKNOWN, decode_primitive, encode_primitive

def test_read_varint_single_byte():
    assert read_varint(bytes([0x05]), 0) == (5, 1)

def test_read_varint_multibyte():
    # 0x80 0x01 => 128 (LEB128 little-endian, 7 bits per byte)
    assert read_varint(bytes([0x80, 0x01]), 0) == (128, 2)

def test_read_varint_offset_and_node_tag():
    # 0x02 at a position => 2 (a concrete node tag), advances by 1
    assert read_varint(bytes([0xFF, 0x02]), 1) == (2, 2)

def test_xxh64_known_vectors():
    assert xxh64(b"") == 0xEF46DB3751D8E999
    assert xxh64(b"abc") == 0x44BC2CF5AD770999

def test_primitive_int_roundtrip():
    b = encode_primitive(5, 16)            # wk 5 = int (4 bytes LE)
    assert b == (16).to_bytes(4, "little")
    assert decode_primitive(5, b) == 16

def test_primitive_fp_scale():
    # wk 17 = FP, real = raw/65536 ; value 10 -> raw 655360
    b = encode_primitive(17, 10)
    assert int.from_bytes(b, "little", signed=True) == 10 * 65536
    assert decode_primitive(17, b) == 10

def test_wellknown_sizes():
    assert WELLKNOWN[2][0] == 1   # byte
    assert WELLKNOWN[5][0] == 4   # int
    assert WELLKNOWN[17][0] == 8  # FP
    assert WELLKNOWN[19][0] == 4  # LFP
