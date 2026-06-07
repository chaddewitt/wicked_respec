# tests/test_container.py
from src.cerimal.container import split_blocks, parse_header, parse_docs, reseal, verify

def test_split_two_blocks(main_save):
    blocks = split_blocks(main_save)
    assert len(blocks) == 2

def test_header_fields(main_save):
    blocks = split_blocks(main_save)
    h2 = parse_header(main_save, blocks[1][0])
    assert h2["version"] == 3
    assert h2["schema_size"] == 7759
    assert h2["content_size"] == 1862
    assert h2["comp_type"] == 1
    # stored checksum must equal xxh64 over all bytes after byte 28 of the block
    from src.cerimal.codec import xxh64
    s, e = blocks[1]
    assert h2["checksum"] == xxh64(main_save[s + 28:e])

def test_parse_docs_decompresses(main_save, dict_bytes):
    docs = parse_docs(main_save, dict_bytes)
    assert len(docs) == 2
    assert len(docs[0].content) == 295
    assert len(docs[1].content) == 6976
    assert docs[1].schema_size == 7759

def test_reseal_noop_roundtrip_verifies(main_save, dict_bytes):
    # Re-sealing unmodified docs (now uncompressed) must produce a valid file.
    docs = parse_docs(main_save, dict_bytes)
    out = reseal(docs)
    ok, details = verify(out, dict_bytes)
    assert ok, details
    # And decompressing the re-sealed content yields the same bytes we started with.
    docs2 = parse_docs(out, dict_bytes)
    assert bytes(docs2[1].content) == bytes(docs[1].content)
    assert bytes(docs2[0].content) == bytes(docs[0].content)

def test_reseal_all_snapshots(all_saves, dict_bytes):
    import struct
    for name, data in all_saves:
        if not name.endswith(".cerimal") and ".bak" not in name:
            continue
        docs = parse_docs(data, dict_bytes)
        try:
            out = reseal(docs)
        except ValueError as e:
            # Backup files can carry a ContentsChecksum *history*, making the
            # byte-search fallback ambiguous. The authoritative field is the
            # first occurrence (right after the character name); supply it.
            assert "ambiguous" in str(e), f"{name}: unexpected error: {e}"
            old_bytes = struct.pack("<Q", docs[1].original_checksum)
            idx = bytes(docs[0].content).index(old_bytes)
            out = reseal(docs, contents_checksum_offset=idx)
        ok, details = verify(out, dict_bytes)
        assert ok, f"{name}: {details}"

def test_reseal_edit_path_updates_block1_and_verifies(main_save, dict_bytes):
    import struct
    docs = parse_docs(main_save, dict_bytes)
    # main_save has exactly one embedded copy of block 2's checksum in block 1.
    old_c = docs[1].original_checksum
    old_bytes = struct.pack("<Q", old_c)
    assert bytes(docs[0].content).count(old_bytes) == 1
    # Actually change block 2's content so the edit path runs meaningfully.
    docs[1].content[200] ^= 1
    out = reseal(docs)
    ok, details = verify(out, dict_bytes)
    assert ok, details
    # The new block-2 hash must now be embedded (exactly once) in block 1.
    docs2 = parse_docs(out, dict_bytes)
    new_c = docs2[1].original_checksum
    new_bytes = struct.pack("<Q", new_c)
    assert bytes(docs2[0].content).count(new_bytes) == 1
    # And the OLD hash must be gone (it was the only embedded copy).
    assert bytes(docs2[0].content).count(old_bytes) == 0

def test_reseal_accepts_explicit_offset(main_save, dict_bytes):
    import struct
    docs = parse_docs(main_save, dict_bytes)
    old_bytes = struct.pack("<Q", docs[1].original_checksum)
    offset = bytes(docs[0].content).index(old_bytes)
    docs[1].content[200] ^= 1  # force block 2 change so the patch runs
    out = reseal(docs, contents_checksum_offset=offset)
    ok, details = verify(out, dict_bytes)
    assert ok, details
    # The 8 bytes at the explicit offset now hold the new block-2 hash.
    docs2 = parse_docs(out, dict_bytes)
    new_bytes = struct.pack("<Q", docs2[1].original_checksum)
    assert bytes(docs2[0].content)[offset:offset + 8] == new_bytes

def test_reseal_fallback_raises_on_ambiguous(main_save, dict_bytes):
    import struct
    docs = parse_docs(main_save, dict_bytes)
    old_bytes = struct.pack("<Q", docs[1].original_checksum)
    # Force a second copy of the old hash into block 1's content (a fake history
    # entry), so the byte-search fallback finds two occurrences.
    docs[0].content.extend(old_bytes)
    docs[1].content[200] ^= 1  # make block 2 change so the patch branch runs
    import pytest
    with pytest.raises(ValueError, match="ambiguous"):
        reseal(docs)
