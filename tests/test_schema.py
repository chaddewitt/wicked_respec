# tests/test_schema.py
from src.cerimal.schema import read_typeref, parse_schema
from src.cerimal.container import parse_docs

def test_typeref_examples():
    # int -> (5<<3)|0 = 0x28, primitive wk 5
    assert read_typeref(bytes([0x28]), 0)[0] == ("prim", 5)
    # int[] rank 1 -> 0x09 then 0x28
    tr, pos = read_typeref(bytes([0x09, 0x28]), 0)
    assert tr == ("array", 1, ("prim", 5)) and pos == 2

def test_parse_schema_finds_target_types(main_save, dict_bytes):
    docs = parse_docs(main_save, dict_bytes)
    table = parse_schema(docs[1].schema_bytes)
    names = {td.name for td in table.types.values()}
    assert "Quantum.CharacterContents" in names or any(
        n.endswith("CharacterContents") for n in names)
    member_names = {m.name for td in table.types.values() for m in td.members}
    assert {"CurrentPoints", "TotalPoints"} <= member_names
    for attr in ("Strength", "Dexterity", "Intelligence", "Faith"):
        assert attr in member_names, attr

def test_parse_schema_both_blocks_all_snapshots(all_saves, dict_bytes):
    """Additional gate: parse_schema must succeed (no desync) on BOTH blocks'
    schema_bytes for ALL snapshots. Block 1 = CharacterMetadata, block 2 =
    CharacterContents. The desync assertion inside _parse_type_record fires if
    any type record's parsed length != its declared total_record_bytes."""
    seen = 0
    for name, data in all_saves:
        if not name.endswith(".cerimal") and ".bak" not in name:
            continue
        docs = parse_docs(data, dict_bytes)
        assert len(docs) == 2, f"{name}: expected 2 blocks"
        for block_idx in (0, 1):
            table = parse_schema(docs[block_idx].schema_bytes)
            # Sanity: at least one type parsed and a root typeref was read.
            assert table.types, f"{name} block {block_idx}: no types parsed"
            assert table.root is not None, f"{name} block {block_idx}: no root"
        seen += 1
    assert seen > 0, "no snapshots exercised"
