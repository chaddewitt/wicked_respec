"""Orchestration: read save, compute reset-only respec, write back safely."""
import os
import tempfile
from src.cerimal import (parse_docs, reseal, verify, parse_schema,
                         locate_primitives, locate_attribute_values, decode_primitive,
                         character_name)
from src.respec import compute_respec
from src.backup import make_backup


def _attr_values(content, refs):
    return {n: decode_primitive(r.wk_id, content[r.offset:r.offset + r.width])
            for n, r in refs.items()}


def _locate_attrs(docs):
    table = parse_schema(docs[1].schema_bytes)
    return locate_attribute_values(table, docs[1].content)


def _contents_checksum_offset(docs):
    meta_table = parse_schema(docs[0].schema_bytes)
    found = locate_primitives(meta_table, docs[0].content)
    if "ContentsChecksum" not in found:
        raise RuntimeError("ContentsChecksum field not found in CharacterMetadata")
    return found["ContentsChecksum"].offset


def _character_name(docs):
    """Best-effort display name: block 2's CharacterName, else block 1's Common.Name."""
    for d in docs:
        try:
            name = character_name(parse_schema(d.schema_bytes), d.content)
        except Exception:
            name = None
        if name:
            return name
    return None


def preview_respec(save_bytes, dict_bytes):
    docs = parse_docs(save_bytes, dict_bytes)
    refs = _locate_attrs(docs)
    values = _attr_values(docs[1].content, refs)
    plan = compute_respec(refs, values, base=10)
    name = _character_name(docs)
    return plan, values, name


def apply_respec(save_path, dict_bytes, do_backup=True):
    with open(save_path, "rb") as f:
        save_bytes = f.read()
    docs = parse_docs(save_bytes, dict_bytes)
    refs = _locate_attrs(docs)
    values = _attr_values(docs[1].content, refs)
    plan = compute_respec(refs, values, base=10)

    if not plan.writes:
        return plan  # already all-base; no backup, no write

    backup_path = make_backup(save_path) if do_backup else None
    plan.backup_path = backup_path

    cc_offset = _contents_checksum_offset(docs)
    for w in plan.writes:
        docs[1].content[w.offset:w.offset + len(w.bytes)] = w.bytes
    out = reseal(docs, contents_checksum_offset=cc_offset)
    ok, details = verify(out, dict_bytes)
    if not ok:
        raise RuntimeError(f"reseal verify failed, NOT writing: {details}")

    # Atomic write: write a temp file in the same directory, then os.replace
    # (atomic on Windows when source and destination share a volume). A crash
    # mid-write can never leave a truncated/half-written save in place.
    save_dir = os.path.dirname(os.path.abspath(save_path))
    fd, tmp_path = tempfile.mkstemp(dir=save_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(out)
        os.replace(tmp_path, save_path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return plan
