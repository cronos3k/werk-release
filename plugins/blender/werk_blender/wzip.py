"""Store-mode zip writer, preview-first entry ordering, preview prefix.

Byte-for-byte what `core/src/zipstore.rs::write_zip` and
`fixtures/build_golden.py::write_zip` emit, because a package written by the
Blender add-on and the same package written by werk-core must be the same
bytes or "round-trip byte identity" is a claim about one writer instead of a
property of the format.

Three things make that hold and each is easy to break by accident:

1. **Store, method 0.** SPEC section 1: a zero-dependency zip reader is a
   hundred lines without an inflate implementation. `zipfile` would also work
   here, but it would drag its own defaults (timestamps, version-made-by,
   external attributes) into the bytes, and those defaults are exactly what
   destroys byte identity.
2. **A fixed DOS timestamp**, not a wall clock. A clock in a local header
   makes two identical exports differ, which costs the store its dedup and
   costs the gate its strongest assertion, and buys nothing.
3. **Flag bit 3 (data descriptor) is never set** and the general purpose flag
   carries only the UTF-8 bit — `werk_read.py` refuses an entry with bit 3,
   and it is right to.

Entry order follows `container.entry_order`, matched exact-path-first then
directory-prefix (S-14's proposed ruling, which is what every werk
implementation already does), remainder lexicographic.
"""

import struct

# The same fixed DOS timestamp core/src/zipstore.rs uses: 2026-08-08 09:00:00.
DOS_TIME = (9 << 11) | (0 << 5)
DOS_DATE = ((2026 - 1980) << 9) | (8 << 5) | 8
FLAG_UTF8 = 0x0800

#: The preview-first physical order (SPEC section 1, law 9). `PREVIEW_TIER` is
#: the part of it whose end `container.preview_prefix_bytes` measures to.
PREVIEW_TIER = [
    "MANIFEST.json",
    "SIGNATURE.json",
    "LICENSE",
    "README.txt",
    "loaders/",
    "spec/",
    "semantics/",
    "imposters/",
]
ENTRY_ORDER = PREVIEW_TIER + [
    "materials/",
    "textures/",
    "physics/",
    "skeleton/",
    "animation/",
    "properties/",
    "provenance/",
    "geometry/",
    "audio/",
    "x/",
]

_CRC_TABLE = []
for _n in range(256):
    _c = _n
    for _ in range(8):
        _c = (_c >> 1) ^ (0xEDB88320 if _c & 1 else 0)
    _CRC_TABLE.append(_c)


def crc32(data):
    c = 0xFFFFFFFF
    for b in bytearray(data):
        c = (c >> 8) ^ _CRC_TABLE[(c ^ b) & 0xFF]
    return c ^ 0xFFFFFFFF


def _matches(path, pattern):
    """S-14: a trailing '/' means directory prefix, anything else means an
    exact path. Exact wins, and is tried first by `order_entries`."""
    return path.startswith(pattern) if pattern.endswith("/") else path == pattern


def order_entries(paths, entry_order=None, preview_extra=()):
    """Physical entry order: each `entry_order` bucket in turn, exact matches
    before prefix matches, then everything left over, lexicographic."""
    order = list(entry_order or ENTRY_ORDER)
    remaining = sorted(paths)
    out = []
    for pat in order:
        picked = [p for p in remaining if _matches(p, pat)]
        for p in picked:
            remaining.remove(p)
            out.append(p)
    return out + remaining


def entry_size(name, data):
    """Physical bytes one store-mode entry occupies: local header + name + data.
    No extra field, no data descriptor, so this is exact rather than a bound."""
    return 30 + len(name.encode("utf-8")) + len(data)


def preview_prefix_bytes(entries, preview_tier=None, preview_extra=()):
    """Offset of the END of the last entry belonging to the preview tier.

    S-15 filed that the spec never said what this number measures *to*. This
    implements the proposed ruling literally: the tier is `PREVIEW_TIER` plus
    whatever `preview_extra` names (normally the one entry `primary.sound`
    points at), and the value is the physical end offset of the last such
    entry. It is recomputed on every write and compared, never carried over.
    """
    tier = list(preview_tier or PREVIEW_TIER) + list(preview_extra)
    cursor = 0
    prefix = 0
    for name, data in entries:
        size = entry_size(name, data)
        if any(_matches(name, p) for p in tier):
            prefix = cursor + size
        cursor += size
    return prefix


def write_zip(entries):
    """`entries` is an ordered list of (package_path, bytes)."""
    out, central, count = bytearray(), bytearray(), 0
    for name, data in entries:
        lho = len(out)
        crc = crc32(data)
        nb = name.encode("utf-8")
        out += struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, FLAG_UTF8, 0, DOS_TIME,
                           DOS_DATE, crc, len(data), len(data), len(nb), 0)
        out += nb + data
        central += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, FLAG_UTF8, 0,
                               DOS_TIME, DOS_DATE, crc, len(data), len(data), len(nb),
                               0, 0, 0, 0, 0, lho)
        central += nb
        count += 1
    cd_off, cd_size = len(out), len(central)
    out += central
    out += struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, count, count, cd_size, cd_off, 0)
    return bytes(out)


def selftest(verbose=False):
    bad = []

    # CRC-32 of "123456789" is the standard check value, 0xCBF43926
    got = crc32(b"123456789")
    if got != 0xCBF43926:
        bad.append("crc32 check value: got 0x%08X want 0xCBF43926" % got)
    elif verbose:
        print("  OK crc32('123456789') = 0x%08X" % got)

    # exact beats prefix, and an exact path between two prefixes keeps its slot
    order = order_entries(
        ["geometry/game.glb", "MANIFEST.json", "spec/SPEC.md", "audio/sfx/a.wav",
         "loaders/werk_read.py", "zzz.txt", "LICENSE"])
    want_first = ["MANIFEST.json", "LICENSE", "loaders/werk_read.py", "spec/SPEC.md"]
    if order[:4] != want_first:
        bad.append("entry order: got %r want prefix %r" % (order[:4], want_first))
    elif verbose:
        print("  OK entry order preview-first: %r" % (order,))
    if order[-1] != "zzz.txt":
        bad.append("unlisted paths must sort last: got %r" % (order,))

    # a written zip must be readable by the vendored reader, which parses the
    # byte tables by hand. Two independent implementations agreeing is the
    # point of checking this here rather than with `zipfile`.
    from .vendor.werk_read import ZipContainer
    blob = write_zip([("a.txt", b"hello"), ("dir/b.bin", bytes(range(256)))])
    z = ZipContainer(blob)
    if z.names() != ["a.txt", "dir/b.bin"]:
        bad.append("round trip names: %r" % (z.names(),))
    elif z.read("a.txt") != b"hello" or z.read("dir/b.bin") != bytes(range(256)):
        bad.append("round trip bytes differ")
    elif verbose:
        print("  OK write_zip -> vendored ZipContainer round trip")

    # two writes of the same content are byte-identical (no wall clock)
    if write_zip([("a.txt", b"hello")]) != write_zip([("a.txt", b"hello")]):
        bad.append("write_zip is not deterministic")
    elif verbose:
        print("  OK write_zip is deterministic")

    # preview prefix arithmetic: sum of the physical extents up to the tier end
    ents = [("MANIFEST.json", b"x" * 10), ("LICENSE", b"y" * 20),
            ("geometry/game.glb", b"z" * 30)]
    want = entry_size(*ents[0]) + entry_size(*ents[1])
    got = preview_prefix_bytes(ents)
    if got != want:
        bad.append("preview_prefix_bytes: got %d want %d" % (got, want))
    elif verbose:
        print("  OK preview_prefix_bytes = %d" % got)

    return bad
