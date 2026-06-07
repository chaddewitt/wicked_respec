"""CERIMAL container framing: split blocks, parse headers, decompress, reseal, verify."""
import io, struct
import zstandard as zstd
from .codec import xxh64

MAGIC = b"CERIMAL"

def split_blocks(data):
    """Return [(start, end), ...] for each CERIMAL block."""
    offs, i = [], 0
    while True:
        j = data.find(MAGIC, i)
        if j < 0:
            break
        offs.append(j); i = j + 1
    return [(s, offs[k + 1] if k + 1 < len(offs) else len(data))
            for k, s in enumerate(offs)]

def parse_header(data, start):
    schema_size, content_size, comp_type = struct.unpack_from("<III", data, start + 8)
    checksum = struct.unpack_from("<Q", data, start + 20)[0]
    return {
        "version": data[start + 7],
        "schema_size": schema_size,
        "content_size": content_size,
        "comp_type": comp_type,
        "checksum": checksum,
    }

def decompress(content, comp_type, dict_bytes):
    if comp_type == 0:
        return bytes(content)
    dctx = zstd.ZstdDecompressor(dict_data=zstd.ZstdCompressionDict(dict_bytes))
    return dctx.stream_reader(io.BytesIO(content)).read()

class Doc:
    def __init__(self, version, schema_bytes, content, original_checksum):
        self.version = version
        self.schema_bytes = schema_bytes          # bytes (plaintext, unchanged)
        self.content = bytearray(content)          # decompressed, mutable
        self.original_checksum = original_checksum  # stored hash before any edit
    @property
    def schema_size(self):
        return len(self.schema_bytes)

def parse_docs(data, dict_bytes):
    docs = []
    for s, e in split_blocks(data):
        h = parse_header(data, s)
        body = data[s + 28:e]                       # schema + backref + content
        schema_bytes = body[:h["schema_size"]]
        raw_content = data[e - h["content_size"]:e] # content = last content_size bytes
        content = decompress(raw_content, h["comp_type"], dict_bytes)
        docs.append(Doc(h["version"], schema_bytes, content, h["checksum"]))
    return docs

def _emit_block(doc, checksum):
    """Assemble one block, content uncompressed (comp_type=0)."""
    content = bytes(doc.content)
    header = bytearray(28)
    header[0:7] = MAGIC
    header[7] = doc.version
    struct.pack_into("<III", header, 8, doc.schema_size, len(content), 0)
    struct.pack_into("<Q", header, 20, checksum)
    return bytes(header) + doc.schema_bytes + content

def reseal(docs, contents_checksum_offset=None):
    """Return full file bytes with both blocks re-sealed (uncompressed).

    When block 2's content changed, block 1 (CharacterMetadata) embeds a copy of
    block 2's checksum that must be updated to match. Locating that field:
      - If `contents_checksum_offset` is given, patch block 1's decompressed content
        at exactly that offset (the engine supplies a field-name-located offset).
      - Otherwise fall back to searching block 1's decompressed content for block 2's
        OLD checksum bytes. This is only safe when there is exactly ONE occurrence.
        Block 1 may contain a checksum *history* (e.g. backup files), so >1 occurrence
        is ambiguous: refuse and require an explicit offset rather than guess.
    """
    if len(docs) != 2:
        raise ValueError(f"expected 2 docs, got {len(docs)}")
    meta, contents = docs[0], docs[1]

    new_c = xxh64(contents.schema_bytes + bytes(contents.content))
    old_c = contents.original_checksum
    if new_c != old_c:
        if contents_checksum_offset is not None:
            idx = contents_checksum_offset
        else:
            old_bytes = struct.pack("<Q", old_c)
            occ = bytes(meta.content).count(old_bytes)
            if occ == 0:
                raise ValueError(
                    f"embedded ContentsChecksum {old_c:#018x} not found in block 1 "
                    f"(refusing to patch)")
            if occ > 1:
                raise ValueError(
                    f"ambiguous embedded ContentsChecksum: {occ} occurrences; "
                    f"pass contents_checksum_offset")
            idx = bytes(meta.content).index(old_bytes)
        meta.content[idx:idx + 8] = struct.pack("<Q", new_c)
        contents.original_checksum = new_c  # keep consistent if resealed again

    new_m = xxh64(meta.schema_bytes + bytes(meta.content))
    return _emit_block(meta, new_m) + _emit_block(contents, new_c)

def verify(data, dict_bytes):
    """Return (ok, details): every stored header checksum matches recomputed."""
    details, ok = [], True
    for i, (s, e) in enumerate(split_blocks(data)):
        h = parse_header(data, s)
        calc = xxh64(data[s + 28:e])
        good = (h["checksum"] == calc)
        ok = ok and good
        details.append((i + 1, h["checksum"], calc, good))
    return ok, details
