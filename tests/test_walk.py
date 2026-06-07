# tests/test_walk.py
import pytest

from src.cerimal.container import parse_docs
from src.cerimal.schema import parse_schema
from src.cerimal.walk import (
    walk_primitives, locate_primitives, locate_attribute_values,
    walk_strings, character_name,
)
from src.cerimal.codec import decode_primitive


def _is_save(name):
    return name.endswith(".cerimal") or ".bak" in name


def test_walk_block2_consumes_exactly_all_content(all_saves, dict_bytes):
    """Gate 1a: walking block 2 (CharacterContents) consumes EXACTLY len(content)."""
    for name, data in all_saves:
        if not _is_save(name):
            continue
        docs = parse_docs(data, dict_bytes)
        table = parse_schema(docs[1].schema_bytes)
        prims, end = walk_primitives(table, docs[1].content)
        assert end == len(docs[1].content), \
            f"{name} block2: walked {end}/{len(docs[1].content)}"


def test_walk_block1_consumes_exactly_all_content(all_saves, dict_bytes):
    """Gate 1b: walking block 1 (CharacterMetadata) consumes EXACTLY len(content)."""
    for name, data in all_saves:
        if not _is_save(name):
            continue
        docs = parse_docs(data, dict_bytes)
        table = parse_schema(docs[0].schema_bytes)
        prims, end = walk_primitives(table, docs[0].content)
        assert end == len(docs[0].content), \
            f"{name} block1: walked {end}/{len(docs[0].content)}"


ATTR_NAMES = ("Strength", "Dexterity", "Intelligence", "Faith",
              "Focus", "Stamina", "Health", "ItemLoad")


def test_locate_targets_and_invariant(main_save, dict_bytes):
    """Gate 2: locate the attribute fields; the point-funded set satisfies the
    respec invariant.

    Empirically verified against the real schema (NOT the design doc's earlier
    raw-string reconnaissance): the 8 attributes are stored as the *values* of an
    enum-keyed dictionary (``Attributes`` map, ``EnumMap<AttributeType, int>``),
    so the walker labels each value with its ``AttributeType`` variant name and
    they become locatable by name (``Strength`` ...).

    ``CurrentPoints``/``TotalPoints`` live ONLY in ``SerializedPlayerClassData``,
    reached through ``ClassData.Classes`` - a ``List`` that is EMPTY in every
    fixture, so those fields are absent from block-2 content here. The invariant
    ``Σ(attr − base) == TotalPoints − CurrentPoints`` is therefore asserted only
    when both fields are present (other saves / future states with a class
    selected); on these fixtures we assert their documented absence instead.
    """
    docs = parse_docs(main_save, dict_bytes)
    table = parse_schema(docs[1].schema_bytes)
    found = locate_primitives(table, docs[1].content)

    def val(name):
        r = found[name]
        return decode_primitive(r.wk_id, docs[1].content[r.offset:r.offset + r.width])

    # The enum-keyed dict walk must surface all 8 attributes by name.
    attrs = {a: val(a) for a in ATTR_NAMES if a in found}
    assert set(attrs) == set(ATTR_NAMES), f"missing attributes: {set(ATTR_NAMES) - set(attrs)}"

    base = 10
    spent = sum(v - base for v in attrs.values() if v > base)
    # The point-funded total for the main save is 9 (Strength 19 -> +9).
    assert spent == 9, attrs

    if "CurrentPoints" in found and "TotalPoints" in found:
        # Full invariant: only reachable when a class is selected (Classes list
        # non-empty). Kept live so it runs on such saves.
        assert val("TotalPoints") - val("CurrentPoints") == spent, \
            (attrs, val("TotalPoints"), val("CurrentPoints"))
    else:
        # Documented reality for these fixtures: empty Classes list.
        assert "CurrentPoints" not in found and "TotalPoints" not in found


def test_attribute_invariant_consistent_across_snapshots(all_saves, dict_bytes):
    """The point-funded total is internally consistent (spend == 9) on every
    fixture, by whichever attributes are raised - proving the enum-keyed walk
    finds the right fields regardless of which attribute carries the points."""
    for name, data in all_saves:
        if not _is_save(name):
            continue
        docs = parse_docs(data, dict_bytes)
        table = parse_schema(docs[1].schema_bytes)
        found = locate_primitives(table, docs[1].content)

        def val(n):
            r = found[n]
            return decode_primitive(r.wk_id, docs[1].content[r.offset:r.offset + r.width])

        attrs = {a: val(a) for a in ATTR_NAMES if a in found}
        assert set(attrs) == set(ATTR_NAMES), f"{name}: missing {set(ATTR_NAMES) - set(attrs)}"
        spent = sum(v - 10 for v in attrs.values() if v > 10)
        assert spent == 9, f"{name}: spent={spent} attrs={attrs}"


def test_block1_contents_checksum_crosscheck(main_save, dict_bytes):
    """Gate 3: block 1's ContentsChecksum equals block 2's stored checksum."""
    docs = parse_docs(main_save, dict_bytes)
    table0 = parse_schema(docs[0].schema_bytes)
    found0 = locate_primitives(table0, docs[0].content)
    assert "ContentsChecksum" in found0, sorted(found0)
    r = found0["ContentsChecksum"]
    assert r.wk_id == 8, f"ContentsChecksum wk_id={r.wk_id} (expected 8 = ulong)"
    val = decode_primitive(r.wk_id, docs[0].content[r.offset:r.offset + r.width])
    assert val == docs[1].original_checksum, \
        f"block1 ContentsChecksum {val:#018x} != block2 stored {docs[1].original_checksum:#018x}"


def test_locate_attribute_values_targets_real_map(main_save, dict_bytes):
    """`locate_attribute_values` returns the real Attributes map, never the
    DistributionMap template."""
    docs = parse_docs(main_save, dict_bytes)
    table = parse_schema(docs[1].schema_bytes)
    found = locate_attribute_values(table, docs[1].content)

    def val(name):
        r = found[name]
        return decode_primitive(r.wk_id, docs[1].content[r.offset:r.offset + r.width])

    decoded = {a: val(a) for a in ATTR_NAMES}
    assert decoded == {
        "Health": 10, "Stamina": 10, "Strength": 19, "Dexterity": 10,
        "Intelligence": 10, "Faith": 10, "Focus": 10, "ItemLoad": 10,
    }, decoded

    # The returned Strength ref is the Attributes-map one (value 19), NOT the
    # DistributionMap template one (value 1).
    strength = found["Strength"]
    assert strength.container == "Attributes"
    assert decode_primitive(strength.wk_id,
                            docs[1].content[strength.offset:strength.offset + strength.width]) == 19


def test_container_distinguishes_attributes_from_distribution_map(main_save, dict_bytes):
    """The walk records `container`, so the two enum-keyed maps are separable."""
    docs = parse_docs(main_save, dict_bytes)
    table = parse_schema(docs[1].schema_bytes)
    prims, _ = walk_primitives(table, docs[1].content)

    # The DistributionMap template (all 1s) is present in the full walk...
    dist = [p for p in prims if p.container == "DistributionMap"]
    assert dist, "expected DistributionMap entries in the full walk"
    dist_attr = [p for p in dist if p.name in ATTR_NAMES]
    assert dist_attr, "expected DistributionMap attribute entries"
    for p in dist_attr:
        v = decode_primitive(p.wk_id, docs[1].content[p.offset:p.offset + p.width])
        assert v == 1, (p.name, v)  # template values are all 1

    # ...and every located attribute ref comes from the Attributes container.
    found = locate_attribute_values(table, docs[1].content)
    assert all(r.container == "Attributes" for r in found.values())
    # The two maps point at different offsets for the same attribute name.
    dist_strength = next(p for p in dist if p.name == "Strength")
    assert found["Strength"].offset != dist_strength.offset


def test_locate_attribute_values_raises_when_absent():
    """No silent fallback: a tree without an Attributes container raises."""
    import src.cerimal.walk as walk_mod
    from src.cerimal.walk import PrimitiveRef

    # Simulate a walk that yields only DistributionMap entries (no "Attributes").
    orig = walk_mod.walk_primitives
    try:
        walk_mod.walk_primitives = lambda table, content: (
            [PrimitiveRef("Strength", 5, 0, 4, container="DistributionMap")], 4)
        with pytest.raises(ValueError, match="Attributes"):
            walk_mod.locate_attribute_values(None, b"")
    finally:
        walk_mod.walk_primitives = orig


def test_character_name_extracted_from_both_blocks(main_save, dict_bytes):
    docs = parse_docs(main_save, dict_bytes)
    # block 2 carries top-level CharacterName; block 1 carries Common.Name
    assert character_name(parse_schema(docs[1].schema_bytes), docs[1].content) == "Aurhan"
    assert character_name(parse_schema(docs[0].schema_bytes), docs[0].content) == "Aurhan"


def test_walk_strings_includes_name(main_save, dict_bytes):
    docs = parse_docs(main_save, dict_bytes)
    names = {n for n, _v, _c, _p in walk_strings(parse_schema(docs[1].schema_bytes), docs[1].content)}
    assert "CharacterName" in names
