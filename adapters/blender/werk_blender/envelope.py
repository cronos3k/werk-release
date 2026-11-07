"""Canonical MessagePack + the werk binary envelope, writer side.

`spec/layouts/ENVELOPE.layout.txt` is the authority; this implements section 4
(the MessagePack subset, including 4.3's canonical-encoding MUSTs) and
sections 1 and 5 (the frame and the section rules).

Only the WRITER lives here. Reading an envelope is already solved by the
vendored `werk_read.read_envelope`, and the gate checks this writer against
that reader rather than against itself — two implementations that share code
cannot disagree, which is the same reason werk-core was tested against
`spec/examples/make-examples.py` instead of against a re-reading of the prose.

Canonical encoding matters more than it looks: it is what makes two exports of
the same clip hash the same, which is what makes the store dedup them and the
round-trip gate meaningful.
"""

import math
import struct


# --- MessagePack, canonical writer (ENVELOPE section 4.3) ------------------

def mp_encode(value):
    out = bytearray()
    _mp_write(out, value)
    return bytes(out)


def _mp_write(out, v):
    # bool before int: in Python `True` is an int, and encoding it as 1 would
    # be a silent type change in someone else's header.
    if v is None:
        out.append(0xC0)
    elif v is True:
        out.append(0xC3)
    elif v is False:
        out.append(0xC2)
    elif isinstance(v, int):
        _mp_int(out, v)
    elif isinstance(v, float):
        if v.is_integer() and abs(v) < 2 ** 53:
            # NOT collapsed to an int: 4.3 says encode every NON-INTEGRAL
            # number as float64, which leaves integral floats free — but a
            # rate_hz that silently became an int would change the header's
            # type and break a reader that checks it. Keep the float.
            pass
        if math.isnan(v) or math.isinf(v):
            raise ValueError("no NaN and no infinity may appear in a core payload "
                             "(ENVELOPE section 6)")
        out.append(0xCB)
        out += struct.pack(">d", v)
    elif isinstance(v, str):
        b = v.encode("utf-8")
        n = len(b)
        if n <= 31:
            out.append(0xA0 | n)
        elif n <= 0xFF:
            out += struct.pack(">BB", 0xD9, n)
        elif n <= 0xFFFF:
            out += struct.pack(">BH", 0xDA, n)
        else:
            out += struct.pack(">BI", 0xDB, n)
        out += b
    elif isinstance(v, (bytes, bytearray)):
        n = len(v)
        if n <= 0xFF:
            out += struct.pack(">BB", 0xC4, n)
        elif n <= 0xFFFF:
            out += struct.pack(">BH", 0xC5, n)
        else:
            out += struct.pack(">BI", 0xC6, n)
        out += bytes(v)
    elif isinstance(v, (list, tuple)):
        n = len(v)
        if n <= 15:
            out.append(0x90 | n)
        elif n <= 0xFFFF:
            out += struct.pack(">BH", 0xDC, n)
        else:
            out += struct.pack(">BI", 0xDD, n)
        for item in v:
            _mp_write(out, item)
    elif isinstance(v, dict):
        # 4.3: map keys sorted ascending by RAW UTF-8 byte sequence, and never
        # emit nil for an absent optional key — omit the key instead.
        items = [(k, val) for k, val in v.items() if val is not None]
        items.sort(key=lambda kv: kv[0].encode("utf-8"))
        n = len(items)
        if n <= 15:
            out.append(0x80 | n)
        elif n <= 0xFFFF:
            out += struct.pack(">BH", 0xDE, n)
        else:
            out += struct.pack(">BI", 0xDF, n)
        for k, val in items:
            if not isinstance(k, str):
                raise ValueError("werk header map keys must be strings, got %r" % (k,))
            _mp_write(out, k)
            _mp_write(out, val)
    else:
        raise ValueError("no canonical werk-header encoding for %r" % (type(v),))


def _mp_int(out, v):
    """The SHORTEST encoding that represents the integer exactly (4.3)."""
    if 0 <= v <= 0x7F:
        out.append(v)
    elif -32 <= v < 0:
        out.append(v + 256)
    elif 0 <= v <= 0xFF:
        out += struct.pack(">BB", 0xCC, v)
    elif 0 <= v <= 0xFFFF:
        out += struct.pack(">BH", 0xCD, v)
    elif 0 <= v <= 0xFFFFFFFF:
        out += struct.pack(">BI", 0xCE, v)
    elif 0 <= v <= 0xFFFFFFFFFFFFFFFF:
        out += struct.pack(">BQ", 0xCF, v)
    elif -0x80 <= v < 0:
        out += struct.pack(">Bb", 0xD0, v)
    elif -0x8000 <= v < 0:
        out += struct.pack(">Bh", 0xD1, v)
    elif -0x80000000 <= v < 0:
        out += struct.pack(">Bi", 0xD2, v)
    else:
        out += struct.pack(">Bq", 0xD3, v)


# --- the envelope frame (ENVELOPE sections 1 and 5) ------------------------

def align16(n):
    return (n + 15) // 16 * 16


DTYPE_SIZE = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4,
              "u64": 8, "i64": 8, "f32": 4, "f64": 8}


def build(magic, version, header, sections):
    """Assemble one envelope file.

    `sections` is an ordered list of (name, dtype, shape, stride, bytes). Their
    absolute offsets, sizes, `payload_origin` and `payload_size` are computed
    here and written into the header, then the whole thing is checked against
    ENVELOPE section 3's consistency algorithm before any bytes leave.

    `payload_origin` depends on `header_len`, and `header_len` depends on
    `payload_origin` because it is a header key. That is a fixed point, and it
    is iterated rather than guessed: adding the offsets can push a
    variable-length integer up a size class, which changes the header length,
    which moves the offsets. Two rounds is the normal case; the loop is bounded
    so a pathological input fails loudly instead of spinning.
    """
    if not isinstance(magic, bytes) or len(magic) != 4:
        raise ValueError("magic must be exactly 4 ASCII bytes, got %r" % (magic,))

    hdr = dict(header)
    hdr["endianness"] = "le"

    payload_origin = 0
    for _round in range(8):
        cursor = payload_origin
        decls = []
        for name, dtype, shape, stride, data in sections:
            cursor = align16(cursor)
            decls.append({"name": name, "offset": cursor, "size": len(data),
                          "dtype": dtype, "shape": list(shape), "stride": stride})
            cursor += len(data)
        hdr["sections"] = decls
        hdr["payload_origin"] = payload_origin
        hdr["payload_size"] = max(0, align16(cursor) - payload_origin)
        header_bytes = mp_encode(hdr)
        recomputed = align16(12 + len(header_bytes))
        if recomputed == payload_origin:
            break
        payload_origin = recomputed
    else:
        raise ValueError("envelope header length did not converge")

    for d in decls:
        _check_section(d)

    out = bytearray()
    out += magic
    out += struct.pack("<II", version, len(header_bytes))
    out += header_bytes
    out += b"\x00" * (payload_origin - len(out))
    for d, (_n, _dt, _sh, _st, data) in zip(decls, sections):
        out += b"\x00" * (d["offset"] - len(out))
        out += data
    out += b"\x00" * (align16(len(out)) - len(out))

    if len(out) != payload_origin + hdr["payload_size"]:
        raise ValueError("envelope size %d != payload_origin %d + payload_size %d"
                         % (len(out), payload_origin, hdr["payload_size"]))
    return bytes(out)


def _check_section(d):
    """ENVELOPE section 3's consistency rule, as the algorithm it is."""
    esz = DTYPE_SIZE.get(d["dtype"], d["stride"])
    shape = d["shape"]
    prod_all = 1
    for x in shape:
        prod_all *= x
    if d["stride"] == esz:
        want = d["stride"] * prod_all
    else:
        if d["stride"] < esz * shape[-1]:
            raise ValueError("section %r: stride %d < dtype size %d * shape[-1] %d"
                             % (d["name"], d["stride"], esz, shape[-1]))
        prod_but_last = 1
        for x in shape[:-1]:
            prod_but_last *= x
        want = d["stride"] * prod_but_last
    if d["size"] != want:
        raise ValueError("section %r: size %d != %d required by the consistency rule"
                         % (d["name"], d["size"], want))
    if d["offset"] % 16:
        raise ValueError("section %r: offset %d is not 16-byte aligned"
                         % (d["name"], d["offset"]))


def selftest(verbose=False):
    """Checked against the vendored reader and against the spec's own worked
    example, not against this module's opinion of itself."""
    from .vendor.werk_read import mp_decode, read_envelope

    bad = []

    # ENVELOPE section 4.4's worked example, byte for byte, with the corrected
    # arithmetic that Stage 1 decision 18 recorded (ae / 35 / pad 1).
    sample = mp_encode({"endianness": "le", "kind": "core.pose.rest"})
    want = b"\x82\xaaendianness\xa2le\xa4kind\xaecore.pose.rest"
    if sample != want:
        bad.append("section 4.4 worked example: got %r" % (sample,))
    elif len(sample) != 35 or align16(12 + 35) != 48:
        bad.append("section 4.4 arithmetic: header_len %d" % len(sample))
    elif verbose:
        print("  OK MessagePack matches ENVELOPE 4.4 byte for byte (35 -> origin 48)")

    # shortest-form integers, sorted keys, no nil for an absent key
    enc = mp_encode({"z": 1, "a": 127, "m": 128, "big": 70000, "neg": -1,
                     "gone": None})
    if b"\xc0" in enc:
        bad.append("a None value must be omitted, not encoded as nil")
    dec = mp_decode(enc)
    if dec != {"z": 1, "a": 127, "m": 128, "big": 70000, "neg": -1}:
        bad.append("integer round trip: %r" % (dec,))
    elif list(dec.keys()) != sorted(dec.keys()):
        bad.append("keys are not byte-sorted: %r" % (list(dec.keys()),))
    elif verbose:
        print("  OK canonical integers, sorted keys, omitted nil")

    # a real envelope, checked by the reader that ships inside every package
    frames, bones = 3, 2
    root = b"".join(struct.pack("<7f", f, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)
                    for f in range(frames))
    rots = b"".join(struct.pack("<4f", 1.0, 0.0, 0.0, 0.0)
                    for _ in range(bones * frames))
    blob = build(b"WKAC", 1,
                 {"kind": "core.anim.clip", "clip_id": "test-clip",
                  "skeleton_id": "test-rig", "bone_count": bones,
                  "frame_count": frames, "rate_hz": 30.0,
                  "duration_s": frames / 30.0, "flags": 0,
                  "bones": ["bone-a", "bone-b"], "root_bone": "root"},
                 [("root-track", "f32", [frames, 7], 28, root),
                  ("bone-rotations", "f32", [bones, frames, 4], 16, rots)])
    try:
        magic, ver, hdr = read_envelope(blob)
        if magic != b"WKAC" or ver != 1:
            bad.append("envelope magic/version: %r %r" % (magic, ver))
        elif hdr["payload_origin"] != align16(12 + struct.unpack_from("<I", blob, 8)[0]):
            bad.append("payload_origin disagrees with the frame")
        elif verbose:
            print("  OK WKAC envelope (%d bytes) accepted by the vendored reader, "
                  "origin %d" % (len(blob), hdr["payload_origin"]))
    except Exception as e:  # noqa: BLE001 - the failure IS the result here
        bad.append("vendored reader rejected our envelope: %s" % e)

    # padding is zero, as a writer MUST (section 1)
    hl = struct.unpack_from("<I", blob, 8)[0]
    if any(b != 0 for b in bytearray(blob[12 + hl:align16(12 + hl)])):
        bad.append("header padding is not zero")
    elif verbose:
        print("  OK header padding is zero")

    # the consistency rule refuses a wrong stride rather than writing it
    try:
        build(b"WKAC", 1, {"kind": "core.anim.clip"},
              [("bad", "f32", [4, 4], 16, b"\x00" * 32)])
        bad.append("a section violating the consistency rule was written anyway")
    except ValueError:
        if verbose:
            print("  OK a section violating ENVELOPE section 3 is refused")

    # NaN is refused rather than written
    try:
        mp_encode({"x": float("nan")})
        bad.append("NaN was encoded into a core payload header")
    except ValueError:
        if verbose:
            print("  OK NaN is refused")

    return bad
