# src/cerimal/walk.py
"""Walk the CERIMAL content tree, recording primitive leaves with their field names.

The model mirrors the format spec's Content Section:

* The content stream begins with the back-reference mapping table
  (`[7-bit count][7-bit offset]*count`); the node tree follows it.
* Whether a node carries a leading node tag is decided by ``needs_tag``:
  only **strings**, **arrays**, and **class** (TypeDef kind=1) references are
  tagged. Primitives, enums, value-structs (kind=2) and unmanaged structs
  (kind=3) are serialized **inline without a tag**.
* Value-structs and unmanaged structs are first attempted as a **blittable raw
  blob** (fixed alignment layout); if any field is non-blittable (array/string/
  class) the type falls back to **field-by-field** serialization where each field
  is itself a node (tag-or-not per ``needs_tag``).
* Generic type arguments are resolved positionally through ``type_args`` so that
  e.g. ``AttributeMap<int>`` reads ``int`` where a member is ``TypeArgument(0)``.
"""
from .codec import read_varint, WELLKNOWN
from .schema import read_typeref

# WellKnownType ids whose size differs from their alignment (size 16, align 4).
_ALIGN4_16 = {14, 15}  # decimal, Guid
_STRING_WK = 16


class PrimitiveRef:
    __slots__ = ("name", "wk_id", "offset", "width", "container", "path")

    def __init__(self, name, wk_id, offset, width, container=None, path=()):
        self.name = name
        self.wk_id = wk_id
        self.offset = offset
        self.width = width
        # `container`: the enclosing dict/list member name this leaf lives under
        # (e.g. "Attributes" vs "DistributionMap"). `None` for top-level fields.
        self.container = container
        # `path`: the full root-to-leaf chain of member names, for unambiguous
        # targeting (e.g. ("$root","AttributeDistribution","DistributionMap",
        # "Strength")).
        self.path = path


class _Walker:
    def __init__(self, table, content):
        self.t = table
        self.c = content
        self.pos = 0
        self.prims = []
        self.strings = []   # (name, offset, length, container, path) for string fields

    # -- type-argument resolution ------------------------------------------
    def _resolve(self, tr, type_args):
        """Resolve a TypeArgument typeref against the active generic args."""
        if tr is not None and tr[0] == "targ":
            if type_args and tr[1] < len(type_args):
                return type_args[tr[1]]
        return tr

    def _enum_def(self, tr, type_args):
        """Return the enum TypeDef for `tr`, or None if it isn't an enum."""
        tr = self._resolve(tr, type_args)
        if tr is not None and tr[0] == "named":
            td = self.t.types.get(tr[1])
            if td is not None and td.kind == 4:
                return td
        return None

    def _read_enum_value(self, enum_td):
        """Consume an inline enum value (no tag) and return its integer value."""
        size = WELLKNOWN[enum_td.enum_underlying][0]
        signed = WELLKNOWN[enum_td.enum_underlying][1]
        val = int.from_bytes(self.c[self.pos:self.pos + size], "little", signed=signed)
        self.pos += size
        return val

    # -- tag presence ------------------------------------------------------
    def _needs_tag(self, tr):
        """A node carries a leading tag iff it is a string, array, or class."""
        kind = tr[0]
        if kind == "prim":
            return tr[1] == _STRING_WK
        if kind == "array":
            return True
        if kind == "named":
            td = self.t.types.get(tr[1])
            if td is None:
                return True  # unknown: be conservative, expect a tag
            return td.kind == 1  # class
        return True  # type-argument that failed to resolve: conservative

    # -- blittable layout --------------------------------------------------
    def _prim_size_align(self, wk):
        size = WELLKNOWN[wk][0]
        align = 4 if wk in _ALIGN4_16 else size
        return size, align

    def _blittable_layout(self, tr, type_args):
        """Return (size, align) for a blittable typeref. Raise if non-blittable."""
        tr = self._resolve(tr, type_args)
        kind = tr[0]
        if kind == "prim":
            if tr[1] == _STRING_WK:
                raise ValueError("string is not blittable")
            return self._prim_size_align(tr[1])
        if kind == "array":
            raise ValueError("array is not blittable")
        if kind == "named":
            td = self.t.types.get(tr[1])
            if td is None:
                raise ValueError("unknown type in blittable layout")
            if td.kind == 4:  # enum
                s = WELLKNOWN[td.enum_underlying][0]
                return s, s
            if td.kind in (2, 3):  # value-struct / unmanaged
                eff = tr[2] if tr[2] else type_args
                off = 0
                max_a = 1
                for m in td.members:
                    if m.member_kind != "simple" or m.typeref is None:
                        raise ValueError("non-simple member in blittable layout")
                    sz, al = self._blittable_layout(m.typeref, eff)
                    off = (off + al - 1) // al * al
                    off += sz
                    max_a = max(max_a, al)
                total = (off + max_a - 1) // max_a * max_a
                return total, max_a
            raise ValueError("class is not blittable")
        raise ValueError(f"non-blittable typeref {tr}")

    def _unmanaged_fields(self, td, type_args):
        """Return (total_size, [(name, field_offset, resolved_typeref)])."""
        off = 0
        max_a = 1
        fields = []
        for m in td.members:
            if m.member_kind != "simple" or m.typeref is None:
                raise ValueError("non-simple member in unmanaged layout")
            resolved = self._resolve(m.typeref, type_args)
            sz, al = self._blittable_layout(resolved, type_args)
            off = (off + al - 1) // al * al
            fields.append((m.name, off, resolved))
            off += sz
            max_a = max(max_a, al)
        total = (off + max_a - 1) // max_a * max_a
        return total, fields

    def _record_blittable_leaves(self, tr, name, base, field_off, type_args,
                                 container, path):
        """Record primitive/enum leaves of a blittable field at absolute offsets."""
        tr = self._resolve(tr, type_args)
        leaf_path = path + (name,)
        if tr[0] == "prim":
            sz = WELLKNOWN[tr[1]][0]
            self.prims.append(PrimitiveRef(name, tr[1], base + field_off, sz,
                                           container, leaf_path))
            return
        if tr[0] == "named":
            td = self.t.types.get(tr[1])
            if td is None:
                raise ValueError(f"unknown type GUID {tr[1].hex()} in schema")
            if td.kind == 4:  # enum leaf
                sz = WELLKNOWN[td.enum_underlying][0]
                self.prims.append(PrimitiveRef(name, td.enum_underlying,
                                               base + field_off, sz,
                                               container, leaf_path))
                return
            # nested blittable struct: descend with its own field layout
            eff = tr[2] if tr[2] else type_args
            _, subfields = self._unmanaged_fields(td, eff)
            for fname, foff, ftr in subfields:
                self._record_blittable_leaves(ftr, fname, base, field_off + foff,
                                              eff, container, leaf_path)
            return
        # arrays/strings cannot occur inside a blittable struct
        raise ValueError(f"non-blittable leaf {tr}")

    # -- node / value parsing ----------------------------------------------
    def node(self, tr, name, type_args, container, path):
        """Read one node of declared type `tr`, honouring needs_tag."""
        tr = self._resolve(tr, type_args)
        if not self._needs_tag(tr):
            self.value(tr, 0, name, type_args, container, path)
            return
        tag, self.pos = read_varint(self.c, self.pos)
        kind = tag & 0x3
        if kind == 0:        # null
            return
        if kind == 1:        # back-reference (already serialized elsewhere)
            return
        if kind == 3:        # polymorphic: runtime typeref, then a full inner node
            rtr, self.pos = read_typeref(self.c, self.pos)
            self.node(rtr, name, type_args, container, path)
            return
        # kind == 2 concrete
        self.value(tr, tag >> 3, name, type_args, container, path)

    def value(self, tr, tag_payload, name, type_args, container, path):
        tr = self._resolve(tr, type_args)
        kind = tr[0]
        if kind == "prim":
            wk = tr[1]
            if wk == _STRING_WK:        # string: payload = UTF-8 byte length
                self.strings.append((name, self.pos, tag_payload, container,
                                     path + (name,)))
                self.pos += tag_payload
                return
            size = WELLKNOWN[wk][0]
            self.prims.append(PrimitiveRef(name, wk, self.pos, size,
                                           container, path + (name,)))
            self.pos += size
            return
        if kind == "array":
            rank = tr[1]
            elem = tr[2]
            total = tag_payload                 # first dimension
            for _ in range(1, rank):            # extra dims as 7-bit ints
                d, self.pos = read_varint(self.c, self.pos)
                total *= d
            # Elements live inside this array member: it becomes their container.
            elem_path = path + (name,)
            for _ in range(total):
                self.node(elem, name, type_args, name, elem_path)
            return
        if kind == "named":
            td = self.t.types.get(tr[1])
            if td is None:
                raise ValueError(f"unknown type GUID {tr[1].hex()} in schema")
            eff = tr[2] if tr[2] else type_args
            if td.kind == 4:                    # enum value (inline)
                size = WELLKNOWN[td.enum_underlying][0]
                self.prims.append(PrimitiveRef(name, td.enum_underlying, self.pos,
                                               size, container, path + (name,)))
                self.pos += size
                return
            if td.kind in (2, 3):               # value-struct / unmanaged
                struct_path = path + (name,)
                try:
                    total, fields = self._unmanaged_fields(td, eff)
                except ValueError:
                    # non-blittable: field-by-field. The struct's own member name
                    # is now the enclosing path component; container is inherited.
                    self._record_fields(td, eff, container, struct_path)
                    return
                base = self.pos                  # blittable raw blob
                for fname, foff, ftr in fields:
                    self._record_blittable_leaves(ftr, fname, base, foff, eff,
                                                  container, struct_path)
                self.pos = base + total
                return
            # class (kind 1)
            self._record_fields(td, eff, container, path + (name,))
            return
        raise ValueError(f"unhandled typeref {tr}")

    def _record_fields(self, td, type_args, container, path):
        # Class: base-class fields first (recursively), resolving base type-args.
        if td.kind == 1 and td.base is not None:
            base_tr = self._resolve(td.base, type_args)
            if base_tr[0] == "named":
                base_td = self.t.types.get(base_tr[1])
                if base_td is not None:
                    base_args = None
                    if base_tr[2]:
                        base_args = [self._resolve(a, type_args) for a in base_tr[2]]
                    self._record_fields(base_td,
                                        base_args if base_args is not None else type_args,
                                        container, path)
        for m in td.members:
            if m.member_kind == "list":
                count, self.pos = read_varint(self.c, self.pos)
                # Elements live inside this list member: it becomes their
                # container. Generic collections (List<T>, EnumMap<...>) carry an
                # anonymous member (name=None); fall back to the simple-member
                # that introduced the collection (the deepest named path part)
                # so the container is meaningful (e.g. "Attributes", "Classes").
                coll = m.name or (path[-1] if path else None)
                for _ in range(count):
                    self.node(m.typeref, m.name, type_args, coll, path)
            elif m.member_kind == "dict":
                count, self.pos = read_varint(self.c, self.pos)
                key_enum = self._enum_def(m.key_typeref, type_args)
                # Entries live inside this dict member: it becomes their container
                # (with the same anonymous-collection fallback as lists).
                coll = m.name or (path[-1] if path else None)
                for _ in range(count):
                    # When the key is an enum, label the value with the enum
                    # variant name (e.g. "Strength") so attribute values stored
                    # as dict entries become locatable by name.
                    val_name = m.name
                    if key_enum is not None:
                        kval = self._read_enum_value(key_enum)
                        if 0 <= kval < len(key_enum.members):
                            val_name = key_enum.members[kval].name
                    else:
                        self.node(m.key_typeref, m.name, type_args, coll, path)
                    self.node(m.value_typeref, val_name, type_args, coll, path)
            else:  # simple
                self.node(m.typeref, m.name, type_args, container, path)


def walk_primitives(table, content):
    """Walk the whole content tree. Return (list[PrimitiveRef], end_offset)."""
    w = _Walker(table, content)
    # Skip the back-reference mapping table: count, then `count` offsets.
    count, w.pos = read_varint(w.c, w.pos)
    for _ in range(count):
        _, w.pos = read_varint(w.c, w.pos)
    w.node(table.root, "$root", None, None, ())
    return w.prims, w.pos


def locate_primitives(table, content):
    """Return {field_name: PrimitiveRef}. Last occurrence wins for duplicate names."""
    prims, _ = walk_primitives(table, content)
    return {p.name: p for p in prims if p.name}


def walk_strings(table, content):
    """Walk the tree and return ``[(name, value, container, path), ...]`` for every
    string field, in document order. Decoded as UTF-8 (replace on error)."""
    w = _Walker(table, content)
    count, w.pos = read_varint(w.c, w.pos)   # skip back-reference mapping table
    for _ in range(count):
        _, w.pos = read_varint(w.c, w.pos)
    w.node(table.root, "$root", None, None, ())
    out = []
    for name, off, ln, container, path in w.strings:
        val = bytes(content[off:off + ln]).decode("utf-8", "replace")
        out.append((name, val, container, path))
    return out


def character_name(table, content):
    """Return the character's display name from this block, or None if absent.
    Prefers a top-level ``CharacterName`` (CharacterContents) then ``Name``
    (CharacterMetadata.Common)."""
    by_name = {}
    for name, val, _container, _path in walk_strings(table, content):
        by_name.setdefault(name, val)        # first occurrence wins
    for key in ("CharacterName", "Name"):
        if by_name.get(key):
            return by_name[key]
    return None


# The eight point-funded attributes (AttributeType enum variants).
ATTRIBUTE_NAMES = ("Health", "Stamina", "Strength", "Dexterity",
                   "Intelligence", "Faith", "Focus", "ItemLoad")

# The member name of the authoritative attribute-value map on CharacterContents.
# Its sibling AttributeDistribution.DistributionMap is a starting-distribution
# TEMPLATE (all 1s) and must never be confused with the real values.
ATTRIBUTES_CONTAINER = "Attributes"


def locate_attribute_values(table, content):
    """Return ``{attr_name: PrimitiveRef}`` for the eight attributes, drawn
    specifically from the ``Attributes`` map (``container == "Attributes"``).

    This explicitly excludes ``AttributeDistribution.DistributionMap`` (the
    starting-distribution template), so the respec engine can never patch the
    wrong map. Raises ``ValueError`` if the ``Attributes`` container is not
    present (no silent fallback to the template).
    """
    prims, _ = walk_primitives(table, content)
    found = {}
    saw_container = False
    for p in prims:
        if p.container == ATTRIBUTES_CONTAINER:
            saw_container = True
            if p.name in ATTRIBUTE_NAMES:
                found[p.name] = p
    if not saw_container:
        raise ValueError(
            f"{ATTRIBUTES_CONTAINER!r} container not found in content; refusing "
            f"to fall back to the DistributionMap template")
    missing = set(ATTRIBUTE_NAMES) - set(found)
    if missing:
        raise ValueError(
            f"{ATTRIBUTES_CONTAINER!r} map is missing attributes: {sorted(missing)}")
    return found
