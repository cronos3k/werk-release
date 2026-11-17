# -*- coding: utf-8 -*-
"""werk -- read and write werk packages with the Python standard library alone.

One file on purpose: `werk_single.py` is this file plus the embedded bundle, so
a host that can vendor one .py (Blender, 3ds Max, Cinema 4D, GIMP, Unreal ...)
gets exactly the code the package uses. Python 3.7+ for everything; the READ
half (open / verify / read_payload / extract / primary_*) also runs on Python
2.7 (Cinema 4D R21 embeds 2.7.14), which is tested, not assumed.

    import werk
    pkg = werk.open("thing.werk")          # zip or directory form
    print(pkg.verdict())                   # signature state, census, error codes
    png = pkg.primary_image()[2]           # the bytes of THE image

    w = werk.PackageWriter("image/1", name="Sunset")
    ...                                    # see write_image_package()

Normative ground truth: the spec/ tree this library vendors (bundle/), in
particular spec/SPEC.md sections 1, 2, 2.1, 5, 6, 7 and 10, and
spec/MINI-SPECS.md sections 3, 5, 11 and 12.
"""

from __future__ import print_function

import binascii
import hashlib
import json
import os
import struct
import sys
import time
import uuid as _uuid
import zlib
from collections import OrderedDict

PY2 = sys.version_info[0] == 2
if PY2:  # pragma: no cover - exercised under 2.7 only
    text_type = unicode  # noqa: F821
    string_types = (str, unicode)  # noqa: F821
    integer_types = (int, long)  # noqa: F821
else:
    text_type = str
    string_types = (str,)
    integer_types = (int,)

LIB_VERSION = "0.1.0"
_bopen = open  # the builtin; `werk.open` below opens a PACKAGE
MANIFEST = "MANIFEST.json"
SIGNATURE = "SIGNATURE.json"

# Exit statuses, SPEC.md section 10.2.
EXIT_OK, EXIT_ERRORS, EXIT_REFUSED = 0, 1, 2

SIG_VALID, SIG_ABSENT, SIG_INVALID, SIG_UNVERIFIED = (
    "signed-and-valid", "absent", "present-and-invalid", "unverified")


class WerkError(Exception):
    """A request this library cannot carry out (bad writer input, missing node)."""


class ContainerRefusal(WerkError):
    """SPEC section 10.1's container scope: nothing can be loaded."""

    def __init__(self, code, message):
        WerkError.__init__(self, "%s: %s" % (code, message))
        self.code = code
        self.message = message


class EntryUnsupported(ValueError):
    pass


class EntryInvalid(ValueError):
    pass


# ---------------------------------------------------------------------------
# small byte helpers (2.7 and 3.x)
# ---------------------------------------------------------------------------

def _hex(b):
    h = binascii.hexlify(b)
    return h.decode("ascii") if not PY2 else h


def _unhex(s):
    return binascii.unhexlify(s.encode("ascii") if isinstance(s, text_type) else s)


def _int_le(b):
    return int(_hex(bytes(bytearray(reversed(bytearray(b))))), 16) if b else 0


def _le_bytes(n, length):
    h = "%0*x" % (length * 2, n)
    return bytes(bytearray(reversed(bytearray(_unhex(h)))))


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def _utf8(s):
    return s.encode("utf-8") if isinstance(s, text_type) else s


def _makedirs(d):
    if d and not os.path.isdir(d):
        os.makedirs(d)


def _utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# JSON: strict parse (MINI-SPECS section 3) and the libs' one emitter
# ---------------------------------------------------------------------------

def _pairs(pairs):
    out = OrderedDict()
    for k, v in pairs:
        if k in out:
            raise ValueError("duplicate object key %r" % (k,))
        out[k] = v
    return out


def _bad_constant(name):
    raise ValueError("%s is not a JSON number in werk" % name)


def _parse_float(s):
    v = float(s)
    if v in (float("inf"), float("-inf")) or v != v:
        raise ValueError("number %s does not fit binary64" % s)
    return v


def json_loads(data):
    """Strict: UTF-8, no BOM, no duplicate keys, finite numbers, order kept."""
    if isinstance(data, bytes) and not PY2:
        if data[:3] == b"\xef\xbb\xbf":
            raise ValueError("JSON starts with a byte-order mark")
        data = data.decode("utf-8")
    elif PY2 and isinstance(data, str):  # pragma: no cover
        if data[:3] == "\xef\xbb\xbf":
            raise ValueError("JSON starts with a byte-order mark")
        data = data.decode("utf-8")
    return json.loads(data, object_pairs_hook=_pairs, parse_constant=_bad_constant,
                      parse_float=_parse_float)


_ESC = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t",
        "\b": "\\b", "\f": "\\f"}


def _str(s):
    if PY2 and isinstance(s, str):  # pragma: no cover
        s = s.decode("utf-8")
    out = []
    for ch in s:
        e = _ESC.get(ch)
        if e is not None:
            out.append(e)
        elif ord(ch) < 0x20:
            out.append("\\u%04x" % ord(ch))
        elif 0xD800 <= ord(ch) <= 0xDFFF:
            raise WerkError("lone surrogate in a string; werk JSON is UTF-8")
        else:
            out.append(ch)
    return u'"' + u"".join(out) + u'"'


def _num(v):
    if isinstance(v, bool):
        raise TypeError("bool")
    if isinstance(v, integer_types):
        return u"%d" % v
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")):
            raise WerkError("werk JSON numbers are finite")
        # repr is the shortest round-trip form; this spelling (Python's) is THE
        # spelling of a non-integer in every libs/ writer (README, "JSON").
        return text_type(repr(v))
    raise TypeError("not a number: %r" % (v,))


def _emit(v, indent, level, out):
    if v is None:
        out.append(u"null")
    elif v is True:
        out.append(u"true")
    elif v is False:
        out.append(u"false")
    elif isinstance(v, string_types):
        out.append(_str(v))
    elif isinstance(v, (integer_types, float)):
        out.append(_num(v))
    elif isinstance(v, dict):
        if not v:
            out.append(u"{}")
            return
        pad = u"\n" + u" " * (indent * (level + 1)) if indent else u""
        out.append(u"{")
        first = True
        for k, x in v.items():
            if not first:
                out.append(u",")
            first = False
            out.append(pad)
            out.append(_str(k))
            out.append(u": " if indent else u":")
            _emit(x, indent, level + 1, out)
        out.append((u"\n" + u" " * (indent * level)) if indent else u"")
        out.append(u"}")
    elif isinstance(v, (list, tuple)):
        if not v:
            out.append(u"[]")
            return
        pad = u"\n" + u" " * (indent * (level + 1)) if indent else u""
        out.append(u"[")
        for i, x in enumerate(v):
            if i:
                out.append(u",")
            out.append(pad)
            _emit(x, indent, level + 1, out)
        out.append((u"\n" + u" " * (indent * level)) if indent else u"")
        out.append(u"]")
    else:
        raise TypeError("cannot write %r as JSON" % (v,))


def json_pretty(value):
    """The bytes every libs/ writer emits for a JSON file: two-space indent,
    `": "` after keys, non-ASCII as itself, LF, one trailing newline, keys in
    insertion order -- byte for byte what `json.dumps(v, indent=2,
    ensure_ascii=False) + "\\n"` gives on Python 3."""
    out = []
    _emit(value, 2, 0, out)
    return (u"".join(out) + u"\n").encode("utf-8")


def _sorted_obj(v):
    if isinstance(v, dict):
        keys = sorted(v.keys(), key=lambda k: _utf8(k))
        return OrderedDict((k, _sorted_obj(v[k])) for k in keys)
    if isinstance(v, (list, tuple)):
        return [_sorted_obj(x) for x in v]
    return v


def json_canonical(value):
    """MINI-SPECS section 3, canonical JSON: keys sorted by UTF-8 bytes, no
    whitespace, minimal escapes, non-ASCII as UTF-8."""
    out = []
    _emit(_sorted_obj(value), 0, 0, out)
    return u"".join(out).encode("utf-8")


# ---------------------------------------------------------------------------
# Ed25519 -- RFC 8032 reference algorithm (pure Python, not constant-time:
# verification has no secret; signing is for authors on their own machine)
# ---------------------------------------------------------------------------

_P = 2 ** 255 - 19
_Q = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)


def _inv(x):
    return pow(x, _P - 2, _P)


def _padd(p1, p2):
    a = (p1[1] - p1[0]) * (p2[1] - p2[0]) % _P
    b = (p1[1] + p1[0]) * (p2[1] + p2[0]) % _P
    c = 2 * p1[3] * p2[3] * _D % _P
    d = 2 * p1[2] * p2[2] % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _pmul(s, pt):
    out = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            out = _padd(out, pt)
        pt = _padd(pt, pt)
        s >>= 1
    return out


def _peq(p1, p2):
    return ((p1[0] * p2[2] - p2[0] * p1[2]) % _P == 0
            and (p1[1] * p2[2] - p2[1] * p1[2]) % _P == 0)


def _recover_x(y, sign):
    if y >= _P:
        return None
    x2 = (y * y - 1) * _inv(_D * y * y + 1) % _P
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


_GY = 4 * _inv(5) % _P
_GX = _recover_x(_GY, 0)
_G = (_GX, _GY, 1, _GX * _GY % _P)


def _compress(pt):
    zi = _inv(pt[2])
    x, y = pt[0] * zi % _P, pt[1] * zi % _P
    return _le_bytes(y | ((x & 1) << 255), 32)


def _decompress(b):
    if len(b) != 32:
        return None
    y = _int_le(b)
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def _h512q(data):
    return _int_le(hashlib.sha512(data).digest()) % _Q


def _expand(secret):
    if len(secret) != 32:
        raise WerkError("an Ed25519 secret key is 32 bytes (64 hex digits)")
    h = hashlib.sha512(secret).digest()
    a = _int_le(h[:32])
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def ed25519_public_key(secret):
    a, _ = _expand(secret)
    return _compress(_pmul(a, _G))


def ed25519_sign(secret, message):
    a, prefix = _expand(secret)
    pub = _compress(_pmul(a, _G))
    r = _h512q(prefix + message)
    big_r = _compress(_pmul(r, _G))
    s = (r + _h512q(big_r + pub + message) * a) % _Q
    return big_r + _le_bytes(s, 32)


def ed25519_verify(pub, message, sig):
    if len(pub) != 32 or len(sig) != 64:
        return False
    pa = _decompress(pub)
    if pa is None:
        return False
    rs = sig[:32]
    pr = _decompress(rs)
    if pr is None:
        return False
    s = _int_le(sig[32:])
    if s >= _Q:
        return False
    h = _h512q(rs + pub + message)
    return _peq(_pmul(s, _G), _padd(pr, _pmul(h, pa)))


# ---------------------------------------------------------------------------
# Containers (MINI-SPECS section 5): directory, or zip (store + deflate read)
# ---------------------------------------------------------------------------

ZIP64_REMEDY = ("werk does not use zip64: a package past the zip32 ceiling (4 GiB, "
                "65534 entries) is carried in DIRECTORY form, which is the same format")


def _unsafe(path):
    """MINI-SPECS 5.4: relative, forward slashes, no `..` segment, no drive
    letter, no leading slash (and no NUL)."""
    return (not path or path.startswith("/") or "\\" in path or "\x00" in path
            or ".." in path.split("/") or (len(path) > 1 and path[1] == ":"))


def _unsafe_msg(tag, path):
    return ("%s: files[] path %r is not a package path (MINI-SPECS 5.4: relative, forward "
            "slashes, no `..` segment, no drive letter); this version is unusable" % (tag, path))


def _reject_unsafe(path):
    if _unsafe(path):
        raise ValueError("refusing an unsafe package path: %r" % (path,))


class DirContainer(object):
    form = "directory"

    def __init__(self, root):
        self.root = root

    def names(self):
        out = []
        for dp, _dn, fn in os.walk(self.root):
            for f in fn:
                rel = os.path.relpath(os.path.join(dp, f), self.root).replace(os.sep, "/")
                if PY2 and isinstance(rel, str):  # pragma: no cover
                    rel = rel.decode(sys.getfilesystemencoding() or "utf-8")
                out.append(rel)
        return sorted(out, key=_utf8)

    def _full(self, path):
        _reject_unsafe(path)
        return os.path.join(self.root, *path.split("/"))

    def read(self, path):
        full = self._full(path)
        if not os.path.isfile(full):
            raise KeyError(path)
        with _bopen(full, "rb") as fh:
            return fh.read()

    def size(self, path):
        full = self._full(path)
        if not os.path.isfile(full):
            raise KeyError(path)
        return os.path.getsize(full)

    def sha256(self, path):
        full = self._full(path)
        if not os.path.isfile(full):
            raise KeyError(path)
        h = hashlib.sha256()
        n = 0
        with _bopen(full, "rb") as fh:
            while True:
                b = fh.read(1 << 20)
                if not b:
                    break
                n += len(b)
                h.update(b)
        return h.hexdigest(), n


class ZipContainer(object):
    form = "zip"

    def __init__(self, data):
        self.data = data
        self.entries = {}
        self.order = []
        self._parse()

    def _parse(self):
        d = self.data
        n = len(d)
        if n < 22:
            raise ContainerRefusal("bad-container", "file is too short to be a zip")
        eocd = -1
        for i in range(n - 22, max(0, n - 22 - 65535) - 1, -1):
            if d[i:i + 4] == b"PK\x05\x06":
                if i + 22 + struct.unpack_from("<H", d, i + 20)[0] == n:
                    eocd = i
                    break
        if eocd < 0:
            raise ContainerRefusal("bad-container", "no end-of-central-directory record: not a zip")
        disks, count, cd_size, cd_off = struct.unpack_from("<HHII", d, eocd + 8)
        sentinel = 0xFFFFFFFF in (cd_size, cd_off) or 0xFFFF in (count, disks)
        locator = eocd >= 20 and d[eocd - 20:eocd - 16] == b"PK\x06\x07"
        if sentinel or locator:
            raise ContainerRefusal("zip64-unsupported", "zip64 container. " + ZIP64_REMEDY)
        p = cd_off
        for _ in range(count):
            if d[p:p + 4] != b"PK\x01\x02":
                raise ContainerRefusal("bad-container", "bad central directory signature at %d" % p)
            flags, method = struct.unpack_from("<HH", d, p + 8)
            crc, comp, uncomp = struct.unpack_from("<III", d, p + 16)
            nlen, mlen, klen = struct.unpack_from("<HHH", d, p + 28)
            lho = struct.unpack_from("<I", d, p + 42)[0]
            if p + 46 + nlen > n:
                raise ContainerRefusal("bad-container", "a central directory name runs past the end of the file")
            # MINI-SPECS 5.4 rule 3: lossy UTF-8, so a damaged name is a name
            # no manifest path matches (file-missing), never a malformed directory.
            name = d[p + 46:p + 46 + nlen].decode("utf-8", "replace")
            if 0xFFFFFFFF in (comp, uncomp, lho):
                raise ContainerRefusal("zip64-unsupported",
                                       "entry %r carries a zip64 sentinel. %s" % (name, ZIP64_REMEDY))
            if flags & 0x0008:
                raise ContainerRefusal("bad-container",
                                       "entry %r sets flag bit 3 (data descriptor)" % name)
            if name in self.entries:
                # Two records, one name: which bytes ARE that file cannot be
                # decided, and readers that pick different ones disagree about
                # one package. Refused whole (container scope, exit 2).
                raise ContainerRefusal("bad-container",
                                       "the zip holds two entries named %r; which bytes are that "
                                       "file cannot be decided, so the container is refused" % name)
            self.entries[name] = (method, comp, uncomp, lho, flags, crc)
            self.order.append(name)
            p += 46 + nlen + mlen + klen

    def names(self):
        return [n for n in self.order if not n.endswith("/")]

    def read(self, path):
        if path not in self.entries:
            raise KeyError(path)
        method, comp, uncomp, lho, flags, crc = self.entries[path]
        if flags & 0x0001:
            raise EntryUnsupported("entry %r is encrypted" % path)
        if method not in (0, 8):
            raise EntryUnsupported("entry %r uses compression method %d" % (path, method))
        d = self.data
        if d[lho:lho + 4] != b"PK\x03\x04":
            raise EntryInvalid("bad local header signature for %r" % path)
        nlen, mlen = struct.unpack_from("<HH", d, lho + 26)
        start = lho + 30 + nlen + mlen
        raw = d[start:start + comp]
        if len(raw) != comp:
            raise EntryInvalid("entry %r runs past the end of the file" % path)
        if method == 0:
            return raw
        try:
            z = zlib.decompressobj(-15)
            out = z.decompress(raw, uncomp + 1)
        except zlib.error as e:
            raise EntryInvalid("entry %r: deflate stream does not decode: %s" % (path, e))
        if len(out) != uncomp or not getattr(z, "eof", True):
            raise EntryInvalid("entry %r does not inflate to the %d bytes declared" % (path, uncomp))
        if (zlib.crc32(out) & 0xFFFFFFFF) != crc:
            raise EntryInvalid("entry %r inflates to bytes whose CRC-32 disagrees" % path)
        return out

    def size(self, path):
        return len(self.read(path))

    def sha256(self, path):
        b = self.read(path)
        return sha256_hex(b), len(b)


def _eocd_offset(d):
    """MINI-SPECS 5.4 rule 1: the EOCD is the record at the HIGHEST offset of
    the 5.1 window whose signature matches and whose comment length accounts
    for exactly the rest of the bytes; -1 when there is none."""
    n = len(d)
    for i in range(n - 22, max(0, n - 22 - 65535) - 1, -1):
        if d[i:i + 4] == b"PK\x05\x06" and i + 22 + struct.unpack_from("<H", d, i + 20)[0] == n:
            return i
    return -1


def open_container(path):
    if os.path.isdir(path):
        return DirContainer(path)
    if not os.path.isfile(path):
        raise ContainerRefusal("bad-container", "%s is neither a file nor a directory" % path)
    with _bopen(path, "rb") as fh:
        fh.seek(0, 2)
        size = fh.tell()
        fh.seek(max(0, size - (22 + 65535 + 20)))
        tail = fh.read()
        e = _eocd_offset(tail)
        if e >= 0:
            c = struct.unpack_from("<HHII", tail, e + 8)
            if 0xFFFF in c[:2] or 0xFFFFFFFF in c[2:] or (
                    e >= 20 and tail[e - 20:e - 16] == b"PK\x06\x07"):
                raise ContainerRefusal("zip64-unsupported", "zip64 container. " + ZIP64_REMEDY)
        fh.seek(0)
        data = fh.read()
    try:
        return ZipContainer(data)
    except (struct.error, IndexError) as e:
        raise ContainerRefusal("bad-container", "the zip directory is malformed: %s" % e)


def _dos_datetime(created):
    """RFC 3339 `YYYY-MM-DDTHH:MM:SSZ` -> (dos_time, dos_date). The zip
    timestamp of every entry is the package's `created`, so the bytes are a
    function of the input alone."""
    try:
        y, mo, d = int(created[0:4]), int(created[5:7]), int(created[8:10])
        h, mi, s = int(created[11:13]), int(created[14:16]), int(created[17:19])
    except (ValueError, TypeError):
        raise WerkError("created must be RFC 3339 UTC, e.g. 2026-11-07T12:00:00Z")
    if y < 1980:
        y, mo, d, h, mi, s = 1980, 1, 1, 0, 0, 0
    return (h << 11) | (mi << 5) | (s // 2), ((y - 1980) << 9) | (mo << 5) | d


class ZipWriter(object):
    """Store-mode zip, exactly as MINI-SPECS section 5 and every libs/ writer
    lay it out: version 20, flag 0x0800 (UTF-8 names), method 0, no extra
    field, no data descriptor, no comment, no directory entries, no zip64."""

    def __init__(self, fh, created):
        self.fh = fh
        self.t, self.d = _dos_datetime(created)
        self.central = []
        self.pos = 0

    def add(self, name, data, crc=None):
        nb = _utf8(name)
        if crc is None:
            crc = zlib.crc32(data) & 0xFFFFFFFF
        n = len(data)
        if n >= 0xFFFFFFFF or self.pos + 30 + len(nb) + n >= 0xFFFFFFFF:
            raise WerkError("the zip form ends below 4 GiB; write this package in directory form")
        hdr = struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0x0800, 0, self.t, self.d,
                          crc, n, n, len(nb), 0)
        self.central.append(struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 0x0800, 0,
                                        self.t, self.d, crc, n, n, len(nb), 0, 0, 0, 0, 0,
                                        self.pos) + nb)
        self.fh.write(hdr + nb)
        self.fh.write(data)
        self.pos += len(hdr) + len(nb) + n

    def close(self):
        if len(self.central) > 65534:
            raise WerkError("more than 65534 entries; write this package in directory form")
        cd = b"".join(self.central)
        self.fh.write(cd)
        self.fh.write(struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(self.central),
                                  len(self.central), len(cd), self.pos, 0))


def physical_order(paths, entry_order):
    """container.entry_order applied (SPEC section 1, the two-pass rule), then
    MANIFEST.json moved first: every exact path in list order, then each
    directory prefix in list order, each group sorted by UTF-8 bytes, then
    whatever is left, sorted."""
    left = sorted(paths, key=_utf8)
    placed = {}
    for i, pat in enumerate(entry_order):
        if not pat.endswith("/") and pat in left and pat not in placed:
            placed[pat] = i
    for i, pat in enumerate(entry_order):
        if pat.endswith("/"):
            for p in left:
                if p not in placed and p.startswith(pat):
                    placed[p] = i
    listed = sorted((p for p in left if p in placed), key=lambda p: (placed[p], _utf8(p)))
    order = listed + [p for p in left if p not in placed]
    if MANIFEST in order:
        order.remove(MANIFEST)
        order.insert(0, MANIFEST)
    return order


# ---------------------------------------------------------------------------
# The binary envelope frame (spec/layouts/ENVELOPE.layout.txt section 7)
# ---------------------------------------------------------------------------

MAGIC_KIND = {b"WKFF": "core.field.flow", b"WKRP": "core.pose.rest",
              b"WKAC": "core.anim.clip", b"WKSK": "core.skeleton",
              b"WKEM": "core.embedding", b"WKPC": "core.geom.points",
              b"WKGS": "core.geom.gsplat"}
_MAGIC_TAIL = bytearray(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
_BANNED = (0xC1, 0xC7, 0xC8, 0xC9, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8)


def is_envelope_magic(m):
    m = bytearray(m)
    return len(m) == 4 and m[0] == 0x57 and m[1] == 0x4B and m[2] in _MAGIC_TAIL and m[3] in _MAGIC_TAIL


def _mp(b, o):
    c = b[o]
    o += 1
    if c in _BANNED:
        raise ValueError("format byte 0x%02x is banned in werk headers" % c)
    if c <= 0x7F:
        return c, o
    if c >= 0xE0:
        return c - 256, o
    if 0xA0 <= c <= 0xBF:
        n = c & 0x1F
        return bytes(b[o:o + n]).decode("utf-8"), o + n
    if 0x90 <= c <= 0x9F:
        return _mpseq(b, o, c & 0x0F, False)
    if 0x80 <= c <= 0x8F:
        return _mpseq(b, o, c & 0x0F, True)
    if c == 0xC0:
        return None, o
    if c == 0xC2:
        return False, o
    if c == 0xC3:
        return True, o
    fixed = {0xCC: (">B", 1), 0xCD: (">H", 2), 0xCE: (">I", 4), 0xCF: (">Q", 8),
             0xD0: (">b", 1), 0xD1: (">h", 2), 0xD2: (">i", 4), 0xD3: (">q", 8),
             0xCA: (">f", 4), 0xCB: (">d", 8)}
    if c in fixed:
        fmt, n = fixed[c]
        return struct.unpack_from(fmt, bytes(b[o:o + n]))[0], o + n
    pfx = {0xD9: (">B", 1, "s"), 0xDA: (">H", 2, "s"), 0xDB: (">I", 4, "s"),
           0xC4: (">B", 1, "b"), 0xC5: (">H", 2, "b"), 0xC6: (">I", 4, "b"),
           0xDC: (">H", 2, "a"), 0xDD: (">I", 4, "a"), 0xDE: (">H", 2, "m"), 0xDF: (">I", 4, "m")}
    if c in pfx:
        fmt, n, kind = pfx[c]
        ln = struct.unpack_from(fmt, bytes(b[o:o + n]))[0]
        o += n
        if kind == "s":
            return bytes(b[o:o + ln]).decode("utf-8"), o + ln
        if kind == "b":
            return bytes(b[o:o + ln]), o + ln
        return _mpseq(b, o, ln, kind == "m")
    raise ValueError("unknown MessagePack format byte 0x%02x" % c)


def _mpseq(b, o, n, is_map):
    if not is_map:
        out = []
        for _ in range(n):
            v, o = _mp(b, o)
            out.append(v)
        return out, o
    out = OrderedDict()
    for _ in range(n):
        k, o = _mp(b, o)
        v, o = _mp(b, o)
        if not isinstance(k, string_types):
            raise ValueError("werk header map keys must be strings")
        out[k] = v
    return out, o


def _a16(n):
    return (n + 15) // 16 * 16


def read_envelope(data):
    """Validate an envelope's frame; return (magic, version, header)."""
    if len(data) < 16:
        raise ValueError("file is %d bytes; the smallest legal envelope is 16" % len(data))
    magic = bytes(data[0:4])
    if not is_envelope_magic(magic):
        raise ValueError("not an envelope magic")
    version, hlen = struct.unpack_from("<II", data, 4)
    if 12 + hlen > len(data):
        raise ValueError("header_len %d runs past the end of the file" % hlen)
    b = bytearray(data[12:12 + hlen])
    header, end = _mp(b, 0)
    if end != len(b):
        raise ValueError("trailing bytes after the MessagePack header")
    if not isinstance(header, dict):
        raise ValueError("the header is not a map")
    if header.get("endianness") != "le":
        raise ValueError("header endianness is not 'le'")
    want = MAGIC_KIND.get(magic)
    if want and header.get("kind") != want:
        raise ValueError("magic %r implies kind %r but the header says %r"
                         % (magic, want, header.get("kind")))
    origin = _a16(12 + hlen)
    if header.get("payload_origin") != origin:
        raise ValueError("payload_origin %r != computed %d" % (header.get("payload_origin"), origin))
    psize = header.get("payload_size")
    if not isinstance(psize, integer_types) or origin + psize != len(data):
        raise ValueError("payload_origin + payload_size != file size")
    prev = origin
    secs = header.get("sections") or []
    for s in secs:
        off, size = s["offset"], s["size"]
        if off % 16 or off < prev or off - prev > 15 or off + size > len(data):
            raise ValueError("section %r is misplaced" % s.get("name"))
        prev = off + size
    if secs and _a16(secs[-1]["offset"] + secs[-1]["size"]) != origin + psize:
        raise ValueError("the last section does not end where payload_size says")
    return magic, version, header


# ---------------------------------------------------------------------------
# The bundle: the vendored spec/ + loaders/ and the writer tables
# ---------------------------------------------------------------------------

_EMBEDDED_BUNDLE = None   # werk_single.py sets this to {path: bytes}


class Bundle(object):
    """bundle.json + the files it lists. Every writer reads its texts, its
    tables and its node records for spec/ and loaders/ from here."""

    def __init__(self, reader):
        self._read = reader
        self.info = json_loads(reader("bundle.json"))
        self.files = OrderedDict((f["path"], f) for f in self.info["files"])

    def data(self, path):
        b = self._read(path)
        rec = self.files[path]
        if len(b) != rec["size"] or sha256_hex(b) != rec["sha256"]:
            raise WerkError("the vendored bundle file %s is not the bytes bundle.json "
                            "declares; refusing to copy a damaged specification" % path)
        return b

    @classmethod
    def default(cls):
        if _EMBEDDED_BUNDLE is not None:
            return cls(lambda p: _EMBEDDED_BUNDLE[p])
        root = os.environ.get("WERK_BUNDLE") or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "bundle")

        def rd(p):
            with _bopen(os.path.join(root, *p.split("/")), "rb") as fh:
                return fh.read()
        return cls(rd)


_BUNDLE = []


def default_bundle():
    if not _BUNDLE:
        _BUNDLE.append(Bundle.default())
    return _BUNDLE[0]


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

# Built-in profile convention tables: the same values bundle.json carries.
SUPPORTED_CONVENTIONS = {
    "3d-entity/1": OrderedDict([
        ("endianness", "le"), ("units_per_meter", 1.0), ("length_unit", "metre"),
        ("angle_unit", "radian"), ("time_unit", "second"), ("mass_unit", "kilogram"),
        ("up_axis", "y"), ("forward_axis", "-z"), ("right_axis", "+x"),
        ("handedness", "right"), ("winding", "ccw"), ("quat_order", "wxyz"),
        ("oct_encoding_pole", "y"), ("sh_l1_order", ["dc", "y", "z", "x"]),
        ("color_space_default", "srgb"), ("uv_origin", "top-left"),
        ("alignment_bytes", 16), ("text_encoding", "utf-8"), ("id_case", "kebab-case"),
        ("hash_algorithm", "sha256"), ("signature_algorithm", "ed25519")]),
    "image/1": OrderedDict([
        ("endianness", "le"), ("color_space_default", "srgb"), ("pixel_origin", "top-left"),
        ("alpha_mode", "straight"), ("alignment_bytes", 16), ("text_encoding", "utf-8"),
        ("id_case", "kebab-case"), ("hash_algorithm", "sha256"),
        ("signature_algorithm", "ed25519")]),
}
BASE_CONVENTIONS = OrderedDict([
    ("endianness", "le"), ("alignment_bytes", 16), ("text_encoding", "utf-8"),
    ("id_case", "kebab-case"), ("hash_algorithm", "sha256"), ("signature_algorithm", "ed25519")])

# SPEC section 2.1 rule 4: node type -> its documented payload role.
PAYLOAD_ROLE = {"core.audio.effect": "best", "core.audio.ambience": "best",
                "core.imposter": "atlas", "core.recipe": "record"}

MESH_TYPES = ("core.geom.game", "core.geom.source", "core.geom.lod")


class Entry(object):
    __slots__ = ("severity", "code", "node", "message")

    def __init__(self, severity, code, node, message):
        self.severity, self.code, self.node, self.message = severity, code, node, message

    def __repr__(self):
        return "[%s] %s: %s" % (self.severity, self.code, self.message)


class Node(object):
    """One node of the graph, after the load: `status` is alive / dead /
    skipped, `resolved` the version number actually used."""

    def __init__(self, raw, index):
        self.raw = raw
        self.index = index
        nid = raw.get("node_id")
        self.node_id = nid if isinstance(nid, string_types) else "<node %d>" % index
        t = raw.get("type")
        self.type = t if isinstance(t, string_types) else "<untyped>"
        self.active = raw.get("active")
        self.versions = raw.get("versions") if isinstance(raw.get("versions"), list) else []
        self.edges = raw.get("edges") if isinstance(raw.get("edges"), list) else []
        self.meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
        self.resolved = None
        self.status = "alive"
        self.reason = ""

    def version(self, v=None):
        v = self.resolved if v is None else v
        for x in self.versions:
            if x.get("v") == v:
                return x
        return None

    @property
    def files(self):
        ver = self.version()
        return list(ver.get("files", [])) if ver else []

    def __repr__(self):
        return "<Node %s %s %s>" % (self.node_id, self.type, self.status)


def node_shape_error(n):
    """SPEC 12.1: what a node needs to be walked at all (node_id and type
    strings, an integer `active`, a non-empty versions[] of objects with an
    integer `v` and a files[] of objects) -- the reference core's and the
    bootstrap loaders' rule. A node that fails is dead; the package is not."""
    def is_int(x):
        return isinstance(x, integer_types) and not isinstance(x, bool)
    if not isinstance(n, dict):
        return "is not a JSON object"
    if not isinstance(n.get("node_id"), string_types):
        return "no node_id"
    if not isinstance(n.get("type"), string_types):
        return "no type"
    if not is_int(n.get("active")):
        return "no active"
    vs = n.get("versions")
    if not isinstance(vs, list) or not vs:
        return "no versions array"
    for v in vs:
        if not isinstance(v, dict) or not is_int(v.get("v")):
            return "a version has no v"
        fs = v.get("files")
        if not isinstance(fs, list):
            return "a version has no files[]"
        for f in fs:
            if not isinstance(f, dict):
                return "a files[] entry is not an object"
            # SPEC 12.1: a file record says WHAT the bytes are -- path,
            # sha256, size -- or it cannot be verified and the node is dead.
            if not isinstance(f.get("path"), string_types):
                return "a files[] entry has no path"
            if not isinstance(f.get("sha256"), string_types):
                return "a files[] entry has no sha256"
            if not is_int(f.get("size")) or f["size"] < 0:
                return "a files[] entry has no integer size"
    return None


def payload_path(node, version=None):
    """SPEC section 2.1, the ordered rules. Returns the path, or raises
    WerkError(`payload-file-ambiguous`) -- never files[0] by default."""
    ver = node.version(version) if isinstance(node, Node) else version
    if ver is None:
        raise WerkError("node %s has no usable version" % getattr(node, "node_id", "?"))
    files = ver.get("files", [])
    paths = [f.get("path") for f in files]
    pf = ver.get("payload_file")
    if isinstance(pf, string_types):
        if paths.count(pf) == 1:
            return pf
        raise WerkError("payload-file-ambiguous: payload_file %r is not exactly one of "
                        "files[]" % pf)
    if len(files) == 1:
        return paths[0]
    roled = [f.get("path") for f in files if f.get("role") == "payload"]
    if len(roled) == 1:
        return roled[0]
    ntype = node.type if isinstance(node, Node) else ""
    role = PAYLOAD_ROLE.get(ntype)
    if role:
        roled = [f.get("path") for f in files if f.get("role") == role]
        if len(roled) == 1:
            return roled[0]
    if ntype == "core.anim.clip":
        env = [f.get("path") for f in files if str(f.get("path", "")).endswith(".wkac")]
        if len(env) == 1:
            return env[0]
    raise WerkError("payload-file-ambiguous: node %s has %d candidate files (%s); none is "
                    "declared the payload" % (getattr(node, "node_id", "?"), len(paths),
                                              ", ".join(str(p) for p in paths)))


class Package(object):
    """A werk package, opened and verified (SPEC section 10).

    Reader class, stated honestly: every [B] step of the checklist, plus the
    full-reader steps this library can do without a JSON Schema validator --
    Ed25519 chain verification (all four states), spec_sha256 recomputation,
    input_hash staleness, payload_file resolution. It does NOT validate the
    manifest or payloads against JSON Schemas; `verdict()["schema_validated"]`
    is False to say so."""

    def __init__(self, path, container=None):
        self.path = path
        self.container = container or open_container(path)
        self.form = self.container.form
        self.report = []
        self._hash_cache = {}
        try:
            raw = self.container.read(MANIFEST)
        except KeyError:
            raise ContainerRefusal("manifest-absent", "%s is not in %s" % (MANIFEST, path))
        except ValueError as e:
            raise ContainerRefusal("manifest-unparseable", "%s cannot be read: %s" % (MANIFEST, e))
        self.manifest_bytes = raw
        try:
            self.manifest = json_loads(raw)
        except Exception as e:  # noqa: BLE001
            raise ContainerRefusal("manifest-unparseable", "%s is not valid JSON: %s" % (MANIFEST, e))
        if not isinstance(self.manifest, dict):
            raise ContainerRefusal("manifest-structurally-invalid", "MANIFEST.json is not an object")
        if not isinstance(self.manifest.get("nodes"), list):
            raise ContainerRefusal("manifest-structurally-invalid", "nodes is not an array")
        self.manifest_sha256 = sha256_hex(raw)
        self.profile = self.manifest.get("profile", "")
        self.envelopes_validated = 0
        self.signature_state = SIG_ABSENT
        self.signers = []
        werkv = self.manifest.get("werk")
        major = werkv.get("major") if isinstance(werkv, dict) else None
        if major != 1 or isinstance(major, bool):
            # Not a container trigger (SPEC 12.1 lists only the graph); the
            # base shape pins werk.major to 1, so this is that check failing.
            self._add("error", "schema-invalid", None,
                      "werk.major is %r; this reader implements major version 1" % (major,))
        self._conventions()
        self._signature()
        self.nodes = [Node(n if isinstance(n, dict) else {}, i)
                      for i, n in enumerate(self.manifest["nodes"])]
        self._by_id = OrderedDict((n.node_id, n) for n in self.nodes)
        self._walk()
        self._edges()
        self._floating()
        self._spec_sha256()
        self._input_hashes()

    # -- report ----------------------------------------------------------
    def _add(self, severity, code, node, message):
        self.report.append(Entry(severity, code, node, message))

    def errors(self):
        return [e for e in self.report if e.severity == "error"]

    # -- step 3 ----------------------------------------------------------
    def _conventions(self):
        conv = self.manifest.get("conventions")
        if not isinstance(conv, dict):
            self._add("error", "unsupported-convention", None, "no conventions block")
            return
        table = SUPPORTED_CONVENTIONS.get(self.profile)
        if table is None:
            own = sorted(k for k in conv if k not in BASE_CONVENTIONS)
            self._add("warn", "unsupported-profile", None,
                      "profile %r is not built into this reader; the six base conventions "
                      "were checked, the profile's own (%s) were not interpreted, and the "
                      "manifest was NOT validated against the schema it names (%s). Every "
                      "file is still listed, hash-verified and extractable"
                      % (self.profile, ", ".join(own), self.manifest.get("manifest_schema")))
            table = BASE_CONVENTIONS
        for k, want in table.items():
            if k not in conv:
                self._add("error", "unsupported-convention", None, "`%s` is missing" % k)
            elif conv[k] != want or isinstance(conv[k], bool) != isinstance(want, bool):
                self._add("error", "unsupported-convention", None,
                          "`%s` is %r; this reader implements only %r" % (k, conv[k], want))

    # -- step 4 ----------------------------------------------------------
    def _signature(self):
        try:
            raw = self.container.read(SIGNATURE)
        except ValueError as e:
            # SPEC section 6: present but its entry cannot be read is
            # present-and-invalid, never absent.
            self.signature_state = SIG_INVALID
            self._add("error", "signature-invalid", None,
                      "SIGNATURE.json is present but cannot be read: %s" % e)
            return
        except KeyError:
            self.signature_state = SIG_ABSENT
            self._add("info", "signature-absent", None,
                      "no SIGNATURE.json: anonymous, which is legitimate and visible")
            return
        problems, signers = verify_chain(raw, self.manifest_sha256)
        if problems is None:
            self.signature_state = SIG_UNVERIFIED
            self._add("warn", "signature-unverified", None, "signature algorithm not supported")
        elif problems:
            self.signature_state = SIG_INVALID
            self._add("error", "signature-invalid", None, "; ".join(problems))
        else:
            self.signature_state = SIG_VALID
            self.signers = signers
            self._add("info", "signature-valid", None,
                      "%d link(s) verify: %s" % (len(signers), ", ".join(signers)))

    # -- steps 5, 6, 8 ---------------------------------------------------
    def _file_hash(self, path):
        if path not in self._hash_cache:
            self._hash_cache[path] = self.container.sha256(path)
        return self._hash_cache[path]

    def _verify_version(self, node, ver):
        problems = []
        files = ver.get("files") if isinstance(ver.get("files"), list) else []
        for f in files:
            path = f.get("path") if isinstance(f, dict) else None
            tag = "%s v%s" % (node.node_id, ver.get("v"))
            if not isinstance(path, string_types):
                problems.append(("error", "file-missing", "%s: a file record has no path" % tag))
                continue
            if _unsafe(path):
                problems.append(("error", "schema-invalid", _unsafe_msg(tag, path)))
                continue
            try:
                got, size = self._file_hash(path)
            except KeyError:
                problems.append(("error", "file-missing", "%s: %s is not in the container" % (tag, path)))
                continue
            except EntryInvalid as e:
                problems.append(("error", "zip-entry-invalid", "%s: %s" % (tag, e)))
                continue
            except ValueError as e:
                problems.append(("error", "zip-entry-unsupported", "%s: %s" % (tag, e)))
                continue
            # A record without a usable `size` declares 0 bytes -- werk-core's
            # and the C/Rust loaders' reading -- so it fails unless the file is empty.
            dsize = f.get("size")
            if not isinstance(dsize, integer_types) or isinstance(dsize, bool) or dsize < 0:
                dsize = 0
            if size != dsize:
                problems.append(("error", "size-mismatch", "%s: %s declares %s bytes, holds %d"
                                 % (tag, path, f.get("size"), size)))
            if got != f.get("sha256"):
                problems.append(("error", "hash-mismatch", "%s: %s declares sha256 %s, bytes hash to %s"
                                 % (tag, path, f.get("sha256"), got)))
        return problems

    def _walk(self):
        for node in self.nodes:
            bad = node_shape_error(self.manifest["nodes"][node.index])
            if bad is not None:
                node.status, node.reason, node.type = "dead", "malformed node: %s" % bad, "<malformed>"
                node.versions, node.edges = [], []
                self._add("error", "node-dead", node.node_id,
                          "%s: nodes[%d]: %s; the node is dead, the package is not"
                          % (node.node_id, node.index, bad))
                continue
            if not node.versions:
                node.status, node.reason = "dead", "no versions[]"
                self._add("error", "node-dead", node.node_id, "%s has no versions[]" % node.node_id)
                continue
            active = node.active
            if not any(v.get("v") == active for v in node.versions if isinstance(v, dict)):
                self._add("warn", "version-fallback", node.node_id,
                          "%s: active names v%s, which does not exist" % (node.node_id, active))
            cands = sorted((v for v in node.versions if isinstance(v, dict)
                            and isinstance(v.get("v"), integer_types)
                            and not isinstance(v.get("v"), bool)
                            and (not isinstance(active, integer_types) or v["v"] <= active)),
                           key=lambda v: -v["v"])
            tried = set()
            for cand in cands:
                tried.add(id(cand))
                if "compacted" in cand:
                    self._add("info", "version-compacted", node.node_id,
                              "%s v%d was compacted" % (node.node_id, cand["v"]))
                    continue
                problems = self._verify_version(node, cand)
                if not problems:
                    node.resolved = cand["v"]
                    if cand["v"] != active:
                        self._add("warn", "version-fallback", node.node_id,
                                  "%s: active v%s is unusable, fell back to v%d"
                                  % (node.node_id, active, cand["v"]))
                    break
                for sev, code, msg in problems:
                    self._add(sev, code, node.node_id, msg)
            # MINI-SPECS 5.4 / SPEC 10 step 5: an unsafe path makes its VERSION
            # unusable, never the node; one in a version the walk did not need
            # (newer than `active`, older than the resolved one) is still an
            # error in the manifest, reported -- as werk-core reports it.
            for v in node.versions:
                if not isinstance(v, dict) or id(v) in tried or not isinstance(v.get("files"), list):
                    continue
                for f in v["files"]:
                    p = f.get("path") if isinstance(f, dict) else None
                    if isinstance(p, string_types) and _unsafe(p):
                        self._add("error", "schema-invalid", node.node_id,
                                  _unsafe_msg("%s v%s" % (node.node_id, v.get("v")), p))
            if node.resolved is None:
                node.status, node.reason = "dead", "no usable version"
                self._add("error", "node-dead", node.node_id, "%s: no usable version" % node.node_id)
                continue
            ver = node.version()
            declared = self._declared_formats(node, ver)
            for f in ver.get("files", []):
                path = f.get("path")
                if path in declared:
                    continue
                try:
                    head = self._head(path)
                except Exception:  # noqa: BLE001
                    continue
                if not is_envelope_magic(head):
                    continue
                try:
                    read_envelope(self.container.read(path))
                    self.envelopes_validated += 1
                except Exception as e:  # noqa: BLE001
                    node.status, node.reason = "dead", "envelope-invalid"
                    self._add("error", "envelope-invalid", node.node_id,
                              "%s: %s: %s" % (node.node_id, path, e))
            if node.status == "dead":
                continue
            if not (isinstance(node.type, string_types) and node.type.startswith("core.")):
                node.status = "skipped"
                node.reason = "unknown node type `%s`" % node.type
                self._add("warn", "node-skipped-unknown-type", node.node_id,
                          "%s: type `%s` is not interpreted; its bytes are verified and "
                          "extractable" % (node.node_id, node.type))
            if node.type == "core.loader" and node.meta.get("form") == "prebuilt":
                self._add("info", "prebuilt-not-executed", node.node_id,
                          "%s carries a prebuilt binary; it was NOT executed (SPEC 7.1)" % node.node_id)

    def _head(self, path):
        if isinstance(self.container, DirContainer):
            with _bopen(self.container._full(path), "rb") as fh:
                return fh.read(4)
        return self.container.read(path)[:4]

    @staticmethod
    def _declared_formats(node, ver):
        meta = node.meta
        files = ver.get("files", [])
        out = set()
        if isinstance(meta.get("payload_format"), string_types):
            try:
                out.add(payload_path(node, ver.get("v")))
            except WerkError:
                pass
        roles = meta.get("file_formats")
        if isinstance(roles, dict):
            for f in files:
                if isinstance(f.get("role"), string_types) and f.get("role") in roles:
                    out.add(f.get("path"))
        return out

    def _edges(self):
        changed = True
        while changed:
            changed = False
            for n in self.nodes:
                if n.status == "dead":
                    continue
                for e in n.edges:
                    t = self._by_id.get(e.get("to")) if isinstance(e, dict) and isinstance(e.get("to"), string_types) else None
                    if t is None and isinstance(e, dict) and isinstance(e.get("to"), string_types)                             and e.get("kind") == "requires":
                        # SPEC 5 "Edge targets": a `requires` edge to a node
                        # absent from nodes[] kills the source, skipped or not.
                        n.status, n.reason = "dead", "requires `%s`, which is not a node" % e["to"]
                        self._add("error", "requires-missing-node", n.node_id,
                                  "%s: a `requires` edge to `%s`, which is not a node in "
                                  "this manifest" % (n.node_id, e["to"]))
                        changed = True
                        break
                    if t is not None and t.status == "dead" and e.get("kind") == "requires":
                        n.status, n.reason = "dead", "requires dead node `%s`" % e["to"]
                        self._add("error", "requires-dead-node", n.node_id,
                                  "%s: a `requires` edge into dead node `%s`" % (n.node_id, e["to"]))
                        changed = True
                        break
        for n in self.nodes:
            for e in n.edges:
                if not isinstance(e, dict) or not isinstance(e.get("to"), string_types):
                    continue
                t = self._by_id.get(e.get("to"))
                if t is None and e.get("kind") == "requires":
                    continue   # reported above as requires-missing-node
                if t is None:
                    self._add("warn", "edge-dangling", n.node_id,
                              "%s: edge points at `%s`, which is not a node" % (n.node_id, e.get("to")))
                elif t.status == "dead" and e.get("kind") == "enhances":
                    self._add("warn", "enhances-dead-node", n.node_id,
                              "%s: `enhances` dead node `%s` (one feature lost)" % (n.node_id, e["to"]))

    def _floating(self):
        declared = set()
        for n in self.nodes:
            for v in n.versions:
                for f in (v.get("files") or []) if isinstance(v, dict) else []:
                    if isinstance(f, dict) and isinstance(f.get("path"), string_types):
                        declared.add(f.get("path"))
        for name in self.container.names():
            if name not in (MANIFEST, SIGNATURE) and name not in declared:
                self._add("warn", "floating-file", None,
                          "%s is in the container but no node declares it" % name)

    def _spec_sha256(self):
        declared = self.manifest.get("spec_sha256")
        computed = spec_sha256_of(self.manifest.get("nodes", []))
        self.spec_sha256_computed = computed
        if declared is not None and declared != computed:
            self._add("error", "spec-sha256-mismatch", None,
                      "spec_sha256 declares %s; the spec/ files the manifest lists digest to %s"
                      % (declared, computed))

    def _input_hashes(self):
        """`stale-derived-data` (warn): a declared input_hash that is not the
        hash of the declared inputs as they are in this container."""
        for n in self.nodes:
            ver = n.version()
            if not ver or "input_hash" not in ver:
                continue
            paths = ver.get("input_files") if isinstance(ver.get("input_files"), list) else []
            if not all(isinstance(x, string_types) for x in paths):
                continue
            try:
                digests = [_unhex(self._file_hash(p)[0]) for p in paths]
            except Exception:  # noqa: BLE001 - an input that is not here is not checkable
                continue
            got = input_hash_of(digests, ver.get("input_params") or {})
            if got != ver["input_hash"]:
                self._add("warn", "stale-derived-data", n.node_id,
                          "%s v%s: input_hash %s, the declared inputs hash to %s"
                          % (n.node_id, ver.get("v"), ver["input_hash"], got))

    # -- public API ------------------------------------------------------
    def node(self, node_id):
        n = self._by_id.get(node_id)
        if n is None:
            raise WerkError("no node %r" % node_id)
        return n

    def read_file(self, path):
        """The bytes of one declared file. Never a path outside files[] (step 9)."""
        if not any(f.get("path") == path for n in self.nodes for v in n.versions
                   for f in (v.get("files") or [])):
            if path not in (MANIFEST, SIGNATURE):
                raise WerkError("%s is not declared by any node; refusing to read it" % path)
        return self.container.read(path)

    def payload_path(self, node_id, version=None):
        n = self.node(node_id)
        if version is None and n.resolved is None:
            raise WerkError("node %s is dead: %s" % (node_id, n.reason))
        return payload_path(n, version)

    def read_payload(self, node_id, version=None):
        """The bytes of THE payload of a node's resolved (or given) version,
        resolved by SPEC section 2.1 -- never files[0] by default."""
        n = self.node(node_id)
        if version is None and n.status == "dead":
            raise WerkError("node %s is dead: %s" % (node_id, n.reason))
        return self.container.read(payload_path(n, version))

    def primary(self, key):
        """(node_id, fell_back): the node `primary.<key>` names, or the
        documented fallback (SPEC section 2, PROFILE-IMAGE section 3)."""
        prim = self.manifest.get("primary")
        if isinstance(prim, dict) and isinstance(prim.get(key), string_types):
            return prim[key], False
        alive = [n for n in self.nodes if n.status != "dead"]
        pick = None
        if key == "image":
            if self.profile == "image/1":
                pick = next((n for n in alive if n.type == "core.image.source"), None)
            else:
                pick = next((n for n in alive if n.type == "core.imposter"), None) or next(
                    (n for n in alive if n.type == "core.tex" and n.meta.get("usage") == "base-color"), None)
        elif key == "mesh":
            pick = next((n for n in alive if n.type == "core.geom.game"), None)
        elif key == "thumbnail":
            th = [n for n in alive if n.type == "core.image.derived"
                  and n.meta.get("derived_role") == "thumbnail"]
            th.sort(key=lambda n: n.meta.get("width") or 0)
            pick = th[0] if th else None
        if pick is None:
            raise WerkError("no primary %s declared and the documented fallback finds none" % key)
        return pick.node_id, True

    def primary_image(self):
        """(node_id, path, bytes) of THE image."""
        nid, _fb = self.primary("image")
        return nid, self.payload_path(nid), self.read_payload(nid)

    def primary_mesh(self):
        """(node_id, path, bytes) of THE mesh (a GLB)."""
        prim = self.manifest.get("primary") or {}
        nid = prim.get("mesh") or (prim.get("geometry") if isinstance(prim.get("geometry"), string_types)
                                  and self.node(prim["geometry"]).type in MESH_TYPES else None)
        if not nid:
            nid, _fb = self.primary("mesh")
        return nid, self.payload_path(nid), self.read_payload(nid)

    def extract(self, out_dir, node_ids=None, all_versions=False):
        """Materialise files of the resolved versions (or of every version) of
        the given nodes (default: all live and skipped nodes) under out_dir.
        Returns the list of package paths written."""
        written = []
        for n in self.nodes:
            if node_ids is not None and n.node_id not in node_ids:
                continue
            if n.status == "dead" and not all_versions:
                continue
            vers = n.versions if all_versions else [n.version()]
            for ver in vers:
                for f in (ver or {}).get("files", []):
                    p = f["path"]
                    if p in written:
                        continue
                    _reject_unsafe(p)
                    target = os.path.join(out_dir, *p.split("/"))
                    _makedirs(os.path.dirname(target))
                    with _bopen(target, "wb") as fh:
                        fh.write(self.container.read(p))
                    written.append(p)
        return written

    def census(self):
        alive = sum(1 for n in self.nodes if n.status == "alive")
        dead = sum(1 for n in self.nodes if n.status == "dead")
        return alive, sum(1 for n in self.nodes if n.status == "skipped"), dead

    def verdict(self):
        """The comparable summary the cross-matrix asserts across readers."""
        alive, skipped, dead = self.census()
        errs = sorted(set(e.code for e in self.report if e.severity == "error"))
        files = verified = 0
        for n in self.nodes:
            if n.resolved is not None:
                files += len(n.version().get("files", []))
                if n.status != "dead":
                    verified += len(n.version().get("files", []))
        return OrderedDict([
            ("exit", EXIT_ERRORS if errs else EXIT_OK),
            ("profile", self.profile),
            ("form", self.form),
            ("signature", self.signature_state),
            ("nodes", len(self.nodes)), ("alive", alive), ("skipped", skipped), ("dead", dead),
            ("dead_nodes", sorted(n.node_id for n in self.nodes if n.status == "dead")),
            ("error_codes", errs),
            ("envelopes", self.envelopes_validated),
            ("manifest_sha256", self.manifest_sha256),
            ("spec_sha256_ok", self.manifest.get("spec_sha256") == self.spec_sha256_computed),
            ("schema_validated", False),
        ])


def open(path):  # noqa: A001 - the obvious name, shadowing builtins.open only as werk.open
    """Open a werk package (a .werk zip or a directory). Raises ContainerRefusal
    for SPEC section 10.1's container scope; damage below that is in .report."""
    return Package(path)


# ---------------------------------------------------------------------------
# Hash constructions (SPEC section 2, MINI-SPECS section 11) and signatures
# ---------------------------------------------------------------------------

def spec_sha256_of(nodes):
    """Over every spec/ path any version of any node declares, sorted by UTF-8
    bytes: path, LF, the sha256 as 32 raw bytes, LF."""
    declared = {}
    for n in nodes:
        for v in (n.get("versions") or []) if isinstance(n, dict) else []:
            for f in (v.get("files") or []) if isinstance(v, dict) else []:
                p = f.get("path") if isinstance(f, dict) else None
                if isinstance(p, string_types) and p.startswith("spec/"):
                    declared[p] = f.get("sha256")
    h = hashlib.sha256()
    for p in sorted(declared, key=_utf8):
        try:
            raw = _unhex(declared[p])
        except (TypeError, ValueError, binascii.Error):
            raw = b""
        h.update(_utf8(p) + b"\n" + raw + b"\n")
    return h.hexdigest()


def input_hash_of(raw_digests, params):
    h = hashlib.sha256()
    for d in raw_digests:
        h.update(d)
    h.update(json_canonical(params if params is not None else {}))
    return h.hexdigest()


def signature_message(manifest_sha256, prev, signed_at, uri, kind):
    return u"\n".join([u"werk-sig/1", manifest_sha256, prev, signed_at, uri, kind]).encode("utf-8")


def verify_chain(raw, manifest_sha256):
    """(problems, signers): problems is [] when every link verifies, None when
    the algorithm is not one this reader implements (`unverified`)."""
    try:
        doc = json_loads(raw)
    except Exception as e:  # noqa: BLE001
        return ["SIGNATURE.json is not valid JSON: %s" % e], []
    if not isinstance(doc, dict):
        return ["SIGNATURE.json is not an object"], []
    # SPEC section 6 / 10.1: a foreign algorithm is `unverified` (a statement
    # about this reader); no algorithm, or not a string, is a chain that cannot
    # be read -- present-and-invalid. Exactly werk-core's rule.
    alg = doc.get("algorithm")
    if alg is None:
        return ["SIGNATURE.json has no `algorithm`"], []
    if not isinstance(alg, string_types):
        return ["SIGNATURE.json `algorithm` is not a string"], []
    if alg != "ed25519":
        return None, []
    problems, signers = [], []
    if doc.get("manifest_sha256") != manifest_sha256:
        problems.append("top-level manifest_sha256 %s is not the manifest present (%s)"
                        % (doc.get("manifest_sha256"), manifest_sha256))
    chain = doc.get("chain")
    if not isinstance(chain, list) or not chain:
        return problems + ["chain is empty or not an array"], []
    prev_sig = None
    for i, e in enumerate(chain):
        where = "chain[%d]" % i
        if not isinstance(e, dict):
            problems.append("%s is not an object" % where)
            break
        if e.get("index") != i:
            problems.append("%s declares index %r" % (where, e.get("index")))
        signer = e.get("signer") if isinstance(e.get("signer"), dict) else {}
        em = e.get("manifest_sha256")
        if not isinstance(em, string_types):
            problems.append("%s has no manifest_sha256" % where)
            em = u""
        elif i == len(chain) - 1 and em != manifest_sha256:
            problems.append("%s is the newest link and signs manifest %s, not the one present"
                            % (where, em))
        expected = u"0" * 64 if i == 0 else sha256_hex(_utf8(prev_sig or u""))
        prev = e.get("prev_entry_sha256", u"")
        if prev != expected:
            problems.append("%s prev_entry_sha256 breaks the chain" % where)
        sig_hex, pub_hex = e.get("signature", u""), e.get("public_key", u"")
        try:
            sig, pub = _unhex(sig_hex), _unhex(pub_hex)
        except (TypeError, ValueError, binascii.Error):
            problems.append("%s public_key or signature is not hex" % where)
            prev_sig = sig_hex
            continue
        fields = [em, prev if isinstance(prev, string_types) else u"", e.get("signed_at", u""),
                  signer.get("uri", u""), signer.get("kind", u"")]
        if not all(isinstance(x, string_types) for x in fields):
            problems.append("%s has a non-string field" % where)
        elif not ed25519_verify(pub, signature_message(*fields), sig):
            problems.append("%s Ed25519 signature does not verify" % where)
        else:
            signers.append(u"%s <%s>" % (signer.get("name", u"?"), signer.get("uri", u"")))
        prev_sig = sig_hex if isinstance(sig_hex, string_types) else u""
    return problems, signers


def chain_append(existing_doc, manifest_sha256, secret, uri, kind, name, signed_at,
                 role=None, note=None):
    """Return the SIGNATURE.json object with one entry appended over
    `manifest_sha256` (or a new one-entry chain when existing_doc is None)."""
    if existing_doc is None:
        doc = OrderedDict([("werk_signature", 1), ("algorithm", "ed25519"),
                           ("encoding", "hex-lowercase"), ("manifest_sha256", manifest_sha256),
                           ("chain", [])])
    else:
        doc = existing_doc
        doc["manifest_sha256"] = manifest_sha256
    chain = doc["chain"]
    prev = u"0" * 64 if not chain else sha256_hex(_utf8(chain[-1]["signature"]))
    if kind not in ("human", "agent", "service"):
        raise WerkError("signer kind is human, agent or service (signature.schema.json)")
    for fld in (uri, kind, signed_at):
        if "\n" in fld:
            raise WerkError("a signed field may not contain a line feed")
    msg = signature_message(manifest_sha256, prev, signed_at, uri, kind)
    sig = ed25519_sign(secret, msg)
    signer = OrderedDict([("name", name), ("uri", uri), ("kind", kind)])
    if role:
        signer["role"] = role
    e = OrderedDict([("index", len(chain)), ("signer", signer),
                     ("public_key", _hex(ed25519_public_key(secret))),
                     ("signed_at", signed_at), ("manifest_sha256", manifest_sha256),
                     ("prev_entry_sha256", prev), ("signature", _hex(sig))])
    if note:
        e["note"] = note
    chain.append(e)
    return doc


def parse_secret_key(text):
    t = text.strip() if isinstance(text, string_types) else _hex(text)
    if len(t) != 64:
        raise WerkError("an Ed25519 secret key is given as 64 hex digits (the 32-byte seed)")
    return _unhex(t.lower())


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

import re as _re  # noqa: E402

_ID = _re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_PATH = _re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@/-]*$")
_TYPE = _re.compile(r"^(core|x)\.[a-z0-9-]+(\.[a-z0-9-]+)*$")


def check_id(s, what="id"):
    if not isinstance(s, string_types) or not _ID.match(s):
        raise WerkError("%s %r is not kebab-case ([a-z0-9]+(-[a-z0-9]+)*)" % (what, s))


def check_path(p):
    if (not isinstance(p, string_types) or not _PATH.match(p) or len(p) > 1024
            or ".." in p.split("/") or p.endswith("/") or "//" in p):
        raise WerkError("package path %r is not legal: relative POSIX, ASCII letters, digits "
                        "and . _ @ / - only, first character a letter or digit, no '..' "
                        "(manifest.schema.json $defs/path)" % (p,))
    if p in (MANIFEST, SIGNATURE):
        raise WerkError("%s is written by the writer itself" % p)


class LocalFile(object):
    """A payload taken from a file on disk, streamed (for the directory form of
    a package whose payloads do not fit comfortably in memory)."""

    def __init__(self, path):
        self.path = path
        h = hashlib.sha256()
        c = 0
        n = 0
        with _bopen(path, "rb") as fh:
            while True:
                b = fh.read(1 << 20)
                if not b:
                    break
                h.update(b)
                c = zlib.crc32(b, c)
                n += len(b)
        self.sha256, self.size, self.crc32 = h.hexdigest(), n, c & 0xFFFFFFFF

    def read(self):
        with _bopen(self.path, "rb") as fh:
            return fh.read()


def _blob_info(data):
    if isinstance(data, LocalFile):
        return data.sha256, data.size, data.crc32
    return sha256_hex(data), len(data), zlib.crc32(data) & 0xFFFFFFFF


def _version_record(v, files, note, producer, epistemic, created, payload_file=None,
                    confidence=None, input_files=None, input_params=None, input_hash=None,
                    extra=None):
    r = OrderedDict([("v", v), ("files", files)])
    if payload_file is not None:
        r["payload_file"] = payload_file
    r["note"] = note
    r["producer"] = producer
    r["epistemic"] = epistemic
    if confidence is not None:
        r["confidence"] = confidence
    r["created"] = created
    if input_files is not None:
        r["input_files"] = list(input_files)
        r["input_params"] = input_params if input_params is not None else OrderedDict()
        r["input_hash"] = input_hash
    if extra:
        for k, val in extra.items():
            r[k] = val
    return r


def _check_note(note):
    if not isinstance(note, string_types) or len(note) < 8 or len(note) > 2000:
        raise WerkError("every version carries a work note of 8-2000 characters saying why "
                        "it exists (law 6); got %r" % (note,))


def at_marker(path, n):
    """`doc/body.json` -> `doc/body@1.json`; marker before the last extension
    of the FILE name, or at the end of a name with no extension (SPEC section 5)."""
    d, _, name = path.rpartition("/")
    dot = name.rfind(".")
    name = (name[:dot] + "@%d" % n + name[dot:]) if dot > 0 else (name + "@%d" % n)
    return (d + "/" + name) if d else name


class PackageWriter(object):
    """Build a werk package and write it as a store-mode zip or a directory.

        w = PackageWriter("image/1", name="Sunset", created="2026-11-07T12:00:00Z",
                          uuid="...")
        w.add_node("image-source", "core.image.source",
                   [w.file("image/source.png", png_bytes, "image/png")],
                   note="The image as the camera delivered it.", meta={...})
        w.set_primary("image", "image-source")
        w.write("out.werk")             # or w.write("out-dir", form="directory")

    Everything that is not given is taken from the vendored bundle: spec/ and
    loaders/ byte for byte with their node records, the conventions of the
    profile, LICENSE ("terms not established") and README.txt texts. The output
    is a function of the input alone: same input, same bytes, in every libs/
    writer (Python, JavaScript, Rust)."""

    def __init__(self, profile, name, summary=None, uuid=None, created=None,
                 conventions=None, generator=None, producer=None, license_text=None,
                 spdx_id=None, readme_text=None, bundle=None, manifest_schema=None,
                 profile_spec=None, spec_files=None, conventions_map=None):
        self.bundle = bundle or default_bundle()
        info = self.bundle.info
        ptab = info["profiles"].get(profile)
        if ptab is None:
            if conventions is None or manifest_schema is None:
                raise WerkError("profile %r is not built in: pass conventions= and "
                                "manifest_schema= (SPEC section 2.2)" % profile)
            ptab = OrderedDict([("conventions", conventions), ("manifest_schema", manifest_schema),
                                ("conventions_map", None), ("has_parts", False),
                                ("preview_prefixes", ["semantics/"])])
        if not isinstance(name, string_types) or not (1 <= len(name) <= 200):
            raise WerkError("entity name must be 1-200 characters")
        self.profile = profile
        self.ptab = ptab
        self.created = created or _utc_now()
        _dos_datetime(self.created)
        self.uuid = (uuid or text_type(_uuid.uuid4())).lower()
        if not _re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", self.uuid):
            raise WerkError("uuid must be an RFC 4122 uuid in lower case")
        self.name, self.summary = name, summary
        self.conventions = conventions if conventions is not None else ptab["conventions"]
        self.manifest_schema = manifest_schema or ptab["manifest_schema"]
        self.profile_spec = profile_spec
        if conventions_map is not None:
            check_path(conventions_map)
        self.conventions_map = conventions_map
        lv = info["lib_version"]
        self.generator = generator or OrderedDict([("tool", "werk"), ("version", lv)])
        self.producer = producer or OrderedDict([("tool", "werk"), ("version", lv)])
        self.license_text = license_text
        self.spdx_id = spdx_id
        self.readme_text = readme_text
        self.nodes = OrderedDict()
        self.blobs = OrderedDict()          # path -> bytes | LocalFile
        self.owner = {}                     # path -> node_id
        self.primary = OrderedDict()
        self.parts = []
        self.materials = []
        self.schemas = OrderedDict()
        self.layouts = OrderedDict()
        self.formats = OrderedDict()
        self.preview_exact = []             # exact paths placed in the preview tier
        self.extra_order = []               # exact paths placed early in entry_order
        self.signers = []
        self._carry()
        for sp_path, sp_data in sorted((spec_files or {}).items(), key=lambda kv: _utf8(kv[0])):
            self.add_spec_file(sp_path, sp_data)

    # -- the parts nobody authors ----------------------------------------
    def _carry(self):
        info = self.bundle.info
        texts = info["texts"]
        spec_files = []
        for path, rec in self.bundle.files.items():
            if path.startswith("spec/"):
                self.blobs[path] = _BundleBlob(self.bundle, path)
                self.owner[path] = "spec"
                spec_files.append(OrderedDict([("path", path), ("sha256", rec["sha256"]),
                                               ("size", rec["size"])]))
        self._node_raw("spec", "core.spec", spec_files, texts["spec_note"], "authored")
        for ld in info["loaders"]:
            rec = self.bundle.files[ld["path"]]
            self.blobs[ld["path"]] = _BundleBlob(self.bundle, ld["path"])
            self.owner[ld["path"]] = ld["node_id"]
            self._node_raw(ld["node_id"], "core.loader",
                           [OrderedDict([("path", ld["path"]), ("sha256", rec["sha256"]),
                                         ("size", rec["size"])])],
                           texts["loader_note"], "authored", meta=ld["meta"])
        lic = _utf8(self.license_text) if self.license_text is not None else _utf8(texts["license_unestablished"])
        self.add_node("license", "core.license", [self.file("LICENSE", lic, "text/plain")],
                      note=texts["license_note"])
        rd = _utf8(self.readme_text) if self.readme_text is not None else _utf8(texts["readme"])
        self.add_node("readme", "core.readme", [self.file("README.txt", rd, "text/plain")],
                      note=texts["readme_note"])

    def _node_raw(self, node_id, ntype, files, note, epistemic, meta=None):
        n = OrderedDict([("node_id", node_id), ("type", ntype),
                         ("versions", [_version_record(1, files, note, self.producer, epistemic,
                                                       self.created)]),
                         ("active", 1), ("edges", [])])
        if meta is not None:
            n["meta"] = meta
        self.nodes[node_id] = n

    # -- authoring ---------------------------------------------------------
    @staticmethod
    def file(path, data, media_type=None, role=None):
        """A file of a node: its package path, its bytes (or a LocalFile), and
        optionally a media type and a role (`payload`, `descriptor`, ...)."""
        check_path(path)
        if role is not None:
            check_id(role, "role")
        if not isinstance(data, (bytes, bytearray, LocalFile)):
            raise WerkError("file data must be bytes or a LocalFile")
        return (path, bytes(data) if isinstance(data, bytearray) else data, media_type, role)

    def add_node(self, node_id, type, files, note, epistemic="authored", producer=None,
                 meta=None, edges=None, input_files=None, input_params=None,
                 payload_file=None, part_id=None, material_id=None, confidence=None,
                 created=None):
        """Add a node with one version. `files` is a list of `file(...)`.
        `epistemic` is authored | measured | inferred; measured and inferred
        need `input_files` (package paths) and take `input_params` -- the
        input_hash is computed here (MINI-SPECS section 11)."""
        check_id(node_id, "node_id")
        if node_id in self.nodes:
            raise WerkError("node %s already exists" % node_id)
        if not isinstance(type, string_types) or not _TYPE.match(type):
            raise WerkError("node type %r is not core.* or x.* kebab-case" % (type,))
        if epistemic not in ("authored", "measured", "inferred"):
            raise WerkError("epistemic is authored, measured or inferred")
        if epistemic != "authored" and not input_files:
            raise WerkError("a %s version names its inputs (law 5): pass input_files" % epistemic)
        _check_note(note)
        if not files:
            raise WerkError("a version owns at least one file")
        recs = []
        for path, data, mt, role in files:
            if path in self.owner:
                raise WerkError("%s is already listed by node %s" % (path, self.owner[path]))
            sha, size, _crc = _blob_info(data)
            r = OrderedDict([("path", path), ("sha256", sha), ("size", size)])
            if mt:
                r["media_type"] = mt
            if role:
                r["role"] = role
            recs.append(r)
            self.blobs[path] = data
            self.owner[path] = node_id
        if payload_file is None and len(recs) > 1:
            roled = [r["path"] for r in recs if r.get("role") == "payload"]
            payload_file = roled[0] if len(roled) == 1 else None
        if payload_file is not None and payload_file not in [r["path"] for r in recs]:
            raise WerkError("payload_file %s is not one of the version's files" % payload_file)
        ih = None
        if input_files is not None:
            input_params = input_params if input_params is not None else OrderedDict()
            ih = input_hash_of([_unhex(self._sha_of(p)) for p in input_files], input_params)
        n = OrderedDict([("node_id", node_id), ("type", type)])
        if part_id is not None:
            check_id(part_id, "part_id")
            n["part_id"] = part_id
        if material_id is not None:
            check_id(material_id, "material_id")
            n["material_id"] = material_id
        n["versions"] = [_version_record(1, recs, note, producer or self.producer, epistemic,
                                         created or self.created, payload_file, confidence,
                                         input_files, input_params, ih)]
        n["active"] = 1
        n["edges"] = [self._edge(e) for e in (edges or [])]
        if meta is not None:
            n["meta"] = meta
        self.nodes[node_id] = n
        sp = self.bundle.info["schemas_by_type"].get(type)
        if sp and type not in self.schemas:
            self.schemas[type] = sp
        lp = self.bundle.info["layouts_by_type"].get(type)
        if lp and type not in self.layouts:
            self.layouts[type] = lp
        return n

    @staticmethod
    def _edge(e):
        if isinstance(e, (list, tuple)):
            e = OrderedDict(zip(("to", "kind", "role"), e))
        out = OrderedDict([("to", e["to"]), ("kind", e["kind"])])
        check_id(out["to"], "edge target")
        if out["kind"] not in ("requires", "enhances"):
            raise WerkError("edge kind is requires or enhances")
        if e.get("role"):
            check_id(e["role"], "edge role")
            out["role"] = e["role"]
        return out

    def _sha_of(self, path):
        if path not in self.blobs:
            raise WerkError("input file %s is not in the package (law 1: inputs are carried)" % path)
        b = self.blobs[path]
        if isinstance(b, _BundleBlob):
            return self.bundle.files[path]["sha256"]
        return _blob_info(b)[0]

    def set_primary(self, key, node_id):
        check_id(node_id, "primary node")
        self.primary[key] = node_id

    def add_part(self, part_id, name, parent=None, translation=(0, 0, 0), rotation=(1, 0, 0, 0),
                 scale=(1, 1, 1)):
        check_id(part_id, "part_id")
        self.parts.append(OrderedDict([
            ("part_id", part_id), ("name", name), ("parent", parent),
            ("transform", OrderedDict([("translation", list(translation)),
                                       ("rotation", list(rotation)), ("scale", list(scale))]))]))

    def add_material(self, material_id, name, part_id=None, klass=None):
        check_id(material_id, "material_id")
        m = OrderedDict([("material_id", material_id), ("name", name)])
        if part_id is not None:
            m["part_id"] = part_id
        if klass is not None:
            m["class"] = klass
        self.materials.append(m)

    def set_schema(self, node_type, path):
        self.schemas[node_type] = path

    def set_layout(self, node_type, path):
        self.layouts[node_type] = path

    def add_spec_file(self, path, data, media_type=None):
        """Carry one more file in `spec/`, or replace a vendored one: a
        profile's narrative and schema (`spec/PROFILE-RASTER-LAYERS.md`,
        `spec/schemas/manifest.raster-layers.schema.json`), a format definition
        (`spec/formats/<id>.md`), a newer revision of a bundled document. The
        file joins the `core.spec` node (whose files stay sorted by UTF-8
        path), so it is hashed, listed and covered by `spec_sha256` like every
        other specification file (SPEC section 2.2). Point `manifest_schema=`,
        `profile_spec=`, `set_schema()`, `set_layout()` or `set_format()` at it
        as the profile requires. Returns True when it replaced a bundled file."""
        check_path(path)
        if not path.startswith("spec/"):
            raise WerkError("a specification file lives under spec/: %r" % path)
        if not isinstance(data, (bytes, bytearray)):
            raise WerkError("spec file data must be bytes")
        data = bytes(data)
        owner = self.owner.get(path)
        if owner is not None and owner != "spec":
            raise WerkError("%s is already listed by node %s" % (path, owner))
        replaced = path in self.blobs
        self.blobs[path] = data
        self.owner[path] = "spec"
        rec = OrderedDict([("path", path), ("sha256", sha256_hex(data)), ("size", len(data))])
        if media_type:
            rec["media_type"] = media_type
        files = [f for f in self.nodes["spec"]["versions"][0]["files"] if f["path"] != path]
        files.append(rec)
        files.sort(key=lambda f: _utf8(f["path"]))
        self.nodes["spec"]["versions"][0]["files"] = files
        return replaced

    def add_readme_file(self, path, data, media_type=None):
        """Add a file to the `core.readme` node -- a HOW-TO-READ.md, a
        translated README -- beside README.txt. The version then declares
        `payload_file: "README.txt"` (SPEC section 2.1), so the node's payload
        stays determinable. Files keep the order they were added in."""
        check_path(path)
        if not isinstance(data, (bytes, bytearray)):
            raise WerkError("readme file data must be bytes")
        if path in self.owner:
            raise WerkError("%s is already listed by node %s" % (path, self.owner[path]))
        data = bytes(data)
        self.blobs[path] = data
        self.owner[path] = "readme"
        rec = OrderedDict([("path", path), ("sha256", sha256_hex(data)), ("size", len(data))])
        if media_type:
            rec["media_type"] = media_type
        ver = self.nodes["readme"]["versions"][0]
        files = list(ver["files"]) + [rec]
        new = OrderedDict()
        for k, val in ver.items():
            if k == "payload_file":
                continue
            new[k] = files if k == "files" else val
            if k == "files":
                new["payload_file"] = "README.txt"
        self.nodes["readme"]["versions"][0] = new

    def set_format(self, format_id, path):
        self.formats[format_id] = path

    def preview(self, path):
        """Place an exact path in the preview tier (early in the zip)."""
        if path not in self.preview_exact:
            self.preview_exact.append(path)

    def sign(self, secret_key, uri, kind="human", name=None, role="author", note=None,
             signed_at=None):
        """Sign on write. `secret_key`: the 32-byte Ed25519 seed (bytes or 64 hex)."""
        sk = parse_secret_key(secret_key) if isinstance(secret_key, string_types) else bytes(secret_key)
        self.signers.append((sk, uri, kind, name or uri, role, note, signed_at or self.created))

    # -- assembling ----------------------------------------------------------
    def entry_order(self):
        head = list(self.bundle.info["head_order"])
        dirs = sorted(set(p.split("/", 1)[0] + "/" for p in self.blobs if "/" in p), key=_utf8)
        order = list(head)
        for pre in self.ptab["preview_prefixes"]:
            if pre in dirs and pre not in order:
                order.append(pre)
        for p in self.preview_exact:
            if p not in order:
                order.append(p)
        for d in dirs:
            if d not in order:
                order.append(d)
        return order, list(head) + [p for p in self.ptab["preview_prefixes"] if p in dirs] + list(self.preview_exact)

    def manifest(self, form):
        entry_order, tier = self.entry_order()
        m = OrderedDict()
        m["werk"] = OrderedDict([("major", 1), ("minor", 0)])
        m["profile"] = self.profile
        m["manifest_schema"] = self.manifest_schema
        if self.profile_spec:
            m["profile_spec"] = self.profile_spec
        m["spec_sha256"] = spec_sha256_of(list(self.nodes.values()))
        ent = OrderedDict([("uuid", self.uuid), ("name", self.name)])
        if self.summary is not None:
            ent["summary"] = self.summary
        ent["created"] = self.created
        m["entity"] = ent
        m["conventions"] = self.conventions
        if self.conventions_map is not None:
            if self.conventions_map not in self.blobs or self.owner.get(self.conventions_map) != "spec":
                raise WerkError("conventions_map names %s, which is not a spec/ file of this package "
                                "(carry it with add_spec_file)" % self.conventions_map)
            m["conventions_map"] = self.conventions_map
        else:
            cmap = self.ptab.get("conventions_map")
            if cmap and cmap in self.blobs:
                m["conventions_map"] = cmap
        m["container"] = OrderedDict([("form", form), ("zip_compression", "store"),
                                      ("entry_order", entry_order), ("preview_tier", tier)])
        if self.primary:
            m["primary"] = self.primary
        lic = OrderedDict()
        if self.spdx_id:
            lic["spdx_id"] = self.spdx_id
        lic["file"] = "LICENSE"
        lic["sha256"] = self._sha_of("LICENSE")
        m["license"] = lic
        m["schemas"] = self.schemas
        m["layouts"] = self.layouts
        if self.formats:
            m["formats"] = self.formats
        if self.ptab.get("has_parts"):
            m["parts"] = self.parts
            m["materials"] = self.materials
        m["nodes"] = list(self.nodes.values())
        m["generator"] = self.generator
        for nid in self.primary.values():
            if nid not in self.nodes:
                raise WerkError("primary names %s, which is not a node" % nid)
        for n in self.nodes.values():
            for e in n["edges"]:
                if e["to"] not in self.nodes:
                    raise WerkError("%s has an edge to %s, which is not a node" % (n["node_id"], e["to"]))
        return m

    def build(self, form="zip"):
        """(files, manifest_bytes, signature_bytes|None): the package's content."""
        mb = json_pretty(self.manifest(form))
        sb = None
        if self.signers:
            msha = sha256_hex(mb)
            doc = None
            for sk, uri, kind, name, role, note, at in self.signers:
                doc = chain_append(doc, msha, sk, uri, kind, name, at, role, note)
            sb = json_pretty(doc)
        return self.blobs, mb, sb

    def write(self, out, form=None):
        """Write to `out`: a zip when out ends in .werk / .zip (or form="zip"),
        else a directory (form="directory"). Returns the manifest sha256."""
        if form is None:
            form = "zip" if out.lower().endswith((".werk", ".zip")) else "directory"
        blobs, mb, sb = self.build(form)
        write_container(out, form, blobs, mb, sb, self.manifest(form)["container"]["entry_order"],
                        self.created, self.bundle)
        return sha256_hex(mb)

    def to_bytes(self):
        import io
        blobs, mb, sb = self.build("zip")
        buf = io.BytesIO()
        _write_zip(buf, blobs, mb, sb, self.manifest("zip")["container"]["entry_order"],
                   self.created, self.bundle)
        return buf.getvalue()


class _BundleBlob(object):
    """A vendored file, read from the bundle when written."""
    __slots__ = ("bundle", "path")

    def __init__(self, bundle, path):
        self.bundle, self.path = bundle, path


def _blob_bytes(b, bundle):
    if isinstance(b, _BundleBlob):
        return b.bundle.data(b.path)
    if isinstance(b, LocalFile):
        return b.read()
    return b


def _write_zip(fh, blobs, mb, sb, entry_order, created, bundle=None):
    allp = list(blobs.keys()) + [MANIFEST] + ([SIGNATURE] if sb is not None else [])
    zw = ZipWriter(fh, created)
    for p in physical_order(allp, entry_order):
        if p == MANIFEST:
            zw.add(p, mb)
        elif p == SIGNATURE:
            zw.add(p, sb)
        else:
            b = blobs[p]
            crc = b.bundle.files[p]["crc32"] if isinstance(b, _BundleBlob) else None
            zw.add(p, _blob_bytes(b, bundle), crc)
    zw.close()


def write_container(out, form, blobs, mb, sb, entry_order, created, bundle=None):
    if form == "zip":
        tmp = out + ".partial"
        with _bopen(tmp, "wb") as fh:
            _write_zip(fh, blobs, mb, sb, entry_order, created, bundle)
        if os.path.exists(out):
            os.remove(out)
        os.rename(tmp, out)
        return
    if form != "directory":
        raise WerkError("form is zip or directory")
    if os.path.exists(out) and os.listdir(out):
        raise WerkError("%s exists and is not empty; a directory package is written fresh" % out)
    items = [(p, b) for p, b in blobs.items()] + [(MANIFEST, mb)] + ([(SIGNATURE, sb)] if sb else [])
    for p, b in items:
        full = os.path.join(out, *p.split("/"))
        _makedirs(os.path.dirname(full))
        if isinstance(b, LocalFile):
            with _bopen(b.path, "rb") as src, _bopen(full, "wb") as dst:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    dst.write(chunk)
        else:
            with _bopen(full, "wb") as fh:
                fh.write(_blob_bytes(b, bundle))


# ---------------------------------------------------------------------------
# Rewriting an existing package: append a version / a node, sign
# ---------------------------------------------------------------------------

def _load_all(pkg):
    """Every declared file of every version (bytes), keyed by path."""
    blobs = OrderedDict()
    for n in pkg.nodes:
        for v in n.versions:
            for f in v.get("files", []):
                p = f["path"]
                if p not in blobs:
                    blobs[p] = pkg.container.read(p)
    return blobs


def _container_form(out, form):
    if form is None:
        return "zip" if out.lower().endswith((".werk", ".zip")) else "directory"
    return form


def append_version(src, out, node_id, files, note, epistemic="authored", producer=None,
                   created=None, node_type=None, meta=None, edges=None, input_files=None,
                   input_params=None, payload_file=None, form=None, sign_key=None,
                   signer=None, drop_signature=False, preview=False):
    """Save a later version of `node_id` (or add the node, when `node_type` is
    given and the node does not exist) into a copy of package `src`, written
    to `out`. Implements SPEC section 5: new bytes take the plain path, the
    superseded bytes move to stem@N.ext, earlier records keep their hash and
    size; unchanged files of a multi-file node are relisted unchanged.

    `files`: list of PackageWriter.file(...) tuples, by LOGICAL path (no @).
    A signed source needs `sign_key` (a new chain entry over the new
    manifest) or `drop_signature=True`; it is never silently left invalid."""
    pkg = Package(src)
    if pkg.errors():
        raise WerkError("refusing to append to a package that does not verify clean: %s"
                        % "; ".join(e.code for e in pkg.errors()))
    created = created or _utc_now()
    _dos_datetime(created)
    m = pkg.manifest
    blobs = _load_all(pkg)
    owners = {}
    for n in m["nodes"]:
        for v in n["versions"]:
            for f in v["files"]:
                owners[f["path"]] = n["node_id"]
    _check_note(note)
    prod = producer or OrderedDict([("tool", "werk"), ("version", LIB_VERSION)])
    raw = next((n for n in m["nodes"] if n.get("node_id") == node_id), None)
    new_recs = []
    for path, data, mt, role in files:
        if not isinstance(data, (bytes, bytearray)):
            data = _blob_bytes(data, None)
        r = OrderedDict([("path", path), ("sha256", sha256_hex(data)), ("size", len(data))])
        if mt:
            r["media_type"] = mt
        if role:
            r["role"] = role
        new_recs.append((r, bytes(data)))
    if raw is None:
        if not node_type:
            raise WerkError("no node %s; pass node_type to add it" % node_id)
        check_id(node_id, "node_id")
        if not _TYPE.match(node_type):
            raise WerkError("bad node type %r" % node_type)
        for r, data in new_recs:
            if r["path"] in owners:
                raise WerkError("%s already belongs to node %s" % (r["path"], owners[r["path"]]))
            blobs[r["path"]] = data
        ih = None
        if input_files is not None:
            input_params = input_params if input_params is not None else OrderedDict()
            ih = input_hash_of([_unhex(sha256_hex(blobs[p])) for p in input_files], input_params)
        if payload_file is None and len(new_recs) > 1:
            roled = [r["path"] for r, _d in new_recs if r.get("role") == "payload"]
            payload_file = roled[0] if len(roled) == 1 else None
        node = OrderedDict([("node_id", node_id), ("type", node_type),
                            ("versions", [_version_record(1, [r for r, _d in new_recs], note, prod,
                                                          epistemic, created, payload_file, None,
                                                          input_files, input_params, ih)]),
                            ("active", 1),
                            ("edges", [PackageWriter._edge(e) for e in (edges or [])])])
        if meta is not None:
            node["meta"] = meta
        m["nodes"].append(node)
        b = default_bundle()
        sp = b.info["schemas_by_type"].get(node_type)
        if sp and isinstance(m.get("schemas"), dict) and node_type not in m["schemas"]:
            m["schemas"][node_type] = sp
        lp = b.info["layouts_by_type"].get(node_type)
        if lp and isinstance(m.get("layouts"), dict) and node_type not in m["layouts"]:
            m["layouts"][node_type] = lp
    else:
        vs = raw["versions"]
        cur = next(v for v in vs if v["v"] == raw["active"])
        newv = max(v["v"] for v in vs) + 1
        given = OrderedDict((r["path"], (r, d)) for r, d in new_recs)
        out_files = []
        # Relist unchanged files of the current version; supersede changed ones.
        seen = set()
        for f in cur["files"]:
            logical = _strip_marker(f["path"])
            if logical in given:
                r, data = given[logical]
                seen.add(logical)
                if r["sha256"] == f["sha256"] and r["size"] == f["size"] and f["path"] == logical:
                    out_files.append(f)
                    continue
                if f["path"] == logical:
                    # The superseded bytes move to stem@N.ext, N = the version
                    # that INTRODUCED them; every earlier record follows.
                    intro = min(v["v"] for v in vs if any(x["path"] == logical
                                                          and x["sha256"] == f["sha256"]
                                                          for x in v["files"]))
                    moved = at_marker(logical, intro)
                    if moved in owners:
                        raise WerkError("%s already exists; cannot supersede %s" % (moved, logical))
                    for v in vs:
                        for x in v["files"]:
                            if x["path"] == logical:
                                x["path"] = moved
                    blobs[moved] = blobs.pop(logical)
                    owners[moved] = node_id
                    for v in vs:
                        if v.get("payload_file") == logical:
                            v["payload_file"] = moved
                blobs[logical] = data
                owners[logical] = node_id
                out_files.append(r)
            else:
                out_files.append(f)
        for logical, (r, data) in given.items():
            if logical in seen:
                continue
            if logical in owners and owners[logical] != node_id:
                raise WerkError("%s belongs to node %s" % (logical, owners[logical]))
            if logical in blobs:
                raise WerkError("%s is a file of an earlier version; give it a new path" % logical)
            blobs[logical] = data
            owners[logical] = node_id
            out_files.append(r)
        ih = None
        if input_files is not None:
            input_params = input_params if input_params is not None else OrderedDict()
            ih = input_hash_of([_unhex(sha256_hex(blobs[p])) for p in input_files], input_params)
        if payload_file is None and len(out_files) > 1:
            pf = cur.get("payload_file")
            pf = _strip_marker(pf) if isinstance(pf, string_types) else None
            if pf in [f["path"] for f in out_files]:
                payload_file = pf
            else:
                roled = [f["path"] for f in out_files if f.get("role") == "payload"]
                payload_file = roled[0] if len(roled) == 1 else None
        vs.append(_version_record(newv, out_files, note, prod, epistemic, created,
                                  payload_file, None, input_files, input_params, ih))
        raw["active"] = newv
        if meta is not None:
            raw["meta"] = meta
    form = _container_form(out, form)
    _finish_rewrite(pkg, m, blobs, out, form, created, sign_key, signer, drop_signature,
                    preview_path=(new_recs[0][0]["path"] if preview and new_recs else None))
    return out


def _strip_marker(path):
    d, _, name = path.rpartition("/")
    name = _re.sub(r"@[0-9]+(?=\.[^.]*$|$)", "", name, count=1)
    return (d + "/" + name) if d else name


def _finish_rewrite(pkg, m, blobs, out, form, created, sign_key, signer, drop_signature,
                    preview_path=None):
    m["spec_sha256"] = spec_sha256_of(m["nodes"])
    cont = m.get("container")
    if isinstance(cont, dict):
        cont["form"] = form
        if "total_size_bytes" in cont:
            sizes = {}
            for n in m["nodes"]:
                for v in n["versions"]:
                    for f in v["files"]:
                        sizes[f["path"]] = f["size"]
            cont["total_size_bytes"] = sum(sizes.values())
        if preview_path and isinstance(cont.get("entry_order"), list) and preview_path not in cont["entry_order"]:
            cont["entry_order"].append(preview_path)
    mb = json_pretty(m)
    sb = None
    had_sig = pkg.signature_state != SIG_ABSENT
    if sign_key is not None:
        existing = json_loads(pkg.container.read(SIGNATURE)) if had_sig else None
        sg = signer or {}
        sk = parse_secret_key(sign_key) if isinstance(sign_key, string_types) else sign_key
        doc = chain_append(existing, sha256_hex(mb), sk, sg.get("uri", "urn:werk:anonymous"),
                           sg.get("kind", "human"), sg.get("name", sg.get("uri", "urn:werk:anonymous")),
                           sg.get("signed_at", created), sg.get("role", "author"), sg.get("note"))
        sb = json_pretty(doc)
    elif had_sig and not drop_signature:
        raise WerkError("the package is signed; a changed manifest needs a new chain entry "
                        "(pass a signing key) or drop_signature=True. Leaving the old chain "
                        "in place would make the package present-and-invalid")
    order = cont.get("entry_order") if isinstance(cont, dict) else []
    write_container(out, form, blobs, mb, sb, order or [], created)


def sign_package(src, out, secret_key, uri, kind="human", name=None, role="author",
                 note=None, signed_at=None, form=None):
    """Append a chain entry over the package's CURRENT manifest (the manifest
    bytes are not touched) and write the result to `out`."""
    pkg = Package(src)
    if pkg.signature_state == SIG_INVALID:
        raise WerkError("the existing chain is present-and-invalid; refusing to extend it")
    signed_at = signed_at or _utc_now()
    sk = parse_secret_key(secret_key) if isinstance(secret_key, string_types) else secret_key
    existing = json_loads(pkg.container.read(SIGNATURE)) if pkg.signature_state != SIG_ABSENT else None
    doc = chain_append(existing, pkg.manifest_sha256, sk, uri, kind, name or uri, signed_at, role, note)
    blobs = _load_all(pkg)
    cont = pkg.manifest.get("container") or {}
    write_container(out, _container_form(out, form), blobs, pkg.manifest_bytes, json_pretty(doc),
                    cont.get("entry_order") or [], signed_at)
    return out


# ---------------------------------------------------------------------------
# Profile helpers: image/1 and 3d-entity/1
# ---------------------------------------------------------------------------

def png_info(data):
    """(width, height, channels, bit_depth, has_alpha) from a PNG's IHDR."""
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise WerkError("not a PNG (MINI-SPECS section 8)")
    w, h, depth, ctype = struct.unpack(">IIBB", data[16:26])
    channels = {0: 1, 2: 3, 3: 3, 4: 2, 6: 4}.get(ctype)
    if channels is None:
        raise WerkError("PNG colour type %d is not defined" % ctype)
    if ctype == 3:
        depth = 8
    return w, h, channels, depth, ctype in (4, 6)


def glb_info(data):
    """Check the GLB frame (MINI-SPECS section 10.1); return the glTF JSON."""
    if len(data) < 20 or data[:4] != b"glTF":
        raise WerkError("not a GLB (magic glTF)")
    ver, length = struct.unpack("<II", data[4:12])
    if ver != 2 or length != len(data):
        raise WerkError("GLB version %d / length %d does not match %d bytes" % (ver, length, len(data)))
    clen, ctype = struct.unpack("<II", data[12:20])
    if ctype != 0x4E4F534A:
        raise WerkError("the first GLB chunk is not JSON")
    return json_loads(data[20:20 + clen].rstrip(b" \x00"))


def write_image_package(out, png, name, summary=None, uuid=None, created=None,
                        thumbnail_png=None, thumbnail_params=None, recipe=None,
                        disclosure=None, epistemic="authored", model=None, input_files=None,
                        license_text=None, spdx_id=None, producer=None, generator=None,
                        sign_key=None, signer=None, form=None, attachments=None,
                        source_path="image/source.png", color_space="srgb", spec_files=None,
                        conventions_map=None, readme_files=None):
    """Write an `image/1` package around one PNG. Optional: a thumbnail (a
    `core.image.derived`, measured from the source), a recipe and a disclosure
    (objects written as recipe/recipe.json and disclosure/disclosure.json --
    their content is the caller's, and must satisfy their schemas), attached
    extra nodes. Returns the PackageWriter (already written to `out`)."""
    w = PackageWriter("image/1", name, summary=summary, uuid=uuid, created=created,
                      license_text=license_text, spdx_id=spdx_id, producer=producer,
                      generator=generator, spec_files=spec_files, conventions_map=conventions_map)
    for rp, rd in (readme_files or []):
        w.add_readme_file(rp, rd)
    wd, ht, ch, depth, alpha = png_info(png)
    meta = OrderedDict([("width", wd), ("height", ht), ("channels", ch), ("bit_depth", depth),
                        ("color_space", color_space), ("encoding", "png"), ("has_alpha", alpha)])
    prod = None
    if model:
        prod = OrderedDict([("tool", (producer or w.producer)["tool"]),
                            ("version", (producer or w.producer)["version"]), ("model", model)])
    if epistemic != "authored" and not input_files:
        raise WerkError("an inferred image names its inputs: pass input_files")
    if recipe is not None:
        w.add_node("recipe", "core.recipe",
                   [w.file("recipe/recipe.json", json_pretty(recipe), "application/json", "record")],
                   note="The reproduction record of the generation (SPEC section 3.11).")
        w.preview("recipe/recipe.json")
    w.add_node("image-source", "core.image.source",
               [w.file(source_path, png, "image/png")],
               note="The image as the process that made it delivered it.",
               epistemic=epistemic, producer=prod, meta=meta, input_files=input_files)
    w.set_primary("image", "image-source")
    if thumbnail_png is not None:
        tw, th, tc, td, ta = png_info(thumbnail_png)
        tmeta = OrderedDict([("width", tw), ("height", th), ("channels", tc), ("bit_depth", td),
                             ("color_space", color_space), ("encoding", "png"), ("has_alpha", ta),
                             ("derived_role", "thumbnail"),
                             ("resample", (thumbnail_params or {}).get("resample", "box"))])
        params = thumbnail_params or OrderedDict([("resample", "box"), ("width", tw), ("height", th)])
        w.add_node("image-thumb", "core.image.derived",
                   [w.file("image/thumb.png", thumbnail_png, "image/png")],
                   note="The listing thumbnail, a downscale of the source image.",
                   epistemic="measured", meta=tmeta, input_files=[source_path], input_params=params,
                   edges=[{"to": "image-source", "kind": "requires", "role": "derived-from"}])
        w.set_primary("thumbnail", "image-thumb")
        w.preview("image/thumb.png")
    if disclosure is not None:
        w.add_node("disclosure", "core.disclosure",
                   [w.file("disclosure/disclosure.json", json_pretty(disclosure), "application/json")],
                   note="The machine-readable synthetic-content facts (SPEC section 3.12).")
    _attach(w, attachments)
    if sign_key is not None:
        sg = signer or {}
        w.sign(sign_key, sg.get("uri", "urn:werk:anonymous"), sg.get("kind", "human"),
               sg.get("name"), sg.get("role", "author"), sg.get("note"), sg.get("signed_at"))
    w.write(out, _container_form(out, form))
    return w


def _attach(w, attachments):
    """attachments: [{node_id, type, files: [(path, bytes, media_type?, role?)], note?, meta?}]"""
    for a in attachments or []:
        files = [w.file(*f) for f in a["files"]]
        w.add_node(a["node_id"], a["type"], files,
                   note=a.get("note") or "A file attached by the writing application.",
                   meta=a.get("meta"))


def default_material(material_id, name, base_color_texture=None):
    m = OrderedDict([("material_id", material_id), ("name", name), ("model", "metallic-roughness"),
                     ("base_color_factor", [1, 1, 1, 1]), ("metallic_factor", 0),
                     ("roughness_factor", 1), ("alpha_mode", "opaque"), ("double_sided", False)])
    if base_color_texture:
        m["textures"] = OrderedDict([("base_color", OrderedDict([
            ("node", base_color_texture[0]), ("path", base_color_texture[1]), ("uv_set", 0)]))])
    m["epistemic"] = "authored"
    return m


def write_mesh_package(out, glb, name, summary=None, uuid=None, created=None, textures=None,
                       materials=None, preview_png=None, license_text=None, spdx_id=None,
                       producer=None, generator=None, sign_key=None, signer=None, form=None,
                       attachments=None, part_name="Body", spec_files=None,
                       conventions_map=None, readme_files=None):
    """Write a minimal valid `3d-entity/1` package: one part, a `core.geom.game`
    GLB, optional `core.tex` textures and `core.material` JSON payloads, and an
    optional preview still (a `core.tex` with usage `other`, named by
    primary.image).

    textures: [{"id", "png", "usage"="base-color", "color_space"="srgb",
                "normal_convention"?}] -> nodes `tex-<id>`, files textures/<id>.png
    materials: [{"id", "name", "base_color"?: <texture id>, "class"?,
                 "payload"?: a complete core.material object}]
               -> nodes `mat-<id>`, files materials/<id>.json"""
    w = PackageWriter("3d-entity/1", name, summary=summary, uuid=uuid, created=created,
                      license_text=license_text, spdx_id=spdx_id, producer=producer,
                      generator=generator, spec_files=spec_files, conventions_map=conventions_map)
    for rp, rd in (readme_files or []):
        w.add_readme_file(rp, rd)
    glb_info(glb)
    w.add_part("body", part_name)
    w.add_node("geom-game", "core.geom.game", [w.file("geometry/game.glb", glb, "model/gltf-binary")],
               note="The mesh to render, as the authoring application exported it.", part_id="body")
    w.set_primary("mesh", "geom-game")
    w.set_primary("geometry", "geom-game")
    tex_ids = {}
    for t in textures or []:
        tid = t["id"]
        check_id(tid, "texture id")
        wd, ht, ch, depth, _a = png_info(t["png"])
        usage = t.get("usage", "base-color")
        meta = OrderedDict([("color_space", t.get("color_space", "srgb" if usage in ("base-color", "emissive") else "linear")),
                            ("usage", usage), ("width", wd), ("height", ht), ("channels", ch),
                            ("bit_depth", depth)])
        if usage == "normal":
            meta["normal_convention"] = t.get("normal_convention", "opengl-y-up")
        path = "textures/%s.png" % tid
        w.add_node("tex-" + tid, "core.tex", [w.file(path, t["png"], "image/png")],
                   note=t.get("note") or "A texture of the mesh, as exported.", meta=meta, part_id="body")
        tex_ids[tid] = ("tex-" + tid, path)
    for mt in materials or []:
        mid = mt["id"]
        check_id(mid, "material id")
        w.add_material(mid, mt.get("name", mid), "body", mt.get("class"))
        payload = mt.get("payload") or default_material(
            mid, mt.get("name", mid), tex_ids.get(mt.get("base_color")) if mt.get("base_color") else None)
        edges = []
        if mt.get("base_color"):
            edges.append({"to": tex_ids[mt["base_color"]][0], "kind": "enhances", "role": "base-color"})
        w.add_node("mat-" + mid, "core.material",
                   [w.file("materials/%s.json" % mid, json_pretty(payload), "application/json")],
                   note=mt.get("note") or "Material parameters of the mesh, as exported.",
                   material_id=mid, part_id="body", edges=edges)
    if preview_png is not None:
        wd, ht, ch, depth, _a = png_info(preview_png)
        w.add_node("preview", "core.tex", [w.file("preview/preview.png", preview_png, "image/png")],
                   note="A still of the entity for listings, rendered by the authoring application.",
                   meta=OrderedDict([("color_space", "srgb"), ("usage", "other"), ("width", wd),
                                     ("height", ht), ("channels", ch), ("bit_depth", depth)]))
        w.set_primary("image", "preview")
        w.preview("preview/preview.png")
    _attach(w, attachments)
    if sign_key is not None:
        sg = signer or {}
        w.sign(sign_key, sg.get("uri", "urn:werk:anonymous"), sg.get("kind", "human"),
               sg.get("name"), sg.get("role", "author"), sg.get("note"), sg.get("signed_at"))
    w.write(out, _container_form(out, form))
    return w


# ---------------------------------------------------------------------------
# CLI: python -m werk {info,verify,extract,cat,pack-image,pack-mesh,append,sign}
# ---------------------------------------------------------------------------

USAGE = """werk %s -- read and write werk packages (Python, standard library only)

  werk info    <pkg>                         graph, census, report
  werk verify  <pkg> [--json] [--strict]     exit 0 clean, 1 error entries, 2 refused
  werk extract <pkg> <out-dir> [--node ID ...] [--all-versions]
  werk cat     <pkg> <path>|--payload <node> [--version N]   bytes to stdout
  werk pack-image <out> --png F --name N [--summary S] [--uuid U] [--created T]
                  [--thumb F] [--recipe F.json] [--disclosure F.json] [--model M
                  --epistemic inferred --input PATH] [--license F] [--spdx ID]
                  [--attach ID:TYPE:PKGPATH=FILE ...] [--spec-file spec/PATH=FILE ...]
                  [--conventions-map spec/PATH] [--readme-file PKGPATH=FILE ...]
                  [--sign-key HEX --signer-uri U
                  --signer-kind K --signer-name N] [--dir]
  werk pack-mesh  <out> --glb F --name N [--texture ID=F[:usage] ...]
                  [--material ID[:texture-id] ...] [--preview F] (+ the common options)
  werk append  <pkg> <out> --node ID --file PKGPATH=FILE ... --note TEXT
                  [--type T (new node)] [--created T] [--sign-key HEX ...] [--drop-signature]
  werk sign    <pkg> <out> --sign-key HEX --signer-uri U [--signer-kind K]
                  [--signer-name N] [--signed-at T]

Exit status (SPEC.md section 10.2): 0 opened, no error entry; 1 opened with
error entries (or a write that was refused); 2 container refused / bad command line.
""" % LIB_VERSION


def _args(argv, multi=(), flags=()):
    pos, opt = [], OrderedDict()
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            k = a[2:]
            if k in flags:
                opt[k] = True
                i += 1
                continue
            if i + 1 >= len(argv):
                raise SystemExit2("option %s needs a value" % a)
            v = argv[i + 1]
            if k in multi:
                opt.setdefault(k, []).append(v)
            else:
                opt[k] = v
            i += 2
        else:
            pos.append(a)
            i += 1
    return pos, opt


class SystemExit2(Exception):
    pass


def _readf(p):
    with _bopen(p, "rb") as fh:
        return fh.read()


def _stdout_bytes(b):
    out = getattr(sys.stdout, "buffer", sys.stdout)
    out.write(b)
    out.flush()


def _signer(opt):
    if "sign-key" not in opt:
        return None, None
    key = opt["sign-key"]
    if os.path.isfile(key):
        key = _readf(key).decode("ascii").strip()
    sg = {"uri": opt.get("signer-uri", "urn:werk:anonymous"),
          "kind": opt.get("signer-kind", "human"),
          "name": opt.get("signer-name"), "role": opt.get("signer-role", "author"),
          "signed_at": opt.get("signed-at")}
    return key, dict((k, v) for k, v in sg.items() if v is not None)


def _attachments(opt):
    out = []
    for spec in opt.get("attach", []):
        head, _, local = spec.partition("=")
        parts = head.split(":")
        if len(parts) != 3 or not local:
            raise SystemExit2("--attach is ID:TYPE:PKGPATH=FILE")
        out.append({"node_id": parts[0], "type": parts[1], "files": [(parts[2], _readf(local))]})
    return out


def _spec_files(opt):
    out = OrderedDict()
    for spec in opt.get("spec-file", []):
        path, _, local = spec.partition("=")
        if not local:
            raise SystemExit2("--spec-file is PKGPATH=FILE (PKGPATH under spec/)")
        out[path] = _readf(local)
    return out


def _print_report(pkg, out=None):
    out = out or sys.stdout
    for e in pkg.report:
        out.write(u"[%s] %s: %s\n" % (e.severity, e.code, e.message) if not PY2 else
                  ("[%s] %s: %s\n" % (e.severity, e.code, e.message)).encode("utf-8"))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdout, sys.stderr):
        try:  # a console that cannot show a character must not crash the CLI
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    if not argv or argv[0] in ("-h", "--help", "help"):
        sys.stdout.write(USAGE)
        return 0 if argv else EXIT_REFUSED
    cmd, rest = argv[0], argv[1:]
    common_multi = ("attach", "texture", "material", "file", "node", "input", "spec-file",
                    "readme-file")
    try:
        pos, opt = _args(rest, multi=common_multi,
                         flags=("json", "strict", "dir", "all-versions", "drop-signature"))
        if cmd in ("info", "verify", "extract", "cat"):
            if not pos:
                raise SystemExit2("%s needs a package" % cmd)
            try:
                pkg = Package(pos[0])
            except ContainerRefusal as e:
                if cmd == "verify" and "json" in opt:
                    sys.stdout.write(json_pretty(OrderedDict([("exit", 2), ("refusal", e.code)])).decode("utf-8"))
                sys.stderr.write("[error] %s: %s\ncontainer-scoped refusal: nothing was loaded; "
                                 "exit status 2\n" % (e.code, e.message))
                return EXIT_REFUSED
            if cmd == "verify":
                v = pkg.verdict()
                if "strict" in opt:
                    if any(e.severity == "warn" for e in pkg.report):
                        v["exit"] = EXIT_ERRORS
                        v["strict_promoted_warnings"] = True
                if "json" in opt:
                    sys.stdout.write(json_pretty(v).decode("utf-8"))
                else:
                    _print_report(pkg)
                    a, s, d = pkg.census()
                    print("profile    : %s" % pkg.profile)
                    print("signature  : %s" % pkg.signature_state)
                    print("census     : %d nodes: %d alive, %d skipped, %d dead" % (len(pkg.nodes), a, s, d))
                    print("spec_sha256: %s" % ("ok" if v["spec_sha256_ok"] else "MISMATCH"))
                    print("%d error(s), %d report entries" % (len(pkg.errors()), len(pkg.report)))
                    if v.get("strict_promoted_warnings"):
                        print("--strict: warnings promoted to errors")
                return v["exit"]
            if cmd == "info":
                m = pkg.manifest
                print("entity     : %s (%s)" % ((m.get("entity") or {}).get("name"), (m.get("entity") or {}).get("uuid")))
                print("profile    : %s   form: %s   signature: %s" % (pkg.profile, pkg.form, pkg.signature_state))
                for n in pkg.nodes:
                    pp = ""
                    if n.resolved is not None:
                        try:
                            pp = payload_path(n)
                        except WerkError:
                            pp = "(payload ambiguous)"
                    print("  %-18s %-22s v%-3s %-8s %s" % (n.node_id, n.type,
                                                           n.resolved if n.resolved else "-", n.status, pp))
                _print_report(pkg)
                return EXIT_ERRORS if pkg.errors() else EXIT_OK
            if cmd == "extract":
                if len(pos) < 2:
                    raise SystemExit2("extract needs <pkg> <out-dir>")
                written = pkg.extract(pos[1], opt.get("node"), "all-versions" in opt)
                print("%d file(s) written under %s" % (len(written), pos[1]))
                return EXIT_ERRORS if pkg.errors() else EXIT_OK
            if cmd == "cat":
                if "payload" in opt:
                    ver = int(opt["version"]) if "version" in opt else None
                    _stdout_bytes(pkg.read_payload(opt["payload"], ver))
                elif len(pos) >= 2:
                    _stdout_bytes(pkg.read_file(pos[1]))
                else:
                    raise SystemExit2("cat needs a path or --payload NODE")
                return EXIT_OK
        if cmd in ("pack-image", "pack-mesh"):
            if not pos or "name" not in opt:
                raise SystemExit2("%s needs <out> and --name" % cmd)
            out = pos[0]
            form = "directory" if "dir" in opt else _container_form(out, None)
            key, signer = _signer(opt)
            common = dict(name=opt["name"], summary=opt.get("summary"), uuid=opt.get("uuid"),
                          created=opt.get("created"),
                          license_text=_readf(opt["license"]).decode("utf-8") if "license" in opt else None,
                          spdx_id=opt.get("spdx"), sign_key=key, signer=signer, form=form,
                          attachments=_attachments(opt), spec_files=_spec_files(opt),
                          conventions_map=opt.get("conventions-map"),
                          readme_files=[(p.partition("=")[0], _readf(p.partition("=")[2]))
                                        for p in opt.get("readme-file", [])])
            if cmd == "pack-image":
                if "png" not in opt:
                    raise SystemExit2("pack-image needs --png")
                write_image_package(out, _readf(opt["png"]),
                                    thumbnail_png=_readf(opt["thumb"]) if "thumb" in opt else None,
                                    recipe=json_loads(_readf(opt["recipe"])) if "recipe" in opt else None,
                                    disclosure=json_loads(_readf(opt["disclosure"])) if "disclosure" in opt else None,
                                    model=opt.get("model"), epistemic=opt.get("epistemic", "authored"),
                                    input_files=opt.get("input"), **common)
            else:
                if "glb" not in opt:
                    raise SystemExit2("pack-mesh needs --glb")
                textures = []
                for spec in opt.get("texture", []):
                    tid, _, rest2 = spec.partition("=")
                    fpath, usage = rest2, "base-color"
                    if ":" in rest2 and not os.path.exists(rest2):
                        fpath, _, usage = rest2.rpartition(":")
                    textures.append({"id": tid, "png": _readf(fpath), "usage": usage})
                materials = []
                for spec in opt.get("material", []):
                    mid, _, tex = spec.partition(":")
                    materials.append({"id": mid, "name": mid, "base_color": tex or None})
                write_mesh_package(out, _readf(opt["glb"]), textures=textures, materials=materials,
                                   preview_png=_readf(opt["preview"]) if "preview" in opt else None,
                                   **common)
            print("wrote %s" % out)
            return EXIT_OK
        if cmd == "append":
            if len(pos) < 2 or "node" not in opt or "note" not in opt or "file" not in opt:
                raise SystemExit2("append needs <pkg> <out> --node ID --file PKGPATH=FILE --note TEXT")
            files = []
            for spec in opt["file"]:
                p, _, local = spec.partition("=")
                files.append(PackageWriter.file(p, _readf(local)))
            key, signer = _signer(opt)
            append_version(pos[0], pos[1], opt["node"][0], files, opt["note"],
                           epistemic=opt.get("epistemic", "authored"), created=opt.get("created"),
                           node_type=opt.get("type"), sign_key=key, signer=signer,
                           drop_signature="drop-signature" in opt,
                           form="directory" if "dir" in opt else None)
            print("wrote %s" % pos[1])
            return EXIT_OK
        if cmd == "sign":
            key, signer = _signer(opt)
            if len(pos) < 2 or key is None:
                raise SystemExit2("sign needs <pkg> <out> --sign-key HEX")
            sign_package(pos[0], pos[1], key, signer["uri"], signer["kind"], signer.get("name"),
                         signer["role"], None, opt.get("signed-at"),
                         "directory" if "dir" in opt else None)
            print("wrote %s" % pos[1])
            return EXIT_OK
        raise SystemExit2("unknown command %r" % cmd)
    except SystemExit2 as e:
        sys.stderr.write("werk: %s\n\n%s" % (e, USAGE))
        return EXIT_REFUSED
    except ContainerRefusal as e:
        sys.stderr.write("[error] %s: %s\n" % (e.code, e.message))
        return EXIT_REFUSED
    except WerkError as e:
        sys.stderr.write("werk: %s\n" % e)
        return EXIT_ERRORS
