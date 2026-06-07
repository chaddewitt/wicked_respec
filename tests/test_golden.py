from src.engine import preview_respec, apply_respec
from src.cerimal import (parse_docs, parse_schema, locate_attribute_values,
                         locate_primitives, walk_primitives, decode_primitive, verify)


def _attrs(docs):
    t = parse_schema(docs[1].schema_bytes)
    refs = locate_attribute_values(t, docs[1].content)
    return {n: decode_primitive(r.wk_id, docs[1].content[r.offset:r.offset + r.width])
            for n, r in refs.items()}


def test_preview_does_not_modify(main_save, dict_bytes):
    plan, values, name = preview_respec(main_save, dict_bytes)
    assert values["Strength"] == 19
    assert name == "Aurhan"
    assert plan.refunded == 9
    assert plan.attributes_reset == ["Strength"]


def test_golden_resets_attributes_and_verifies(tmp_path, main_save, dict_bytes):
    save = tmp_path / "char.cerimal"; save.write_bytes(main_save)
    plan = apply_respec(str(save), dict_bytes)
    out = save.read_bytes()
    docs = parse_docs(out, dict_bytes)
    assert all(v == 10 for v in _attrs(docs).values()), _attrs(docs)
    ok, det = verify(out, dict_bytes); assert ok, det
    # block 1 ContentsChecksum equals block 2's new hash
    mt = parse_schema(docs[0].schema_bytes)
    cc = locate_primitives(mt, docs[0].content)["ContentsChecksum"]
    cc_val = decode_primitive(cc.wk_id, docs[0].content[cc.offset:cc.offset + cc.width])
    assert cc_val == docs[1].original_checksum
    assert plan.backup_path is not None


def test_golden_only_attribute_offsets_changed(tmp_path, main_save, dict_bytes):
    save = tmp_path / "char.cerimal"; save.write_bytes(main_save)
    before = parse_docs(main_save, dict_bytes)
    bt = parse_schema(before[1].schema_bytes)
    bp, _ = walk_primitives(bt, before[1].content)
    before_map = {p.offset: decode_primitive(p.wk_id, before[1].content[p.offset:p.offset + p.width])
                  for p in bp if p.name}
    plan = apply_respec(str(save), dict_bytes)
    after = parse_docs(save.read_bytes(), dict_bytes)
    at = parse_schema(after[1].schema_bytes)
    ap, _ = walk_primitives(at, after[1].content)
    after_map = {p.offset: decode_primitive(p.wk_id, after[1].content[p.offset:p.offset + p.width])
                 for p in ap if p.name}
    changed = {off for off in before_map if before_map.get(off) != after_map.get(off)}
    assert changed == {w.offset for w in plan.writes}, (changed, {w.offset for w in plan.writes})


def test_noop_respec_makes_no_backup_and_leaves_file_unchanged(tmp_path, main_save, dict_bytes):
    save = tmp_path / "char.cerimal"; save.write_bytes(main_save)
    apply_respec(str(save), dict_bytes)               # first pass resets Strength -> 10
    after_first = save.read_bytes()
    backups = tmp_path / "_wicked_respec_backups"
    n_before = len(list(backups.iterdir())) if backups.exists() else 0
    plan2 = apply_respec(str(save), dict_bytes)        # second pass: already all base -> no-op
    assert plan2.writes == []
    assert plan2.backup_path is None
    assert save.read_bytes() == after_first            # file untouched on no-op
    n_after = len(list(backups.iterdir())) if backups.exists() else 0
    assert n_after == n_before                          # no spurious backup folder created
