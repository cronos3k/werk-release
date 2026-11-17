#!/usr/bin/env python3
"""Generate the worked examples in spec/examples/. Pure standard library.

This script is documentation as much as it is a generator: `mp_encode` below
is a complete, canonical MessagePack writer for the subset defined in
spec/layouts/ENVELOPE.layout.txt section 4, and `build_wkrp` is a complete
writer for spec/layouts/restposes.layout.txt. Read them if a sentence in
those files is ambiguous; they are the executable statement of it.

Outputs (all regenerated, byte-identical, from this script alone):
    MANIFEST.example.json        a small but complete, schema-valid manifest
    restposes.example.wkrp       a real 2-pose WKRP envelope binary
    restposes.example.hex.txt    an annotated hex dump of that binary
    gsplat.example.wkgs          a real 3-Gaussian WKGS envelope binary
    gsplat.example.hex.txt       an annotated hex dump of that binary
    embedding.example.wkem       a real 8-component WKEM envelope binary
    embedding.example.hex.txt    an annotated hex dump of that binary
    SIGNATURE.example.json       a real one-link chain over MANIFEST.example.json
    signature.example.txt        the signed message, byte-for-byte, and the
                                 verification it produces

WHY THE THREE HEX DUMPS EXIST (spec finding S-OW-3, measured 2026-08-08).
The open-weights gauntlet put ENVELOPE.layout.txt section 4 -- a complete
MessagePack subset -- in front of a 30B coding model, which read it, declined
to implement it, and printed fabricated floats labelled "demonstration". The
grammar was present and the WORKED EXAMPLE was not. A worked example is the
rung between a grammar and a decoder, and every envelope magic a package can
carry now has one.
"""
import hashlib
import json
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent


# --------------------------------------------------------------------------
# Canonical MessagePack writer for the werk header subset.
# Shortest encoding for ints, float64 for every non-integer, map keys sorted
# by raw UTF-8 bytes, no ext types, no nil for absent keys.
# All multi-byte values inside MessagePack are BIG-endian.
# --------------------------------------------------------------------------
def mp_encode(v):
    if v is True:
        return b"\xc3"
    if v is False:
        return b"\xc2"
    if v is None:
        return b"\xc0"
    if isinstance(v, int):
        if 0 <= v <= 127:
            return struct.pack(">B", v)
        if -32 <= v < 0:
            return struct.pack(">b", v)
        if 0 <= v <= 0xFF:
            return b"\xcc" + struct.pack(">B", v)
        if 0 <= v <= 0xFFFF:
            return b"\xcd" + struct.pack(">H", v)
        if 0 <= v <= 0xFFFFFFFF:
            return b"\xce" + struct.pack(">I", v)
        if 0 <= v <= 0xFFFFFFFFFFFFFFFF:
            return b"\xcf" + struct.pack(">Q", v)
        if -0x80 <= v < 0:
            return b"\xd0" + struct.pack(">b", v)
        if -0x8000 <= v < 0:
            return b"\xd1" + struct.pack(">h", v)
        if -0x80000000 <= v < 0:
            return b"\xd2" + struct.pack(">i", v)
        return b"\xd3" + struct.pack(">q", v)
    if isinstance(v, float):
        return b"\xcb" + struct.pack(">d", v)
    if isinstance(v, str):
        b = v.encode("utf-8")
        n = len(b)
        if n <= 31:
            return struct.pack(">B", 0xA0 | n) + b
        if n <= 0xFF:
            return b"\xd9" + struct.pack(">B", n) + b
        if n <= 0xFFFF:
            return b"\xda" + struct.pack(">H", n) + b
        return b"\xdb" + struct.pack(">I", n) + b
    if isinstance(v, (bytes, bytearray)):
        b = bytes(v)
        n = len(b)
        if n <= 0xFF:
            return b"\xc4" + struct.pack(">B", n) + b
        if n <= 0xFFFF:
            return b"\xc5" + struct.pack(">H", n) + b
        return b"\xc6" + struct.pack(">I", n) + b
    if isinstance(v, (list, tuple)):
        n = len(v)
        if n <= 15:
            head = struct.pack(">B", 0x90 | n)
        elif n <= 0xFFFF:
            head = b"\xdc" + struct.pack(">H", n)
        else:
            head = b"\xdd" + struct.pack(">I", n)
        return head + b"".join(mp_encode(x) for x in v)
    if isinstance(v, dict):
        items = sorted(v.items(), key=lambda kv: kv[0].encode("utf-8"))
        n = len(items)
        if n <= 15:
            head = struct.pack(">B", 0x80 | n)
        elif n <= 0xFFFF:
            head = b"\xde" + struct.pack(">H", n)
        else:
            head = b"\xdf" + struct.pack(">I", n)
        return head + b"".join(mp_encode(k) + mp_encode(val) for k, val in items)
    raise TypeError(f"not encodable in the werk MessagePack subset: {type(v)}")


def align16(n):
    return (n + 15) // 16 * 16


# --------------------------------------------------------------------------
# WKRP writer — spec/layouts/restposes.layout.txt
# --------------------------------------------------------------------------
def build_wkrp(poses, extra_header):
    """poses: list of (quat_wxyz, [contact xyz, ...], probability, support_area)"""
    contacts = []
    entries = b""
    for quat, pts, prob, area in poses:
        first = len(contacts)
        contacts.extend(pts)
        entries += struct.pack(
            "<4f2I2f", *quat, first, len(pts), prob, area)
    contact_blob = b"".join(struct.pack("<3f", *p) for p in contacts)

    # The header declares offsets, and the offsets depend on the header's own
    # length, so a writer iterates to a fixed point. Two passes are NOT
    # enough: a shrinking integer (0xFFFF encodes in 3 bytes, 224 in 2) can
    # shorten the header and move the payload. The loop below converges in
    # two or three rounds and the assertion proves it converged.
    def make_header(payload_origin, off0, off1):
        h = dict(extra_header)
        h.update({
            "kind": "core.pose.rest",
            "endianness": "le",
            "payload_origin": payload_origin,
            # Rounded UP to the alignment: ENVELOPE.layout.txt section 5 says
            # trailing padding to the 16-byte boundary is legal and section 1
            # says file_size == payload_origin + payload_size, so the padding
            # is inside payload_size. Both statements only hold together if
            # the writer rounds here.
            "payload_size": align16(off1 + len(contact_blob)) - payload_origin,
            "pose_count": len(poses),
            "contact_count": len(contacts),
            "sections": [
                {"name": "poses", "offset": off0, "size": len(entries),
                 "dtype": "record", "shape": [len(poses)], "stride": 32},
                {"name": "contacts", "offset": off1, "size": len(contact_blob),
                 "dtype": "f32", "shape": [len(contacts), 3], "stride": 12},
            ],
        })
        return mp_encode(h)

    header_len = len(make_header(0, 0, 0))
    for _ in range(8):
        origin = align16(12 + header_len)
        off0 = origin
        off1 = align16(off0 + len(entries))
        header = make_header(origin, off0, off1)
        if len(header) == header_len:
            break
        header_len = len(header)
    else:
        raise RuntimeError("header length did not converge")
    assert align16(12 + len(header)) == origin

    out = bytearray()
    out += b"WKRP"
    out += struct.pack("<I", 1)
    out += struct.pack("<I", len(header))
    out += header
    out += b"\x00" * (origin - len(out))
    out += entries
    out += b"\x00" * (off1 - len(out))
    out += contact_blob
    out += b"\x00" * (align16(len(out)) - len(out))
    return bytes(out), header, origin, off0, off1


# --------------------------------------------------------------------------
# WKGS writer — spec/layouts/gsplat.layout.txt
#
# Three Gaussians, sh_degree 1 (so K = 4 and "sh-rest" is a NON-EMPTY
# [count, K-1, 3] array — the section every reader gets wrong, because the
# source convention stores its transpose). Small enough to annotate every
# record; complete enough that a decoder written against the dump is a
# decoder for a 1.9 M-Gaussian capture too.
# --------------------------------------------------------------------------
GS_SECTIONS = [
    ("means", "f32", 12), ("scales", "f32", 12), ("rotations", "f32", 16),
    ("opacities", "f32", 4), ("sh-dc", "f32", 12), ("sh-rest", "f32", 12),
]


def _sections_at(origin, blobs, shapes, strides, dtypes, names):
    """Lay sections out from `origin`, each 16-byte aligned. -> (maps, bytes)."""
    maps, out, cur = [], bytearray(), origin
    for name, dtype, stride, shape, blob in zip(names, dtypes, strides, shapes, blobs):
        pad = align16(cur) - cur
        out += b"\x00" * pad
        cur += pad
        maps.append({"name": name, "offset": cur, "size": len(blob),
                     "dtype": dtype, "shape": list(shape), "stride": stride})
        out += blob
        cur += len(blob)
    out += b"\x00" * (align16(cur) - cur)
    return maps, bytes(out)


def _build_envelope(magic, kind, extra_header, names, dtypes, strides, shapes, blobs):
    """The generic WK** writer: fixed prefix, canonical header, aligned sections.

    Identical fixed-point iteration to build_wkrp -- the header declares the
    offsets and the offsets depend on the header's own length, so a writer
    iterates until the length stops moving.
    """
    def make(origin):
        maps, payload = _sections_at(origin, blobs, shapes, strides, dtypes, names)
        h = dict(extra_header)
        h.update({"kind": kind, "endianness": "le",
                  "payload_origin": origin,
                  "payload_size": len(payload),
                  "sections": maps})
        return mp_encode(h), maps, payload

    header_len = len(make(0)[0])
    for _ in range(8):
        origin = align16(12 + header_len)
        header, maps, payload = make(origin)
        if len(header) == header_len:
            break
        header_len = len(header)
    else:
        raise RuntimeError("header length did not converge")
    out = bytearray()
    out += magic
    out += struct.pack("<I", 1)
    out += struct.pack("<I", len(header))
    out += header
    out += b"\x00" * (origin - len(out))
    out += payload
    assert len(out) == origin + len(payload)
    return bytes(out), header, origin, maps


def build_wkgs(gaussians, sh_degree, extra_header):
    """gaussians: list of (mean3, scale3, quat_wxyz, opacity, dc3, rest[K-1][3])"""
    k = (sh_degree + 1) ** 2
    n = len(gaussians)
    means = b"".join(struct.pack("<3f", *g[0]) for g in gaussians)
    scales = b"".join(struct.pack("<3f", *g[1]) for g in gaussians)
    rots = b"".join(struct.pack("<4f", *g[2]) for g in gaussians)
    opac = b"".join(struct.pack("<f", g[3]) for g in gaussians)
    shdc = b"".join(struct.pack("<3f", *g[4]) for g in gaussians)
    shrest = b"".join(struct.pack("<3f", *c) for g in gaussians for c in g[5])
    head = dict(extra_header)
    head.update({"count": n, "sh_degree": sh_degree, "sh_coeff_count": k,
                 "sh_coeff_order": "coefficient-major", "quat_order": "wxyz",
                 "scale_space": "linear", "opacity_space": "linear",
                 "length_unit": "metre"})
    return _build_envelope(
        b"WKGS", "core.geom.gsplat", head,
        [s[0] for s in GS_SECTIONS], [s[1] for s in GS_SECTIONS],
        [s[2] for s in GS_SECTIONS],
        [[n, 3], [n, 3], [n, 4], [n], [n, 3], [n, k - 1, 3]],
        [means, scales, rots, opac, shdc, shrest])


def build_wkem(vector, palette, extra_header):
    """vector: list of floats. palette: list of (r, g, b, weight)."""
    vec = b"".join(struct.pack("<f", v) for v in vector)
    pal = b"".join(struct.pack("<4f", *s) for s in palette)
    head = dict(extra_header)
    head.update({"dim": len(vector), "swatch_count": len(palette)})
    return _build_envelope(
        b"WKEM", "core.embedding", head,
        ["vector", "palette"], ["f32", "f32"], [4, 16],
        [[len(vector)], [len(palette), 4]], [vec, pal])


# --------------------------------------------------------------------------
# Ed25519, pure stdlib — RFC 8032, transcribed from the algorithm that
# spec/MINI-SPECS.md section 12 states in prose. It is here so the signed-
# message construction can be DEMONSTRATED on real bytes rather than asserted:
# `main()` signs the exact bytes of MANIFEST.example.json with the RFC 8032
# section 7.1 test key, writes the chain, and verifies it before exiting.
#
# NOT constant-time. That is fine here and only here: the key is a published
# test vector, and MINI-SPECS section 12 says signing belongs in an audited
# library for anyone with a key whose secrecy matters.
# --------------------------------------------------------------------------
_P = 2 ** 255 - 19
_Q = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)


def _pt_add(p1, p2):
    a = (p1[1] - p1[0]) * (p2[1] - p2[0]) % _P
    b = (p1[1] + p1[0]) * (p2[1] + p2[0]) % _P
    c = 2 * p1[3] * p2[3] * _D % _P
    d = 2 * p1[2] * p2[2] % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _pt_mul(s, point):
    out = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            out = _pt_add(out, point)
        point = _pt_add(point, point)
        s >>= 1
    return out


def _recover_x(y, sign):
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


_GY = 4 * pow(5, _P - 2, _P) % _P
_GX = _recover_x(_GY, 0)
_G = (_GX, _GY, 1, _GX * _GY % _P)


def _compress(point):
    zinv = pow(point[2], _P - 2, _P)
    x = point[0] * zinv % _P
    y = point[1] * zinv % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(data):
    y = int.from_bytes(data, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _P)


def _expand(secret):
    h = hashlib.sha512(secret).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def _h_modq(data):
    return int.from_bytes(hashlib.sha512(data).digest(), "little") % _Q


def ed25519_public_key(secret):
    return _compress(_pt_mul(_expand(secret)[0], _G))


def ed25519_sign(secret, message):
    a, prefix = _expand(secret)
    pub = _compress(_pt_mul(a, _G))
    r = _h_modq(prefix + message)
    big_r = _compress(_pt_mul(r, _G))
    s = (r + _h_modq(big_r + pub + message) * a) % _Q
    return big_r + int.to_bytes(s, 32, "little")


def ed25519_verify(pub, message, signature):
    if len(pub) != 32 or len(signature) != 64:
        return False
    point_a = _decompress(pub)
    point_r = _decompress(signature[:32])
    if point_a is None or point_r is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _Q:
        return False
    h = _h_modq(signature[:32] + pub + message)
    p1, p2 = _pt_mul(s, _G), _pt_add(point_r, _pt_mul(h, point_a))
    return ((p1[0] * p2[2] - p2[0] * p1[2]) % _P == 0
            and (p1[1] * p2[2] - p2[1] * p1[2]) % _P == 0)


#: RFC 8032 section 7.1 test vector 1. PUBLISHED, therefore not secret, and
#: used here for exactly that reason: everything below is reproducible by
#: anyone holding this file.
RFC8032_SK = bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")

SIG_SIGNED_AT = "2026-08-08T09:00:00Z"
SIG_URI = "urn:werk:fixture:rfc8032-vector-1"
SIG_KIND = "service"
SIG_ZERO = "0" * 64


def signed_message(manifest_sha256, prev_entry_sha256, signed_at, uri, kind):
    """THE construction. spec/SPEC.md section 6, MINI-SPECS section 12.

    Six fields, LF between them, no trailing newline, UTF-8. Nothing is
    JSON-encoded, nothing is length-prefixed and no field may contain an LF.
    """
    return "\n".join([
        "werk-sig/1", manifest_sha256, prev_entry_sha256, signed_at, uri, kind
    ]).encode("utf-8")


def build_signature_example(manifest_bytes):
    """A real one-link chain over the real bytes of MANIFEST.example.json."""
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    msg = signed_message(manifest_sha256, SIG_ZERO, SIG_SIGNED_AT,
                         SIG_URI, SIG_KIND)
    sig = ed25519_sign(RFC8032_SK, msg)
    pub = ed25519_public_key(RFC8032_SK)
    assert ed25519_verify(pub, msg, sig), "the example signature does not verify"
    doc = {
        "algorithm": "ed25519",
        "chain": [{
            "index": 0,
            "manifest_sha256": manifest_sha256,
            "note": ("Signed with the PUBLISHED RFC 8032 section 7.1 test key "
                     "so that anyone holding spec/MINI-SPECS.md section 12 can "
                     "verify it. It proves nothing about authorship and is not "
                     "a trust anchor."),
            "prev_entry_sha256": SIG_ZERO,
            "public_key": pub.hex(),
            "signature": sig.hex(),
            "signed_at": SIG_SIGNED_AT,
            "signer": {"kind": SIG_KIND,
                       "name": "werk example key (RFC 8032 test vector 1)",
                       "role": "author",
                       "uri": SIG_URI},
        }],
        "encoding": "hex-lowercase",
        "manifest_sha256": manifest_sha256,
        "werk_signature": 1,
    }
    return doc, msg, sig, pub


def hexdump(data, annotations):
    """annotations: sorted list of (offset, length, text)."""
    lines = []
    for off, ln, text in annotations:
        chunk = data[off:off + ln]
        hx = " ".join(f"{b:02x}" for b in chunk)
        # wrap the hex at 16 bytes per line, first line carries the note
        rows = [hx[i:i + 47] for i in range(0, len(hx), 48)] or [""]
        lines.append(f"{off:08x}  {rows[0]:<47}  {text}")
        for r in rows[1:]:
            lines.append(f"{'':8}  {r:<47}")
    return "\n".join(lines)


def _section_annotations(data, maps, notes, per_section_records):
    """Annotate every payload section: record 0 alone, then the remainder.

    Splitting record 0 out is the whole point of a worked example -- a reader
    checks its own decoder against ONE record's bytes and then trusts the loop.
    """
    ann, cur = [], None
    for i, m in enumerate(maps):
        prev_end = maps[i - 1]["offset"] + maps[i - 1]["size"] if i else None
        if prev_end is not None and m["offset"] > prev_end:
            ann.append((prev_end, m["offset"] - prev_end,
                        "zero padding to the 16-byte-aligned "
                        '"%s" section' % m["name"]))
        one = m["stride"] if m["size"] else 0
        if one and m["size"] > one:
            ann.append((m["offset"], one,
                        'section "%s" record 0 -- %s' % (m["name"], notes[m["name"]])))
            ann.append((m["offset"] + one, m["size"] - one,
                        'section "%s" records 1..%d'
                        % (m["name"], m["size"] // one - 1)))
        elif m["size"]:
            ann.append((m["offset"], m["size"],
                        'section "%s" -- %s' % (m["name"], notes[m["name"]])))
        else:
            ann.append((m["offset"], 0, 'section "%s" is EMPTY (size 0, legal)'
                        % m["name"]))
        cur = m["offset"] + m["size"]
    if cur is not None and cur < len(data):
        ann.append((cur, len(data) - cur, "trailing padding to a 16-byte boundary"))
    return [a for a in ann if a[1] > 0]


def _decode_gsplat(data, maps, count):
    """Read the payload back the way a consumer does, and print it."""
    by = {m["name"]: m for m in maps}
    c0 = 0.28209479177387814
    out = []
    for i in range(count):
        mean = struct.unpack_from("<3f", data, by["means"]["offset"] + 12 * i)
        scale = struct.unpack_from("<3f", data, by["scales"]["offset"] + 12 * i)
        quat = struct.unpack_from("<4f", data, by["rotations"]["offset"] + 16 * i)
        opac = struct.unpack_from("<f", data, by["opacities"]["offset"] + 4 * i)[0]
        dc = struct.unpack_from("<3f", data, by["sh-dc"]["offset"] + 12 * i)
        rest = [struct.unpack_from("<3f", data,
                                   by["sh-rest"]["offset"] + 12 * (3 * i + c))
                for c in range(3)]
        rgb = tuple(min(1.0, max(0.0, 0.5 + c0 * v)) for v in dc)
        out.append("  Gaussian %d" % i)
        out.append("    mean      %s   metres" % (list(mean),))
        out.append("    scale     %s   metres, linear" % (list(scale),))
        out.append("    rotation  %s   wxyz" % (list(quat),))
        out.append("    opacity   %g" % opac)
        out.append("    sh-dc     %s  ->  rgb_linear %s"
                   % (list(dc), [round(v, 6) for v in rgb]))
        out.append("    sh-rest   coeff1 %s  coeff2 %s  coeff3 %s"
                   % (list(rest[0]), list(rest[1]), list(rest[2])))
    return out


def write_hex_doc(path, binary_name, data, read_alongside, facts, annotations,
                  header, tail):
    """The one renderer every worked hex dump in this directory goes through."""
    text = ["Annotated hex dump of " + binary_name, "=" * 60, "",
            "Generated by make-examples.py in this directory. Read"]
    text += read_alongside
    text += ["", f"file size          : {len(data)} bytes"]
    text += facts
    text.append(f"sha256             : {hashlib.sha256(data).hexdigest()}")
    text.append("")
    text.append("HEX")
    text.append("-" * 60)
    text.append(hexdump(data, annotations))
    text.append("")
    text.append("HEADER, DECODED")
    text.append("-" * 60)
    text.append(json.dumps(mp_decode(header), indent=2, sort_keys=True))
    text.append("")
    text += tail
    text.append("")
    text.append("The header round-trips: re-encoding the decoded map with the")
    text.append("canonical rules of ENVELOPE.layout.txt section 4.3 reproduces")
    text.append("the same bytes. That is checked every time this script runs.")
    assert mp_encode(mp_decode(header)) == header, "canonical round trip failed"
    # LF newlines on every write in this file: .gitattributes pins the whole
    # tree to LF because a spec file whose line endings change between
    # checkouts has a different sha256, and every fixture hashes these bytes.
    # Writing CRLF here would make a rebuild on Windows differ from a rebuild
    # on a fresh clone -- a real determinism bug, found while rebuilding for
    # this wave and fixed rather than worked around.
    path.write_text("\n".join(text) + "\n", encoding="utf-8", newline="\n")


MS_BEGIN = "<!-- BEGIN GENERATED: signature-example (spec/examples/make-examples.py) -->"
MS_END = "<!-- END GENERATED: signature-example -->"


def sync_minispecs(manifest_bytes, doc, msg, sig, pub):
    """Rewrite MINI-SPECS.md section 12.1's worked block from the real values.

    The block is GENERATED rather than transcribed for the reason
    fixtures/record_fixtures.py exists: a number copied into prose in two
    places is a number whose copies cannot disagree loudly. Not circular --
    MANIFEST.example.json does not depend on MINI-SPECS.md.
    """
    path = HERE.parent / "MINI-SPECS.md"
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if MS_BEGIN not in text or MS_END not in text:
        return False
    entry = doc["chain"][0]
    hx = msg.hex()
    rows = ["    %08x  %s" % (i // 2, " ".join(hx[j:j + 2]
                                               for j in range(i, min(i + 64, len(hx)), 2)))
            for i in range(0, len(hx), 64)]
    body = "\n".join([
        MS_BEGIN,
        "",
        "```",
        "the six fields, from chain[0] of spec/examples/SIGNATURE.example.json",
        "  manifest_sha256    %s" % entry["manifest_sha256"],
        "                     (= sha256 of the %d bytes of MANIFEST.example.json)"
        % len(manifest_bytes),
        "  prev_entry_sha256  %s" % entry["prev_entry_sha256"],
        "  signed_at          %s" % entry["signed_at"],
        "  signer.uri         %s" % entry["signer"]["uri"],
        "  signer.kind        %s" % entry["signer"]["kind"],
        "",
        "the message, as text -- the LAST field has NO newline after it",
        ]
        + ["  " + ln + "\\n" for ln in msg.decode("utf-8").split("\n")[:-1]]
        + ["  " + msg.decode("utf-8").split("\n")[-1] + "        <- no trailing LF",
        "",
        "the message, as all %d of its bytes" % len(msg)]
        + rows
        + ["",
           "CHECKPOINT -- compare these before you compare a signature",
           "  len(message)     %d" % len(msg),
           "  sha256(message)  %s" % hashlib.sha256(msg).hexdigest(),
           "",
           "verify",
           "  public_key  %s" % pub.hex(),
           "  signature   %s" % sig.hex()[:64],
           "              %s" % sig.hex()[64:],
           "  ed25519_verify(public_key, message, signature)  ->  TRUE",
           "```",
           "",
           MS_END])
    start = text.index(MS_BEGIN)
    end = text.index(MS_END) + len(MS_END)
    path.write_text(text[:start] + body + text[end:], encoding="utf-8",
                    newline="\n")
    return True


def render_signature_example(manifest_bytes, doc, msg, sig, pub):
    """The worked signed-message construction, byte for byte.

    S-OW-1, measured 2026-08-08: every small model in the open-weights gauntlet
    that touched a signature reported PRESENT-AND-INVALID -- a false tampering
    alarm -- on a package that is signed-and-valid, because the construction
    below lived only in spec/SPEC.md and signature.schema.json and neither had
    fitted in its documentation budget. This file is the fix's worked half.
    """
    entry = doc["chain"][0]
    L = []
    L.append("The werk signed-message construction, worked end to end")
    L.append("=" * 60)
    L.append("")
    L.append("Generated by make-examples.py in this directory. Everything")
    L.append("below is REAL: the message is built from SIGNATURE.example.json's")
    L.append("own fields, over the actual bytes of MANIFEST.example.json in")
    L.append("this same directory, and the signature verifies.")
    L.append("")
    L.append("Read spec/MINI-SPECS.md section 12 (the primitive) and")
    L.append("spec/SPEC.md section 6 (the chain) alongside it.")
    L.append("")
    L.append("STEP 1 -- hash the manifest bytes AS THEY ARE. No reserialising,")
    L.append("no key reordering, no pretty-printing.")
    L.append("-" * 60)
    L.append("  MANIFEST.example.json      %d bytes" % len(manifest_bytes))
    L.append("  sha256                     %s" % entry["manifest_sha256"])
    L.append("")
    L.append("STEP 2 -- build the message. Six fields, LF between them, NO")
    L.append("trailing newline, UTF-8. Nothing is JSON, nothing is length-")
    L.append("prefixed, and no field may itself contain an LF.")
    L.append("-" * 60)
    L.append("  werk-sig/1  LF  manifest_sha256  LF  prev_entry_sha256  LF")
    L.append("  signed_at   LF  signer.uri       LF  signer.kind")
    L.append("")
    L.append("  taken from chain[0] of SIGNATURE.example.json:")
    L.append("    manifest_sha256    %s" % entry["manifest_sha256"])
    L.append("    prev_entry_sha256  %s" % entry["prev_entry_sha256"])
    L.append("      (64 '0' characters for index 0; for index i>0 it is the")
    L.append("       sha256 of the UTF-8 bytes of entry i-1's `signature`")
    L.append("       STRING -- the hex text, not the 64 raw bytes)")
    L.append("    signed_at          %s" % entry["signed_at"])
    L.append("    signer.uri         %s" % entry["signer"]["uri"])
    L.append("    signer.kind        %s" % entry["signer"]["kind"])
    L.append("")
    L.append("  the message as text (\\n shown explicitly):")
    for line in msg.decode("utf-8").split("\n"):
        L.append("    %s\\n" % line)
    L.append("  ...and the LAST \\n above is NOT in the message: %d bytes total."
             % len(msg))
    L.append("")
    L.append("  the message as bytes, all %d of them:" % len(msg))
    hx = msg.hex()
    for i in range(0, len(hx), 64):
        L.append("    %08x  %s" % (i // 2, " ".join(
            hx[j:j + 2] for j in range(i, min(i + 64, len(hx)), 2))))
    L.append("")
    L.append("  CHECKPOINT -- if your bytes differ from these, stop here:")
    L.append("    len(message)     %d" % len(msg))
    L.append("    sha256(message)  %s" % hashlib.sha256(msg).hexdigest())
    L.append("    (sha256 of the MESSAGE is a checkpoint for you only. Ed25519")
    L.append("     hashes the message itself with SHA-512 internally; you do")
    L.append("     NOT pre-hash before calling verify.)")
    L.append("")
    L.append("STEP 3 -- verify. Pure Ed25519 (RFC 8032), not ph, not ctx.")
    L.append("-" * 60)
    L.append("  public_key  %s" % pub.hex())
    L.append("  signature   %s" % sig.hex()[:64])
    L.append("              %s" % sig.hex()[64:])
    L.append("  R = signature[0:32], S = signature[32:64] little-endian")
    L.append("")
    L.append("  ed25519_verify(public_key, message, signature)  ->  TRUE")
    L.append("")
    L.append("  and the three checks that make the verdict mean something:")
    L.append("    S < L                                            (canonical S)")
    L.append("    chain[0].prev_entry_sha256 == 64 zeros           (chain start)")
    L.append("    chain[-1].manifest_sha256 == sha256(MANIFEST.json bytes held)")
    L.append("                                                     (current state)")
    L.append("")
    L.append("STEP 4 -- report ONE of the four tokens, never a guess.")
    L.append("-" * 60)
    L.append("  signed-and-valid     every link verified, as here")
    L.append("  absent               no SIGNATURE.json at all")
    L.append("  present-and-invalid  a link FAILED -- tampering under a signature")
    L.append("  unverified           you did not perform the check")
    L.append("")
    L.append("  `unverified` is the correct answer when you have no Ed25519")
    L.append("  implementation, or when you have one and chose not to run it.")
    L.append("  Reporting `present-and-invalid` because you could not build the")
    L.append("  message is a FALSE TAMPERING ALARM and is the worst wrong answer")
    L.append("  this format makes available (spec finding S-OW-1).")
    L.append("")
    return "\n".join(L) + "\n"


def ph(path):
    """Deterministic placeholder hash: sha256 of a documented ASCII string.

    Reproduce with:  sha256(("werk example placeholder: " + path).encode())
    These are NOT hashes of real bytes and the example manifest says so.
    """
    return hashlib.sha256(("werk example placeholder: " + path).encode()).hexdigest()


CONVENTIONS = {
    "endianness": "le",
    "units_per_meter": 1.0,
    "length_unit": "metre",
    "angle_unit": "radian",
    "time_unit": "second",
    "mass_unit": "kilogram",
    "up_axis": "y",
    "forward_axis": "-z",
    "right_axis": "+x",
    "handedness": "right",
    "winding": "ccw",
    "quat_order": "wxyz",
    "oct_encoding_pole": "y",
    "sh_l1_order": ["dc", "y", "z", "x"],
    "color_space_default": "srgb",
    "uv_origin": "top-left",
    "alignment_bytes": 16,
    "text_encoding": "utf-8",
    "id_case": "kebab-case",
    "hash_algorithm": "sha256",
    "signature_algorithm": "ed25519",
}


def node(node_id, ntype, files, note, epistemic, edges=(), meta=None,
         producer=None, inputs=None, part_id=None, material_id=None):
    version = {
        "v": 1,
        "files": [{"path": p, "sha256": ph(p), "size": s,
                   **({"media_type": m} if m else {}),
                   **({"role": r} if r else {})}
                  for (p, s, m, r) in files],
        "note": note,
        "producer": producer or {"tool": "werk-example", "version": "0.1"},
        "epistemic": epistemic,
        "created": "2026-08-08T09:00:00Z",
    }
    if epistemic in ("measured", "inferred"):
        assert inputs, node_id
        version["input_files"] = list(inputs)
        h = hashlib.sha256()
        for p in inputs:
            h.update(bytes.fromhex(ph(p)))
        h.update(b"{}")
        version["input_hash"] = h.hexdigest()
        version["input_params"] = {}
    n = {"node_id": node_id, "type": ntype, "versions": [version],
         "active": 1, "edges": [dict(e) for e in edges]}
    if part_id:
        n["part_id"] = part_id
    if material_id:
        n["material_id"] = material_id
    if meta:
        n["meta"] = meta
    return n


def build_manifest():
    nodes = [
        node("spec", "core.spec",
             [("spec/SPEC.md", 21000, "text/markdown", None),
              ("spec/MINI-SPECS.md", 19000, "text/markdown", None),
              ("spec/facets.json", 9000, "application/json", None),
              ("spec/schemas/manifest.schema.json", 27000, "application/json", None),
              ("spec/layouts/ENVELOPE.layout.txt", 13000, "text/plain", None)],
             "The specification this package conforms to, travelling with it "
             "so the file explains itself (law 2).",
             "authored"),
        node("license", "core.license",
             [("LICENSE", 1075, "text/plain", None)],
             "Full licence text embedded, never a link (law 7).",
             "authored"),
        node("readme", "core.readme",
             [("README.txt", 480, "text/plain", None)],
             "One paragraph for a human who opened the zip by hand.",
             "authored"),
        node("loader-python", "core.loader",
             [("loaders/werk_read.py", 14000, "text/x-python", None)],
             "Bootstrap reader so the package carries a way to read itself; "
             "stdlib only, read-only.",
             "authored",
             meta={"language": "python", "form": "source",
                   "entrypoint": "loaders/werk_read.py",
                   "toolchain": "python>=3.8", "dependencies": [],
                   "capabilities": ["read-manifest", "verify-hashes",
                                    "read-envelope", "read-audio"]}),
        node("geom-game", "core.geom.game",
             [("geometry/game.glb", 184320, "model/gltf-binary", None)],
             "Authored game mesh: the representation every consumer can use.",
             "authored", part_id="crate"),
        node("geom-lod1", "core.geom.lod",
             [("geometry/lod1.glb", 61440, "model/gltf-binary", None)],
             "First decimation step; silhouette error measured against the "
             "game mesh, not estimated.",
             "measured", inputs=["geometry/game.glb"],
             edges=[{"to": "geom-game", "kind": "requires", "role": "lod-of"}],
             part_id="crate",
             meta={"lod_level": 1, "screen_space_error_px": 2.4,
                   "reference_resolution_px": 1080, "triangle_count": 1208,
                   "vertex_count": 742}),
        node("tex-basecolor", "core.tex",
             [("textures/crate-basecolor.png", 1048576, "image/png", None)],
             "Base colour map as delivered by the source asset.",
             "authored", material_id="oak-slats",
             meta={"color_space": "srgb", "usage": "base-color",
                   "width": 2048, "height": 2048, "channels": 4,
                   "bit_depth": 8}),
        node("mat-oak", "core.material",
             [("materials/oak-slats.json", 1400, "application/json", None)],
             "Metallic-roughness parameters for the slatted oak body.",
             "authored", material_id="oak-slats",
             edges=[{"to": "tex-basecolor", "kind": "enhances",
                     "role": "sampled-by"}]),
        node("bounds", "core.phys.bounds",
             [("physics/bounds.json", 900, "application/json", None)],
             "AABB and true minimal sphere, computed with Welzl rather than "
             "circumscribing the box.",
             "measured", inputs=["geometry/game.glb"],
             edges=[{"to": "geom-game", "kind": "requires",
                     "role": "measured-from"}]),
        node("rest-poses", "core.pose.rest",
             [("poses/rest.wkrp", 176, None, None)],
             "Settled orientations from a drop simulation; probabilities are "
             "measured over the trials recorded in the header.",
             "measured", inputs=["geometry/game.glb", "physics/bounds.json"],
             edges=[{"to": "geom-game", "kind": "enhances",
                     "role": "measured-from"}]),
        node("semantics", "core.semantics",
             [("semantics/semantics.json", 4800, "application/json", None)],
             "Facet tags, style embedding and palette; the store indexes a "
             "dropped file from this node alone (law 9).",
             "inferred", inputs=["textures/crate-basecolor.png"]),
        node("props", "core.props",
             [("properties/props.json", 6400, "application/json", None)],
             "Simulation properties per material region, every value stamped "
             "individually because most of them are a model's guess.",
             "inferred", inputs=["semantics/semantics.json"],
             edges=[{"to": "semantics", "kind": "enhances"}]),
        node("audio-package", "core.audio.package",
             [("audio/package.json", 12800, "application/json", None)],
             "Index of the sound world: described objects, effect plan, and "
             "every take with its score.",
             "measured", inputs=["geometry/game.glb"]),
        node("audio-crate-impact", "core.audio.effect",
             [("audio/crate/crate-impact-hard-surface.wav", 264644, "audio/wav", "best"),
              ("audio/crate/crate-impact-hard-surface.raw.wav", 264644, "audio/wav", "raw"),
              ("audio/crate/crate-impact-hard-surface.var2.wav", 264644, "audio/wav", "variation"),
              ("audio/crate/crate-impact-hard-surface.json", 1600, "application/json", "descriptor")],
             "Hard impact one-shot; refinement kept the isolated event and "
             "raised the CLAP score, so it shipped refined.",
             "measured", inputs=["audio/package.json"],
             edges=[{"to": "audio-package", "kind": "requires"}],
             material_id="oak-slats"),
    ]

    # SPEC.md section 2.1 (S-XV-4 / S-OW-2): a version with more than one file
    # says WHICH ONE IS THE PAYLOAD, so nothing downstream has to take files[0].
    # The audio node below is the exact shape that produced the measured
    # failure: its files[] holds a best take, a raw take, a variation and a
    # descriptor, and `primary.sound` points at the node, not at a file.
    payload_role = {"core.audio.effect": "best", "core.audio.ambience": "best",
                    "core.imposter": "atlas", "core.recipe": "record"}
    for n in nodes:
        for v in n["versions"]:
            if len(v["files"]) < 2:
                continue
            hit = [f for f in v["files"]
                   if f.get("role") == payload_role.get(n["type"])]
            if len(hit) == 1:
                v["payload_file"] = hit[0]["path"]

    # `spec_sha256` (SPEC.md section 2, MANDATORY since S-29) by the real
    # algorithm over the spec/ files THIS manifest declares: for each path in
    # ascending byte order, the path, 0x0A, the file's sha256 as 32 raw bytes,
    # 0x0A; sha256 of the lot. The per-file hashes here are placeholders, so
    # the result is the digest of placeholders - but it IS the digest of what
    # the manifest lists, which is the only thing the field claims, and it is
    # what makes this file valid against its own schema. It was missing from
    # this example from the day the field became mandatory until 2026-10-13,
    # while spec/README.md called the file schema-valid (finding F-AC-1).
    spec_decl = {}
    for n in nodes:
        for v in n["versions"]:
            for f in v["files"]:
                if f["path"].startswith("spec/"):
                    spec_decl[f["path"]] = f["sha256"]
    acc = b""
    for path in sorted(spec_decl, key=lambda q: q.encode("utf-8")):
        acc += path.encode("utf-8") + b"\n" + bytes.fromhex(spec_decl[path]) + b"\n"
    spec_sha256 = hashlib.sha256(acc).hexdigest()

    return {
        "werk": {"major": 1, "minor": 0},
        "profile": "3d-entity/1",
        "manifest_schema": "spec/schemas/manifest.schema.json",
        "spec_sha256": spec_sha256,
        "entity": {
            "uuid": "6f1c2b7a-9d3e-4a10-8c55-2b8e41d0a7c3",
            "name": "Wooden crate",
            "summary": ("ILLUSTRATIVE EXAMPLE, not a real package. The file "
                        "sizes are plausible and the sha256 values are "
                        "deterministic placeholders, not hashes of real "
                        "bytes: each one is sha256 of the ASCII string "
                        "'werk example placeholder: <path>'. Everything else "
                        "- structure, conventions, edges, stamps - is exactly "
                        "what a real manifest looks like, and this file "
                        "validates against manifest.schema.json. IT IS ALSO "
                        "ABRIDGED, and you must not model completeness on it: "
                        "the core.spec node lists five representative spec/ "
                        "files and a core.loader node lists one of the three "
                        "loaders, whereas SPEC.md section 2 requires that "
                        "EVERY byte in a real container be reachable from "
                        "exactly one node version's files[] - so a real "
                        "package's core.spec node lists every file under "
                        "spec/, and there is one core.loader node per loader. "
                        "For a complete, conformant, byte-real package see "
                        "the conformance fixture, not this file."),
            "created": "2026-08-08T09:00:00Z",
        },
        "conventions": CONVENTIONS,
        # `primary` names NODES. Following primary.sound to its node is half the
        # journey; SPEC.md section 2.1 is the other half -- read that version's
        # `payload_file`, never files[0].
        "primary": {"mesh": "geom-game", "sound": "audio-crate-impact"},
        "container": {
            "form": "zip",
            "zip_compression": "store",
            "entry_order": [
                "MANIFEST.json", "SIGNATURE.json", "LICENSE", "README.txt",
                "loaders/werk_read.py", "spec/", "semantics/semantics.json",
                "imposters/preview-albedo.png",
                "audio/crate/crate-impact-hard-surface.wav",
                "geometry/", "textures/", "physics/", "poses/", "properties/",
                "audio/", "provenance/",
            ],
            "preview_prefix_bytes": 393216,
        },
        "license": {"spdx_id": "CC-BY-4.0", "file": "LICENSE",
                    "sha256": ph("LICENSE")},
        "schemas": {
            "core.material": "spec/schemas/core.material.schema.json",
            "core.imposter": "spec/schemas/core.imposter.schema.json",
            "core.phys.colliders": "spec/schemas/core.phys.colliders.schema.json",
            "core.phys.bounds": "spec/schemas/core.phys.bounds.schema.json",
            "core.phys.body": "spec/schemas/core.phys.body.schema.json",
            "core.skeleton": "spec/schemas/core.skeleton.schema.json",
            "core.anim.clip": "spec/schemas/core.anim.clip.schema.json",
            "core.audio.package": "spec/schemas/core.audio.package.schema.json",
            "core.audio.effect": "spec/schemas/core.audio.effect.schema.json",
            "core.audio.ambience": "spec/schemas/core.audio.effect.schema.json",
            "core.destruct": "spec/schemas/core.destruct.schema.json",
            "core.props": "spec/schemas/core.props.schema.json",
            "core.semantics": "spec/schemas/core.semantics.schema.json",
            "core.provenance": "spec/schemas/core.provenance.schema.json",
        },
        "layouts": {
            "core.field.flow": "spec/layouts/flowfield.layout.txt",
            "core.pose.rest": "spec/layouts/restposes.layout.txt",
            "core.anim.clip": "spec/layouts/animclip.layout.txt",
            "core.skeleton": "spec/layouts/skeleton.layout.txt",
            "core.imposter": "spec/layouts/imposter.layout.txt",
        },
        "parts": [
            {"part_id": "crate", "name": "Crate body", "parent": None,
             "transform": {"translation": [0.0, 0.0, 0.0],
                           "rotation": [1.0, 0.0, 0.0, 0.0],
                           "scale": [1.0, 1.0, 1.0]}},
            {"part_id": "crate-lid", "name": "Lid", "parent": "crate",
             "transform": {"translation": [0.0, 0.42, 0.0],
                           "rotation": [1.0, 0.0, 0.0, 0.0],
                           "scale": [1.0, 1.0, 1.0]}},
        ],
        "materials": [
            {"material_id": "oak-slats", "part_id": "crate",
             "name": "Oak slats", "class": "wood"},
            {"material_id": "iron-banding", "part_id": "crate",
             "name": "Iron banding", "class": "metal"},
        ],
        "nodes": nodes,
        "signature_file": "SIGNATURE.json",
        "generator": {"tool": "spec/examples/make-examples.py", "version": "1"},
    }


def main():
    HERE.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest()
    (HERE / "MANIFEST.example.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")

    poses = [
        # (quat wxyz, contacts in model space, probability, support area m^2)
        ([1.0, 0.0, 0.0, 0.0],
         [(-0.25, 0.0, -0.25), (0.25, 0.0, -0.25),
          (0.25, 0.0, 0.25), (-0.25, 0.0, 0.25)],
         0.62, 0.25),
        ([0.7071067811865476, 0.7071067811865476, 0.0, 0.0],
         [(-0.25, 0.0, -0.21), (0.25, 0.0, -0.21), (0.0, 0.0, 0.21)],
         0.38, 0.105),
    ]
    data, header, origin, off0, off1 = build_wkrp(
        poses,
        {"trials": 4096, "floor_normal": [0.0, 1.0, 0.0],
         "settle_epsilon_m": 0.0005, "merge_angle_deg": 5.0,
         "producer": {"tool": "werk-example", "version": "0.1"},
         "epistemic": "measured"},
    )
    (HERE / "restposes.example.wkrp").write_bytes(data)

    n_contacts = sum(len(p[1]) for p in poses)
    contacts_size = 12 * n_contacts
    ann = [
        (0, 4, 'magic "WKRP"'),
        (4, 4, "u32 LE version = 1"),
        (8, 4, f"u32 LE header_len = {len(header)}"),
        (12, len(header), "MessagePack header (decoded below)"),
        (12 + len(header), origin - (12 + len(header)),
         f"zero padding to payload_origin = {origin}"),
        (off0, 32, "pose entry 0: quat wxyz | contact_first u32 | "
                   "contact_count u32 | probability f32 | support_area f32"),
        (off0 + 32, 32, "pose entry 1"),
        (off0 + 64, off1 - (off0 + 64),
         "zero padding to the 16-byte-aligned contacts section"),
        (off1, 12, "contact 0: f32 x, y, z"),
        (off1 + 12, contacts_size - 12,
         f"contacts 1..{n_contacts - 1}"),
        (off1 + contacts_size, len(data) - (off1 + contacts_size),
         "trailing padding to a 16-byte boundary"),
    ]
    ann = sorted(a for a in ann if a[1] > 0)

    text = []
    text.append("Annotated hex dump of restposes.example.wkrp")
    text.append("=" * 60)
    text.append("")
    text.append("Generated by make-examples.py in this directory. Read")
    text.append("spec/layouts/ENVELOPE.layout.txt and")
    text.append("spec/layouts/restposes.layout.txt alongside it.")
    text.append("")
    text.append(f"file size          : {len(data)} bytes")
    text.append(f"header_len         : {len(header)}")
    text.append(f"payload_origin     : {origin}   (= 16 * ceil((12+"
                f"{len(header)})/16))")
    text.append(f"poses section      : offset {off0}, size 64, stride 32, "
                f"2 entries")
    text.append(f"contacts section   : offset {off1}, size {contacts_size}, "
                f"stride 12, {n_contacts} points")
    text.append(f"payload_size       : {len(data) - origin}   "
                f"(includes the trailing alignment padding, so "
                f"payload_origin + payload_size == file size)")
    text.append(f"sha256             : {hashlib.sha256(data).hexdigest()}")
    text.append("")
    text.append("HEX")
    text.append("-" * 60)
    text.append(hexdump(data, ann))
    text.append("")
    text.append("HEADER, DECODED")
    text.append("-" * 60)
    text.append(json.dumps(mp_decode(header), indent=2, sort_keys=True))
    text.append("")
    text.append("The header round-trips: re-encoding the decoded map with the")
    text.append("canonical rules of ENVELOPE.layout.txt section 4.3 reproduces")
    text.append("the same bytes. That is checked every time this script runs.")
    (HERE / "restposes.example.hex.txt").write_text(
        "\n".join(text) + "\n", encoding="utf-8", newline="\n")

    assert mp_encode(mp_decode(header)) == header, "canonical round trip failed"

    # ---------------------------------------------------------------- WKGS
    # Three Gaussians with sh_degree 1. Values chosen so that every one of
    # them is exactly representable in binary32 and therefore reads back from
    # the dump without a rounding argument.
    gaussians = [
        # mean, scale (metres, LINEAR), quat wxyz, opacity, sh-dc, sh-rest[3][3]
        ((0.0, 0.0, 0.0), (0.25, 0.125, 0.25), (1.0, 0.0, 0.0, 0.0), 1.0,
         (1.0, 0.0, -1.0),
         [(0.5, 0.25, 0.125), (-0.5, 0.25, 0.0), (0.0, -0.25, 0.5)]),
        ((0.5, 0.25, -0.5), (0.0625, 0.0625, 0.5), (0.5, 0.5, 0.5, 0.5), 0.5,
         (0.0, 0.5, 0.25),
         [(0.25, 0.0, -0.125), (0.125, 0.5, 0.25), (-0.25, 0.0, 0.0)]),
        ((-0.5, 1.0, 0.25), (0.5, 0.25, 0.0625), (0.0, 1.0, 0.0, 0.0), 0.0,
         (-1.0, -0.5, 0.25),
         [(0.0, 0.0, 0.0), (0.5, -0.5, 0.125), (0.25, 0.25, -0.25)]),
    ]
    gdata, gheader, gorigin, gmaps = build_wkgs(
        gaussians, 1,
        {"source_convention": "inria-3dgs/1",
         "activation": {"opacity": "sigmoid", "scale": "exp", "sh": "identity"},
         "bounds": {"min": [-0.5, 0.0, -0.5], "max": [0.5, 1.0, 0.25]},
         "producer": {"tool": "werk-example", "version": "0.1"},
         "epistemic": "authored"})
    (HERE / "gsplat.example.wkgs").write_bytes(gdata)
    gann = [(0, 4, 'magic "WKGS"'), (4, 4, "u32 LE version = 1"),
            (8, 4, f"u32 LE header_len = {len(gheader)}"),
            (12, len(gheader), "MessagePack header (decoded below)"),
            (12 + len(gheader), gorigin - (12 + len(gheader)),
             f"zero padding to payload_origin = {gorigin}")]
    gnotes = {
        "means": "Gaussian centres, f32 x,y,z, METRES, werk model space "
                 "(+Y up, -Z forward, right-handed)",
        "scales": "per-axis standard deviations, f32, METRES, LINEAR (already "
                  "exp()'d): Sigma = R diag(sx^2,sy^2,sz^2) R^T",
        "rotations": "unit quaternions, f32, order w,x,y,z, w >= 0",
        "opacities": "alpha in [0,1], f32, LINEAR (already sigmoid()'d)",
        "sh-dc": "SH coefficient 0, f32 R,G,B. rgb = clamp(0.5 + "
                 "0.28209479177387814*dc, 0, 1)",
        "sh-rest": "SH coefficients 1..K-1, COEFFICIENT-MAJOR [count,K-1,3]: "
                   "record i is coeff1 RGB, coeff2 RGB, coeff3 RGB for "
                   "Gaussian i (the source PLY stores the TRANSPOSE)",
    }
    gann += _section_annotations(gdata, gmaps, gnotes, len(gaussians))
    write_hex_doc(
        HERE / "gsplat.example.hex.txt", "gsplat.example.wkgs", gdata,
        ["spec/layouts/ENVELOPE.layout.txt and",
         "spec/layouts/gsplat.layout.txt alongside it."],
        [f"header_len         : {len(gheader)}",
         f"payload_origin     : {gorigin}   (= 16 * ceil((12+{len(gheader)})/16))",
         f"count              : {len(gaussians)} Gaussians, sh_degree 1, "
         f"sh_coeff_count 4"]
        + [f"{m['name']:<18} : offset {m['offset']}, size {m['size']}, "
           f"stride {m['stride']}, shape {m['shape']}" for m in gmaps],
        gann, gheader,
        ["Decoded, the three Gaussians are:", ""]
        + _decode_gsplat(gdata, gmaps, len(gaussians)))

    # ---------------------------------------------------------------- WKEM
    vector = [0.5, -0.25, 0.125, 0.0, 0.75, -0.5, 0.25, 0.0625]
    palette = [(0.5, 0.25, 0.125, 0.5), (0.25, 0.25, 0.25, 0.375),
               (1.0, 1.0, 0.5, 0.125)]
    edata, eheader, eorigin, emaps = build_wkem(
        vector, palette,
        {"model": "werk.descriptor.labhog/1", "normalized": False,
         "metric": "cosine", "colour_space": "linear-srgb",
         "source_path": "textures/crate-basecolor.png", "tolerance": 0.001,
         "producer": {"tool": "werk-example", "version": "0.1"},
         "epistemic": "measured"})
    (HERE / "embedding.example.wkem").write_bytes(edata)
    eann = [(0, 4, 'magic "WKEM"'), (4, 4, "u32 LE version = 1"),
            (8, 4, f"u32 LE header_len = {len(eheader)}"),
            (12, len(eheader), "MessagePack header (decoded below)"),
            (12 + len(eheader), eorigin - (12 + len(eheader)),
             f"zero padding to payload_origin = {eorigin}")]
    eann += _section_annotations(
        edata, emaps,
        {"vector": "the descriptor, f32, contiguous. stride == element size, "
                   "so this is the FIRST branch of the consistency rule",
         "palette": "swatches, f32 (r,g,b,weight), sorted by weight "
                    "DESCENDING. stride 16 > element size 4, so this is the "
                    "SECOND branch"},
        max(len(vector), len(palette)))
    write_hex_doc(
        HERE / "embedding.example.hex.txt", "embedding.example.wkem", edata,
        ["spec/layouts/ENVELOPE.layout.txt and",
         "spec/layouts/embedding.layout.txt alongside it."],
        [f"header_len         : {len(eheader)}",
         f"payload_origin     : {eorigin}   (= 16 * ceil((12+{len(eheader)})/16))",
         f"dim                : {len(vector)}",
         f"swatch_count       : {len(palette)}"]
        + [f"{m['name']:<18} : offset {m['offset']}, size {m['size']}, "
           f"stride {m['stride']}, shape {m['shape']}" for m in emaps],
        eann, eheader,
        ["Decoded:", "",
         "  vector  = " + ", ".join(
             repr(v) for v in struct.unpack_from(
                 "<%df" % len(vector), edata, emaps[0]["offset"])),
         "  palette = " + "; ".join(
             "(%g, %g, %g) weight %g" % struct.unpack_from(
                 "<4f", edata, emaps[1]["offset"] + 16 * i)
             for i in range(len(palette)))])

    # ----------------------------------------------------------- SIGNATURE
    manifest_bytes = (HERE / "MANIFEST.example.json").read_bytes()
    sigdoc, sigmsg, sigbytes, sigpub = build_signature_example(manifest_bytes)
    (HERE / "SIGNATURE.example.json").write_text(
        json.dumps(sigdoc, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (HERE / "signature.example.txt").write_text(
        render_signature_example(manifest_bytes, sigdoc, sigmsg, sigbytes,
                                 sigpub), encoding="utf-8", newline="\n")
    synced = sync_minispecs(manifest_bytes, sigdoc, sigmsg, sigbytes, sigpub)

    print(f"MANIFEST.example.json      {len(json.dumps(manifest))} bytes of JSON")
    print(f"restposes.example.wkrp     {len(data)} bytes, "
          f"sha256 {hashlib.sha256(data).hexdigest()[:16]}...")
    print("restposes.example.hex.txt  written")
    print(f"gsplat.example.wkgs        {len(gdata)} bytes, "
          f"sha256 {hashlib.sha256(gdata).hexdigest()[:16]}...")
    print("gsplat.example.hex.txt     written")
    print(f"embedding.example.wkem     {len(edata)} bytes, "
          f"sha256 {hashlib.sha256(edata).hexdigest()[:16]}...")
    print("embedding.example.hex.txt  written")
    print(f"SIGNATURE.example.json     signature "
          f"{sigbytes.hex()[:16]}..., verifies")
    print("signature.example.txt      written")
    print("MINI-SPECS.md 12.1         %s"
          % ("worked block re-synced" if synced
             else "NOT synced (markers absent -- reading from a package copy?)"))


# --------------------------------------------------------------------------
# Minimal MessagePack reader for the same subset — used to prove the round
# trip, and a second executable statement of ENVELOPE section 4.
# --------------------------------------------------------------------------
def mp_decode(buf):
    val, off = _mp_read(buf, 0)
    if off != len(buf):
        raise ValueError("trailing bytes after MessagePack value")
    return val


def _mp_read(b, o):
    c = b[o]
    o += 1
    if c <= 0x7F:
        return c, o
    if c >= 0xE0:
        return c - 256, o
    if 0xA0 <= c <= 0xBF:
        n = c & 0x1F
        return b[o:o + n].decode("utf-8"), o + n
    if 0x90 <= c <= 0x9F:
        return _mp_array(b, o, c & 0x0F)
    if 0x80 <= c <= 0x8F:
        return _mp_map(b, o, c & 0x0F)
    if c == 0xC0:
        return None, o
    if c == 0xC2:
        return False, o
    if c == 0xC3:
        return True, o
    if c in (0xC7, 0xC8, 0xC9, 0xC1) or 0xD4 <= c <= 0xD8:
        raise ValueError(f"format byte 0x{c:02x} is banned in werk headers")
    fixed = {0xCC: (">B", 1), 0xCD: (">H", 2), 0xCE: (">I", 4), 0xCF: (">Q", 8),
             0xD0: (">b", 1), 0xD1: (">h", 2), 0xD2: (">i", 4), 0xD3: (">q", 8),
             0xCA: (">f", 4), 0xCB: (">d", 8)}
    if c in fixed:
        fmt, n = fixed[c]
        return struct.unpack_from(fmt, b, o)[0], o + n
    lenpfx = {0xD9: (">B", 1, "str"), 0xDA: (">H", 2, "str"), 0xDB: (">I", 4, "str"),
              0xC4: (">B", 1, "bin"), 0xC5: (">H", 2, "bin"), 0xC6: (">I", 4, "bin"),
              0xDC: (">H", 2, "arr"), 0xDD: (">I", 4, "arr"),
              0xDE: (">H", 2, "map"), 0xDF: (">I", 4, "map")}
    if c in lenpfx:
        fmt, n, kind = lenpfx[c]
        ln = struct.unpack_from(fmt, b, o)[0]
        o += n
        if kind == "str":
            return b[o:o + ln].decode("utf-8"), o + ln
        if kind == "bin":
            return bytes(b[o:o + ln]), o + ln
        if kind == "arr":
            return _mp_array(b, o, ln)
        return _mp_map(b, o, ln)
    raise ValueError(f"unknown MessagePack format byte 0x{c:02x}")


def _mp_array(b, o, n):
    out = []
    for _ in range(n):
        v, o = _mp_read(b, o)
        out.append(v)
    return out, o


def _mp_map(b, o, n):
    out = {}
    for _ in range(n):
        k, o = _mp_read(b, o)
        v, o = _mp_read(b, o)
        out[k] = v
    return out, o


if __name__ == "__main__":
    main()
