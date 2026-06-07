# src/cerimal/schema.py
"""CERIMAL schema section: TypeRef + type definitions -> TypeTable."""
import struct
from .codec import read_varint

def read_typeref(buf, pos):
    """Return (typeref, new_pos). typeref is a tuple tagged by kind."""
    h = buf[pos]; pos += 1
    kind = h & 0x3
    payload = h >> 3
    if kind == 0:                       # primitive
        return ("prim", payload), pos
    if kind == 1:                       # array
        elem, pos = read_typeref(buf, pos)
        return ("array", payload, elem), pos
    if kind == 2:                       # type-argument (generic param index)
        return ("targ", payload), pos
    guid = bytes(buf[pos:pos + 16]); pos += 16   # kind 3: named
    args = []
    for _ in range(payload):
        a, pos = read_typeref(buf, pos)
        args.append(a)
    return ("named", guid, args), pos

class Member:
    __slots__ = ("name", "member_kind", "typeref", "key_typeref", "value_typeref")
    def __init__(self, name, member_kind, typeref=None, key_typeref=None, value_typeref=None):
        self.name = name
        self.member_kind = member_kind          # "simple" | "list" | "dict"
        self.typeref = typeref
        self.key_typeref = key_typeref
        self.value_typeref = value_typeref

class TypeDef:
    __slots__ = ("guid", "kind", "type_param_count", "members", "base", "enum_underlying", "name")
    def __init__(self, guid, kind):
        self.guid = guid
        self.kind = kind                        # 1 class, 2 struct, 3 unmanaged, 4 enum
        self.type_param_count = 0
        self.members = []
        self.base = None                        # TypeRef of base class, or None
        self.enum_underlying = None             # wk id for enums
        self.name = None

class TypeTable:
    def __init__(self):
        self.types = {}     # guid -> TypeDef
        self.root = None    # TypeRef

def _read_member_name(buf, pos):
    ln = buf[pos]; pos += 1                      # member names: 1-byte length prefix
    name = buf[pos:pos + ln].decode("utf-8", "replace"); pos += ln
    return name, pos

def _parse_type_record(buf, pos):
    start = pos
    body_bytes, flags = struct.unpack_from("<II", buf, pos)
    # `body_bytes` (the +0x00 field) counts the bytes AFTER the fixed 28-byte
    # header - i.e. the member/body section only, NOT the whole record. The full
    # record length is therefore 28 + body_bytes. (Verified empirically: with this
    # interpretation all 52 type records in block 2 land exactly on defs_end; the
    # off-by-28 was a bug in the plan's draft, which treated this field as the
    # whole-record length.)
    total_bytes = body_bytes + 28
    # local_version at +8 (unused), GUID at +12
    guid = bytes(buf[pos + 12:pos + 28])
    kind = (flags & 0x3) + 1
    has_base = bool((flags >> 2) & 0x1)
    type_param_count = (flags >> 3) & 0x1F
    member_count = flags >> 8
    td = TypeDef(guid, kind)
    td.type_param_count = type_param_count
    p = pos + 28

    if has_base:
        base_hdr = struct.unpack_from("<I", buf, p)[0]; p += 4
        has_base_type = bool((base_hdr >> 24) & 0x1)
        interface_count = (base_hdr >> 25) & 0x7F
        if has_base_type:
            td.base, p = read_typeref(buf, p)
        for _ in range(interface_count):
            _, p = read_typeref(buf, p)

    if kind == 4:  # enum
        m_packed = buf[p]; p += 1
        td.enum_underlying = {0:2,1:1,2:4,3:3,4:6,5:5,6:8,7:7}[m_packed & 0x7]
        size = 1 << ((m_packed & 0x7) >> 1)
        for _ in range(member_count):
            name, p = _read_member_name(buf, p)
            p += size                            # variant value (ignored)
            td.members.append(Member(name, "simple"))
    elif kind == 1:  # class: each member has a u8 kind prefix
        for _ in range(member_count):
            mk = buf[p]; p += 1                   # member_kind - 1
            if mk == 0:                           # List
                elem, p = read_typeref(buf, p)
                td.members.append(Member(None, "list", typeref=elem))
            elif mk == 1:                         # Dict
                kt, p = read_typeref(buf, p)
                vt, p = read_typeref(buf, p)
                td.members.append(Member(None, "dict", key_typeref=kt, value_typeref=vt))
            else:                                 # Simple
                name, p = _read_member_name(buf, p)
                tr, p = read_typeref(buf, p)
                td.members.append(Member(name, "simple", typeref=tr))
    else:          # kind 2/3: no member-kind prefix; [name][typeref]
        for _ in range(member_count):
            name, p = _read_member_name(buf, p)
            tr, p = read_typeref(buf, p)
            td.members.append(Member(name, "simple", typeref=tr))

    assert p - start == total_bytes, f"type record desync: {p-start} != {total_bytes}"
    return td, start + total_bytes

def parse_schema(schema_bytes):
    buf = schema_bytes
    global_version, type_defs_total, type_def_count, name_pool_total = \
        struct.unpack_from("<IIII", buf, 0)
    p = 16
    defs_end = p + type_defs_total
    table = TypeTable()
    order = []
    while p < defs_end:
        td, p = _parse_type_record(buf, p)
        table.types[td.guid] = td
        order.append(td)
    # name pool: one 7-bit-length-prefixed UTF-8 name per type, same order
    for td in order:
        ln, p = read_varint(buf, p)
        td.name = buf[p:p + ln].decode("utf-8", "replace"); p += ln
    # root type reference
    table.root, p = read_typeref(buf, p)
    # The type/name/root section must consume schema_bytes exactly (the back-reference table
    # lives at the start of the content, not here). A shortfall means a parse desync.
    assert p == len(buf), f"schema underconsumed: pos={p} len={len(buf)}"
    return table
