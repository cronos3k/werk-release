"""werk_open.py - an independent reader for a werk 3D-entity package.

Written only from the documentation inside the package (spec/README.md,
spec/SPEC.md, spec/MINI-SPECS.md, spec/layouts/*). It does not import,
run or port the loaders/ bundled in the package.

Usage:
    python -I werk_open.py PACKAGE.werk [OUT_DIR]

It opens the container, lists the node graph with meanings, verifies every
declared hash (files, input_hash, license, spec_sha256, signature chain),
parses the payloads it understands, and extracts primary.mesh and
primary.sound to OUT_DIR. Exit status follows SPEC.md section 10.2:
0 = no error entries, 1 = at least one error entry, 2 = container refused.
"""
import hashlib
import json
import math
import os
import struct
import sys

# ---------------------------------------------------------------- report

REPORT = []


def rep(code, sev, subject, msg):
    REPORT.append((sev, code, subject, msg))


def out(s=''):
    sys.stdout.write(s + '\n')


class ContainerRefused(Exception):
    pass


# ---------------------------------------------------------------- CRC-32 (MINI-SPECS 6)

def _crc_table():
    t = []
    for n in range(256):
        c = n
        for _ in range(8):
            c = (c >> 1) ^ (0xEDB88320 if c & 1 else 0)
        t.append(c)
    return t


_CRC = _crc_table()


def crc32(data):
    c = 0xFFFFFFFF
    for b in data:
        c = _CRC[(c ^ b) & 0xFF] ^ (c >> 8)
    return c ^ 0xFFFFFFFF


# ---------------------------------------------------------------- zip (MINI-SPECS 5)

def open_zip(buf):
    """Return {name: entry dict}. Store mode only; zip64 recognised and refused."""
    n = len(buf)
    if n < 22:
        raise ContainerRefused('file shorter than an EOCD record')
    eocd = -1
    lowest = max(0, n - 22 - 65535)
    for off in range(n - 22, lowest - 1, -1):
        if buf[off:off + 4] == b'PK\x05\x06':
            clen = struct.unpack_from('<H', buf, off + 20)[0]
            if off + 22 + clen == n:
                eocd = off
                break
    if eocd < 0:
        raise ContainerRefused('no EOCD record found')
    (_, disk, cd_disk, cnt_disk, cnt, cd_size, cd_off, _clen) = struct.unpack_from('<IHHHHIIH', buf, eocd)
    if (cnt_disk == 0xFFFF or cnt == 0xFFFF or cd_size == 0xFFFFFFFF or cd_off == 0xFFFFFFFF
            or (eocd >= 20 and buf[eocd - 20:eocd - 16] == b'PK\x06\x07')):
        rep('zip64-unsupported', 'error', '(container)', 'zip64 container; this reader is zip32-only')
        raise ContainerRefused('zip64')
    if disk != 0 or cd_disk != 0 or cnt_disk != cnt:
        raise ContainerRefused('multi-disk zip')
    entries = {}
    p = cd_off
    for _ in range(cnt):
        if buf[p:p + 4] != b'PK\x01\x02':
            raise ContainerRefused('bad central directory signature at %d' % p)
        (flags, method, crc, csize, usize, nlen, mlen, klen, lho) = (
            struct.unpack_from('<H', buf, p + 8)[0], struct.unpack_from('<H', buf, p + 10)[0],
            struct.unpack_from('<I', buf, p + 16)[0], struct.unpack_from('<I', buf, p + 20)[0],
            struct.unpack_from('<I', buf, p + 24)[0], struct.unpack_from('<H', buf, p + 28)[0],
            struct.unpack_from('<H', buf, p + 30)[0], struct.unpack_from('<H', buf, p + 32)[0],
            struct.unpack_from('<I', buf, p + 42)[0])
        name = buf[p + 46:p + 46 + nlen].decode('utf-8')
        p += 46 + nlen + mlen + klen
        if 0xFFFFFFFF in (csize, usize, lho):
            rep('zip64-unsupported', 'error', name, 'zip64 entry sentinel')
            raise ContainerRefused('zip64 entry')
        if name in entries:
            raise ContainerRefused('duplicate zip entry name %r' % name)
        bad_name = (name.startswith('/') or '\\' in name or ':' in name
                    or '..' in name.split('/'))
        if bad_name:
            rep('zip-name-illegal', 'error', name, 'name breaks MINI-SPECS 5.4 rules')
        if flags & 0x8:
            rep('zip-data-descriptor', 'warn', name, 'flag bit 3 set (MINI-SPECS 5.4 forbids it for writers)')
        if buf[lho:lho + 4] != b'PK\x03\x04':
            raise ContainerRefused('bad local header for %r' % name)
        ln, lm = struct.unpack_from('<HH', buf, lho + 26)
        start = lho + 30 + ln + lm
        e = dict(name=name, method=method, crc=crc, csize=csize, usize=usize,
                 lho=lho, start=start, unsupported=False)
        if method != 0:
            e['unsupported'] = True
            rep('zip-method-unsupported', 'error', name,
                'compression method %d; this reader supports store (0) only' % method)
        elif csize != usize:
            rep('zip-size-mismatch', 'error', name, 'stored entry with csize != usize')
        elif start + csize > n:
            rep('zip-truncated', 'error', name, 'entry data runs past end of file')
            e['unsupported'] = True
        entries[name] = e
    return entries


def entry_bytes(buf, e):
    if e['unsupported']:
        return None
    return bytes(buf[e['start']:e['start'] + e['csize']])


# ---------------------------------------------------------------- strict JSON (MINI-SPECS 3)

def _no_dups(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError('duplicate JSON key %r' % k)
        d[k] = v
    return d


def _no_const(x):
    raise ValueError('non-finite JSON number %s' % x)


def strict_json(data):
    if data.startswith(b'\xef\xbb\xbf'):
        raise ValueError('UTF-8 BOM present (MINI-SPECS 2 says reject)')
    return json.loads(data.decode('utf-8'), object_pairs_hook=_no_dups, parse_constant=_no_const)


def canonical_json(v):
    """MINI-SPECS 3, 'Canonical JSON (for hashing only)'."""
    if v is None:
        return 'null'
    if v is True:
        return 'true'
    if v is False:
        return 'false'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v.is_integer() and abs(v) < 2 ** 53:
            return str(int(v))
        return repr(v)
    if isinstance(v, str):
        o = ['"']
        short = {'"': '\\"', '\\': '\\\\', '\b': '\\b', '\f': '\\f', '\n': '\\n', '\r': '\\r', '\t': '\\t'}
        for ch in v:
            if ch in short:
                o.append(short[ch])
            elif ord(ch) < 0x20:
                o.append('\\u%04x' % ord(ch))
            else:
                o.append(ch)
        o.append('"')
        return ''.join(o)
    if isinstance(v, list):
        return '[' + ','.join(canonical_json(x) for x in v) + ']'
    if isinstance(v, dict):
        keys = sorted(v.keys(), key=lambda k: k.encode('utf-8'))
        return '{' + ','.join(canonical_json(k) + ':' + canonical_json(v[k]) for k in keys) + '}'
    raise TypeError(type(v))


# ---------------------------------------------------------------- Ed25519 verify (MINI-SPECS 12)

P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493


def _inv(a):
    return pow(a, P - 2, P)


D = (-121665 * _inv(121666)) % P
I = pow(2, (P - 1) // 4, P)


def _decompress(b):
    if len(b) != 32:
        return None
    y = int.from_bytes(b, 'little')
    sign = y >> 255
    y &= (1 << 255) - 1
    if y >= P:
        return None
    u = (y * y - 1) % P
    v = (D * y * y + 1) % P
    x = (u * pow(v, 3, P) * pow(u * pow(v, 7, P), (P - 5) // 8, P)) % P
    if (v * x * x - (-u)) % P == 0:
        x = (x * I) % P
    if (v * x * x - u) % P != 0:
        return None
    if x == 0 and sign == 1:
        return None
    if (x & 1) != sign:
        x = P - x
    return (x, y, 1, (x * y) % P)


def _add(p1, p2):
    X1, Y1, Z1, T1 = p1
    X2, Y2, Z2, T2 = p2
    A = (Y1 - X1) * (Y2 - X2) % P
    B = (Y1 + X1) * (Y2 + X2) % P
    C = T1 * 2 * D * T2 % P
    Dd = Z1 * 2 * Z2 % P
    E, F, G, H = B - A, Dd - C, Dd + C, B + A
    return (E * F % P, G * H % P, F * G % P, E * H % P)


def _mul(s, pt):
    q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            q = _add(q, pt)
        pt = _add(pt, pt)
        s >>= 1
    return q


def _eq(p1, p2):
    X1, Y1, Z1, _ = p1
    X2, Y2, Z2, _ = p2
    return (X1 * Z2 - X2 * Z1) % P == 0 and (Y1 * Z2 - Y2 * Z1) % P == 0


_By = 4 * _inv(5) % P
BASE = _decompress(_By.to_bytes(32, 'little'))  # sign bit 0 => even x


def ed25519_verify(pub, msg, sig):
    if len(sig) != 64:
        return False
    A = _decompress(pub)
    R = _decompress(sig[:32])
    if A is None or R is None:
        return False
    S = int.from_bytes(sig[32:], 'little')
    if S >= L:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), 'little') % L
    lhs = _mul(8, _mul(S, BASE))
    rhs = _mul(8, _add(R, _mul(k, A)))
    return _eq(lhs, rhs)


def ed25519_selftest():
    """RFC 8032 vector 1, as printed in MINI-SPECS 12."""
    pub = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
    sig = bytes.fromhex('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b')
    good = ed25519_verify(pub, b'', sig)
    bad = ed25519_verify(pub, b'x', sig)
    return good and not bad


def sig_message(entry):
    return '\n'.join(['werk-sig/1', entry['manifest_sha256'], entry['prev_entry_sha256'],
                      entry['signed_at'], entry['signer']['uri'], entry['signer']['kind']]).encode('utf-8')


def message_selftest():
    """The 203-byte checkpoint in MINI-SPECS 12.1."""
    e = {'manifest_sha256': 'c421d2e85a9455f0be794ca8ee673f727a7ef67485d631e374f95c4a6d6ce61a',
         'prev_entry_sha256': '0' * 64, 'signed_at': '2026-08-08T09:00:00Z',
         'signer': {'uri': 'urn:werk:fixture:rfc8032-vector-1', 'kind': 'service'}}
    m = sig_message(e)
    return len(m) == 203 and hashlib.sha256(m).hexdigest() == \
        '11e260cc16bc454f39f1aa6d56679c868ba1e83d33e3c22a462040b32a92165a'


# ---------------------------------------------------------------- MessagePack subset (ENVELOPE 4)

class MPError(Exception):
    pass


def mp_decode(b, i=0):
    if i >= len(b):
        raise MPError('truncated')
    t = b[i]
    i += 1

    def take(k):
        nonlocal i
        if i + k > len(b):
            raise MPError('truncated')
        r = b[i:i + k]
        i += k
        return r

    if t <= 0x7f:
        return t, i
    if t >= 0xe0:
        return t - 256, i
    if 0xa0 <= t <= 0xbf:
        return take(t & 0x1f).decode('utf-8'), i
    if 0x90 <= t <= 0x9f:
        return _mp_arr(b, i, t & 0x0f)
    if 0x80 <= t <= 0x8f:
        return _mp_map(b, i, t & 0x0f)
    simple = {0xc0: None, 0xc2: False, 0xc3: True}
    if t in simple:
        return simple[t], i
    ints = {0xcc: '>B', 0xcd: '>H', 0xce: '>I', 0xcf: '>Q', 0xd0: '>b', 0xd1: '>h', 0xd2: '>i', 0xd3: '>q',
            0xca: '>f', 0xcb: '>d'}
    if t in ints:
        f = ints[t]
        return struct.unpack(f, take(struct.calcsize(f)))[0], i
    lens = {0xd9: '>B', 0xda: '>H', 0xdb: '>I'}
    if t in lens:
        n = struct.unpack(lens[t], take(struct.calcsize(lens[t])))[0]
        return take(n).decode('utf-8'), i
    blens = {0xc4: '>B', 0xc5: '>H', 0xc6: '>I'}
    if t in blens:
        n = struct.unpack(blens[t], take(struct.calcsize(blens[t])))[0]
        return bytes(take(n)), i
    if t in (0xdc, 0xdd):
        n = struct.unpack('>H' if t == 0xdc else '>I', take(2 if t == 0xdc else 4))[0]
        return _mp_arr(b, i, n)
    if t in (0xde, 0xdf):
        n = struct.unpack('>H' if t == 0xde else '>I', take(2 if t == 0xde else 4))[0]
        return _mp_map(b, i, n)
    raise MPError('banned or unknown format byte 0x%02x' % t)


def _mp_arr(b, i, n):
    out_ = []
    for _ in range(n):
        v, i = mp_decode(b, i)
        out_.append(v)
    return out_, i


def _mp_map(b, i, n):
    d = {}
    for _ in range(n):
        k, i = mp_decode(b, i)
        v, i = mp_decode(b, i)
        if k in d:
            raise MPError('duplicate map key %r' % (k,))
        d[k] = v
    return d, i


# ---------------------------------------------------------------- envelope (ENVELOPE 1-7)

MAGICS = {b'WKFF': 'core.field.flow', b'WKRP': 'core.pose.rest', b'WKAC': 'core.anim.clip',
          b'WKSK': 'core.skeleton', b'WKEM': 'core.embedding', b'WKPC': 'core.geom.points',
          b'WKGS': 'core.geom.gsplat'}
DTYPES = {'u8': 1, 'i8': 1, 'u16': 2, 'i16': 2, 'u32': 4, 'i32': 4, 'u64': 8, 'i64': 8, 'f32': 4, 'f64': 8}


def read_envelope(buf):
    """Return (magic, version, header). Raise ValueError naming the failed check."""
    if len(buf) < 12:
        raise ValueError('shorter than 12 bytes')
    magic = bytes(buf[0:4])
    version, hlen = struct.unpack_from('<II', buf, 4)
    if hlen < 1 or 12 + hlen > len(buf):
        raise ValueError('header_len %d does not fit' % hlen)
    try:
        hdr, used = mp_decode(buf[12:12 + hlen])
    except (MPError, UnicodeDecodeError) as ex:
        raise ValueError('header MessagePack: %s' % ex)
    if used != hlen:
        raise ValueError('header map ends at %d, header_len says %d' % (used, hlen))
    if not isinstance(hdr, dict):
        raise ValueError('header is not a map')
    for k in ('kind', 'endianness', 'payload_origin', 'payload_size', 'sections'):
        if k not in hdr:
            raise ValueError('mandatory header key %r missing' % k)
    if magic in MAGICS and hdr['kind'] != MAGICS[magic]:
        raise ValueError('kind %r does not match magic %r' % (hdr['kind'], magic))
    if hdr['endianness'] != 'le':
        raise ValueError('endianness %r' % hdr['endianness'])
    p = 16 * math.ceil((12 + hlen) / 16)
    if hdr['payload_origin'] != p:
        raise ValueError('payload_origin %r != computed %d' % (hdr['payload_origin'], p))
    if p + hdr['payload_size'] != len(buf):
        raise ValueError('payload_origin + payload_size != file size')
    prev_end = p
    for idx, s in enumerate(hdr['sections']):
        for k in ('name', 'offset', 'size', 'dtype', 'shape', 'stride'):
            if k not in s:
                raise ValueError('section %d lacks %r' % (idx, k))
        off, size, stride, shape = s['offset'], s['size'], s['stride'], s['shape']
        if idx == 0 and off != p:
            raise ValueError('section 0 does not start at payload_origin')
        if off % 16:
            raise ValueError('section %r offset not 16-aligned' % s['name'])
        if off < prev_end or off - prev_end > 15:
            raise ValueError('section %r gap/overlap/out of order' % s['name'])
        if any(buf[prev_end:off]):
            rep('envelope-padding-nonzero', 'warn', s['name'], 'nonzero padding between sections')
        if off + size > len(buf):
            raise ValueError('section %r runs past end of file' % s['name'])
        esz = DTYPES.get(s['dtype'], stride if s['dtype'] == 'record' else None)
        if esz is None:
            raise ValueError('section %r unknown dtype %r' % (s['name'], s['dtype']))
        if stride == esz:
            if size != stride * math.prod(shape):
                raise ValueError('section %r size rule (first branch)' % s['name'])
        else:
            if not shape or stride < esz * shape[-1] or size != stride * math.prod(shape[:-1]):
                raise ValueError('section %r size rule (second branch)' % s['name'])
        prev_end = off + size
    if 16 * math.ceil(prev_end / 16) != p + hdr['payload_size']:
        raise ValueError('trailing data after last section')
    return magic, version, hdr


def decode_wkrp(buf, hdr):
    secs = {s['name']: s for s in hdr['sections']}
    poses, contacts = secs['poses'], secs['contacts']
    n = hdr['pose_count']
    rows = []
    total_c = 0
    for k in range(n):
        o = poses['offset'] + k * poses['stride']
        w, x, y, z, cf, cc, prob, area = struct.unpack_from('<4f2I2f', buf, o)
        rows.append(dict(quat_wxyz=(w, x, y, z), contact_first=cf, contact_count=cc,
                         probability=prob, support_area_m2=area))
        total_c += cc
        for v in (w, x, y, z, prob, area):
            if not math.isfinite(v):
                raise ValueError('non-finite float in pose %d' % k)
        if abs(math.sqrt(w * w + x * x + y * y + z * z) - 1.0) > 1e-6:
            raise ValueError('pose %d quaternion not unit' % k)
    if total_c != hdr['contact_count']:
        raise ValueError('sum of contact_count != header contact_count')
    if any(rows[i]['probability'] < rows[i + 1]['probability'] for i in range(n - 1)):
        raise ValueError('poses not sorted by probability descending')
    if hdr.get('trials', 0) > 0 and abs(sum(r['probability'] for r in rows) - 1.0) > 1e-3:
        raise ValueError('probabilities do not sum to 1 +/- 1e-3')
    pts = [struct.unpack_from('<3f', buf, contacts['offset'] + c * contacts['stride'])
           for c in range(contacts['shape'][0])]
    return rows, pts


# ---------------------------------------------------------------- GLB / WAV / PNG (MINI-SPECS 8-10)

COMP = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}


def parse_glb(b):
    if b[:4] != b'glTF':
        raise ValueError('magic is not glTF')
    ver, total = struct.unpack_from('<II', b, 4)
    if ver != 2:
        raise ValueError('GLB version %d' % ver)
    if total != len(b):
        raise ValueError('GLB length field %d != %d' % (total, len(b)))
    p, js, binc = 12, None, None
    while p < len(b):
        clen, ctype = struct.unpack_from('<II', b, p)
        data = b[p + 8:p + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(data.decode('utf-8'))
        elif ctype == 0x004E4942:
            binc = data
        p += 8 + clen
    if js is None:
        raise ValueError('no JSON chunk')
    return js, binc


def read_accessor(js, binc, idx):
    a = js['accessors'][idx]
    bv = js['bufferViews'][a['bufferView']]
    fmt, sz = COMP[a['componentType']]
    nc = NCOMP[a['type']]
    stride = bv.get('byteStride', sz * nc)
    base = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    return [struct.unpack_from('<%d%s' % (nc, fmt), binc, base + i * stride) for i in range(a['count'])]


def parse_wav(b):
    if b[:4] != b'RIFF' or b[8:12] != b'WAVE':
        raise ValueError('not RIFF/WAVE')
    riff_size = struct.unpack_from('<I', b, 4)[0]
    if riff_size + 8 != len(b):
        rep('wav-riff-size', 'warn', '', 'RIFF size %d + 8 != file size %d' % (riff_size, len(b)))
    p, fmt, data = 12, None, None
    chunks = []
    while p + 8 <= len(b):
        cid = b[p:p + 4].decode('ascii', 'replace')
        size = struct.unpack_from('<I', b, p + 4)[0]
        chunks.append(cid)
        body = b[p + 8:p + 8 + size]
        if cid == 'fmt ':
            af, ch, sr, br, ba, bps = struct.unpack_from('<HHIIHH', body, 0)
            fmt = dict(audio_format=af, channels=ch, sample_rate=sr, byte_rate=br, block_align=ba, bits=bps)
        elif cid == 'data':
            data = body
        p += 8 + size + (size & 1)
    if fmt is None or data is None:
        raise ValueError('missing fmt or data chunk')
    frames = len(data) // fmt['block_align']
    peak = 0
    if fmt['audio_format'] == 1 and fmt['bits'] == 16:
        for (s,) in struct.iter_unpack('<h', data[:len(data) - len(data) % 2]):
            peak = max(peak, abs(s))
    fmt.update(chunks=chunks, frames=frames, seconds=frames / fmt['sample_rate'],
               peak_dbfs=(20 * math.log10(peak / 32768) if peak else None))
    return fmt


def parse_png(b):
    if b[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('bad PNG signature')
    p, ihdr, bad = 8, None, []
    while p < len(b):
        ln = struct.unpack_from('>I', b, p)[0]
        ctype = b[p + 4:p + 8]
        body = b[p + 8:p + 8 + ln]
        crc = struct.unpack_from('>I', b, p + 8 + ln)[0]
        if crc32(ctype + body) != crc:
            bad.append(ctype.decode('ascii', 'replace'))
        if ctype == b'IHDR':
            w, h, depth, ctyp = struct.unpack_from('>IIBB', body, 0)
            ihdr = dict(width=w, height=h, bit_depth=depth, color_type=ctyp,
                        channels={0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctyp))
        p += 12 + ln
        if ctype == b'IEND':
            break
    return ihdr, bad


# ---------------------------------------------------------------- meanings

MEANING = {
    'core.geom.game': 'runtime mesh (GLB) a renderer loads',
    'core.geom.source': 'archival source mesh (GLB)',
    'core.material': 'PBR parameters for one material id (JSON)',
    'core.phys.bounds': 'measured AABB / bounding sphere for culling and placement (JSON)',
    'core.semantics': 'facet tags, palette and search text for a browser listing (JSON)',
    'core.provenance': 'who made what, from what, with which models (JSON)',
    'core.audio.effect': 'one sound effect: WAV takes plus a JSON descriptor',
    'core.audio.package': 'the audio package descriptor (JSON)',
    'core.spec': 'the format specification travelling inside the file',
    'core.loader': 'a bundled single-file reader program (inert data here)',
    'core.license': 'full licence text',
    'core.readme': 'one page for a human',
    'core.pose.rest': 'settled rest orientations from a drop simulation (WKRP envelope)',
}
SUPPORTED_PROFILE = '3d-entity/1'
# SPEC.md section 2: the convention set of profile 3d-entity/1. This reader
# implements exactly these values; anything else is refused per the
# package's own conventions-map.json.
SUPPORTED_CONV = {
    'endianness': 'le', 'units_per_meter': 1.0, 'length_unit': 'metre', 'angle_unit': 'radian',
    'time_unit': 'second', 'mass_unit': 'kilogram', 'up_axis': 'y', 'forward_axis': '-z',
    'right_axis': '+x', 'handedness': 'right', 'winding': 'ccw', 'quat_order': 'wxyz',
    'oct_encoding_pole': 'y', 'sh_l1_order': ['dc', 'y', 'z', 'x'], 'color_space_default': 'srgb',
    'uv_origin': 'top-left', 'alignment_bytes': 16, 'text_encoding': 'utf-8', 'id_case': 'kebab-case',
    'hash_algorithm': 'sha256', 'signature_algorithm': 'ed25519'}


# ---------------------------------------------------------------- main

def resolve_payload(node_type, ver):
    """SPEC.md 2.1, rules 1-5. Never files[0]."""
    files = ver['files']
    paths = [f['path'] for f in files]
    if 'payload_file' in ver:
        if paths.count(ver['payload_file']) != 1:
            return None, 'payload_file %r is not exactly one entry of files[]' % ver['payload_file']
        return ver['payload_file'], 'rule 1 (payload_file)'
    if len(files) == 1:
        return paths[0], 'rule 2 (single file)'
    pl = [f['path'] for f in files if f.get('role') == 'payload']
    if len(pl) == 1:
        return pl[0], 'rule 3 (role payload)'
    role = {'core.audio.effect': 'best', 'core.audio.ambience': 'best', 'core.imposter': 'atlas',
            'core.recipe': 'record'}.get(node_type)
    if role:
        c = [f['path'] for f in files if f.get('role') == role]
        if len(c) == 1:
            return c[0], 'rule 4 (role %s)' % role
    return None, 'payload-file-ambiguous: ' + ', '.join(paths)


def main(argv):
    if len(argv) < 2:
        out(__doc__)
        return 2
    path = argv[1]
    outdir = argv[2] if len(argv) > 2 else 'extracted'
    with open(path, 'rb') as fh:
        buf = fh.read()

    out('=' * 78)
    out('werk package: %s  (%d bytes)' % (path, len(buf)))
    out('=' * 78)

    # 1. container
    try:
        entries = open_zip(buf)
    except ContainerRefused as ex:
        rep('container-refused', 'error', '(container)', str(ex))
        print_report()
        return 2
    data = {}
    for name, e in entries.items():
        b = entry_bytes(buf, e)
        if b is not None:
            data[name] = b
            if crc32(b) != e['crc']:
                rep('zip-crc-mismatch', 'error', name, 'CRC-32 in central directory does not match bytes')
    out('\n[1] container: zip, %d entries, all store-mode: %s' % (
        len(entries), all(e['method'] == 0 for e in entries.values())))

    # 2. manifest
    if 'MANIFEST.json' not in data:
        rep('manifest-missing', 'error', '(container)', 'MANIFEST.json absent')
        print_report()
        return 2
    mbytes = data['MANIFEST.json']
    try:
        man = strict_json(mbytes)
    except ValueError as ex:
        rep('manifest-unparseable', 'error', 'MANIFEST.json', str(ex))
        print_report()
        return 2
    msha = hashlib.sha256(mbytes).hexdigest()
    werk = man.get('werk', {})
    out('[2] manifest: werk %s.%s, profile %s, sha256 %s' % (
        werk.get('major'), werk.get('minor'), man.get('profile'), msha))
    ent = man.get('entity', {})
    out('    entity: %s  (uuid %s)' % (ent.get('name'), ent.get('uuid')))
    if werk.get('major') != 1:
        rep('unsupported-major', 'error', 'MANIFEST.json', 'werk.major %r' % werk.get('major'))
    profile_ok = man.get('profile') == SUPPORTED_PROFILE
    if not profile_ok:
        rep('unsupported-profile', 'warn', 'MANIFEST.json', 'profile %r' % man.get('profile'))

    # 3. conventions, scoped through the package's own map
    refused_types = set()
    cmap = {}
    cmap_path = man.get('conventions_map')
    if cmap_path and cmap_path in data:
        try:
            cmap = strict_json(data[cmap_path]).get('conventions', {})
        except ValueError as ex:
            rep('conventions-map-invalid', 'warn', cmap_path, str(ex))
    conv = man.get('conventions', {})
    if profile_ok:
        for k, want in SUPPORTED_CONV.items():
            got = conv.get(k)
            if got != want:
                gov = cmap.get(k, {}) if isinstance(cmap, dict) else {}
                scope = gov.get('scope', 'node')
                rep('unsupported-convention', 'error', 'conventions.' + k,
                    'value %r, reader supports %r (scope %s)' % (got, want, scope))
                if scope == 'container':
                    print_report()
                    return 2
                refused_types.update(gov.get('governs', []))
    out('[3] conventions: %d values checked, refused node types: %s' % (
        len(SUPPORTED_CONV), sorted(refused_types) or 'none'))

    # 4. signature chain
    sig_state = verify_signature(data, msha)
    out('[4] signature: %s' % sig_state)

    # 5-8. graph walk, hashes
    nodes = man.get('nodes', [])
    by_id = {n['node_id']: n for n in nodes}
    owner = {}
    dead = set()
    active_ver = {}
    for n in nodes:
        nid = n['node_id']
        vers = {v['v']: v for v in n.get('versions', [])}
        ver = vers.get(n.get('active'))
        if ver is None:
            older = sorted(v for v in vers if isinstance(n.get('active'), int) and v < n['active'])
            if older:
                ver = vers[older[-1]]
                rep('active-fallback', 'warn', nid, 'active %r invalid; using v%d' % (n.get('active'), older[-1]))
            else:
                rep('active-invalid', 'error', nid, 'no usable version')
                dead.add(nid)
                continue
        active_ver[nid] = ver
        for v in n.get('versions', []):
            for f in v['files']:
                prev = owner.get(f['path'])
                if prev and prev != nid:
                    rep('file-claimed-twice', 'error', f['path'], 'claimed by %s and %s' % (prev, nid))
                owner[f['path']] = nid
        for f in ver['files']:
            b = data.get(f['path'])
            if b is None:
                rep('file-missing', 'error', nid, '%s declared but not in container' % f['path'])
                dead.add(nid)
                continue
            if len(b) != f['size']:
                rep('size-mismatch', 'error', nid, '%s: %d bytes, declared %d' % (f['path'], len(b), f['size']))
                dead.add(nid)
            h = hashlib.sha256(b).hexdigest()
            if h != f['sha256']:
                rep('hash-mismatch', 'error', nid, '%s: sha256 %s, declared %s' % (f['path'], h, f['sha256']))
                dead.add(nid)
        if n['type'] in refused_types:
            rep('unsupported-convention', 'error', nid, 'node type governed by a refused convention')
            dead.add(nid)

    # floating bytes: every entry except MANIFEST/SIGNATURE must belong to a node
    for name in entries:
        if name in ('MANIFEST.json', 'SIGNATURE.json') or name.endswith('/'):
            continue
        if name not in owner:
            rep('file-floats', 'warn', name, 'container entry not listed by any node (SPEC 2: nothing floats)')

    # input_hash: inputs may live outside this package (they did, in the source build);
    # their sha256 may still be declared somewhere inside it (provenance consumed[]).
    known_sha = {}
    for n in nodes:
        for v in n.get('versions', []):
            for f in v['files']:
                known_sha.setdefault(f['path'], f['sha256'])
    prov_extra = {}
    for n in nodes:
        if n['type'] == 'core.provenance' and n['node_id'] in active_ver:
            for f in active_ver[n['node_id']]['files']:
                try:
                    pj = strict_json(data[f['path']])
                except (KeyError, ValueError):
                    continue
                for run in pj.get('runs', []):
                    for c in run.get('consumed', []):
                        prov_extra.setdefault(c['path'], c['sha256'])
    ih_rows = []
    for n in nodes:
        nid = n['node_id']
        ver = active_ver.get(nid)
        if not ver or 'input_hash' not in ver:
            if ver and ver.get('epistemic') in ('measured', 'inferred'):
                rep('input-hash-missing', 'warn', nid, 'measured/inferred version without input_hash')
            continue
        h = hashlib.sha256()
        src = []
        ok = True
        for ip in ver.get('input_files', []):
            if ip in data:
                h.update(hashlib.sha256(data[ip]).digest())
                src.append('bytes')
            elif ip in prov_extra:
                h.update(bytes.fromhex(prov_extra[ip]))
                src.append('provenance-declared sha256')
            else:
                ok = False
                src.append('ABSENT')
        h.update(canonical_json(ver.get('input_params', {})).encode('utf-8'))
        if not ok:
            missing = [ip for ip, s in zip(ver.get('input_files', []), src) if s == 'ABSENT']
            rep('input-hash-unrecheckable', 'info', nid,
                'input(s) not in package and no sha256 declared for them: %s' % ', '.join(missing))
            ih_rows.append((nid, ver['input_hash'], None, src))
        else:
            got = h.hexdigest()
            ih_rows.append((nid, ver['input_hash'], got, src))
            if got != ver['input_hash']:
                rep('input-hash-mismatch', 'warn', nid, 'computed %s, declared %s (derived data may be stale)'
                    % (got, ver['input_hash']))

    # edges. SPEC 5: a requires edge into a DEAD node kills the source.
    # SPEC says nothing about an edge into a node that is not in the package at
    # all (this reduced fixture has several). This reader keeps such a source
    # alive, with verified bytes, and reports it as degraded (warn).
    changed = True
    while changed:
        changed = False
        for n in nodes:
            for e in n.get('edges', []):
                if n['node_id'] not in dead and e['kind'] == 'requires' and e['to'] in dead:
                    dead.add(n['node_id'])
                    changed = True
                    rep('requires-unsatisfied', 'error', n['node_id'],
                        'requires %s (%s), which is dead' % (e['to'], e.get('role')))
    degraded = set()
    for n in nodes:
        for e in n.get('edges', []):
            if e['kind'] == 'requires' and e['to'] not in by_id:
                degraded.add(n['node_id'])
                rep('requires-target-absent', 'warn', n['node_id'],
                    'requires %s (%s), which is not in this package; bytes verified, node kept as degraded'
                    % (e['to'], e.get('role')))
            elif e['kind'] == 'enhances' and e['to'] not in by_id:
                rep('edge-target-absent', 'info', n['node_id'],
                    'enhances %s (%s), which is not in this package: that one feature is lost' % (e['to'], e.get('role')))

    # license / spec_sha256
    lic = man.get('license', {})
    if lic.get('file') in data:
        lh = hashlib.sha256(data[lic['file']]).hexdigest()
        if lh != lic.get('sha256'):
            rep('hash-mismatch', 'error', 'license', 'LICENSE sha256 %s != %s' % (lh, lic.get('sha256')))
    spec_files = sorted({p for p in known_sha if p.startswith('spec/')}, key=lambda s: s.encode('utf-8'))
    sh = hashlib.sha256()
    for p_ in spec_files:
        sh.update(p_.encode('utf-8') + b'\n' + bytes.fromhex(known_sha[p_]) + b'\n')
    spec_got = sh.hexdigest()
    if spec_got != man.get('spec_sha256'):
        rep('spec-sha256-mismatch', 'error', 'MANIFEST.json', 'computed %s, declared %s' % (spec_got, man.get('spec_sha256')))
    if 'total_size_bytes' in man.get('container', {}):
        tot = sum(f['size'] for f in {f['path']: f for n in nodes for v in n['versions'] for f in v['files']}.values())
        if tot != man['container']['total_size_bytes']:
            rep('total-size-differs', 'info', 'MANIFEST.json', 'computed %d' % tot)

    # payload dispatch
    details = {}
    for n in nodes:
        nid = n['node_id']
        if nid in dead or nid not in active_ver:
            continue
        details[nid] = inspect_node(n, active_ver[nid], data, man)

    # -------- listing
    out('\n[5] node graph (%d nodes)' % len(nodes))
    out('-' * 78)
    for n in nodes:
        nid = n['node_id']
        ver = active_ver.get(nid)
        state = 'DEAD' if nid in dead else ('degraded' if nid in degraded else 'ok')
        out('%-34s %-24s [%s]' % (nid, n['type'], state))
        out('    meaning : %s' % (MEANING.get(n['type']) or
                                 ('extension node (x.*): skipped, files hashed only' if n['type'].startswith('x.')
                                  else 'unknown type: skipped')))
        if ver:
            out('    active  : v%s  epistemic=%s  producer=%s %s%s' % (
                ver['v'], ver.get('epistemic'), ver['producer'].get('tool'), ver['producer'].get('version'),
                (' model=' + ver['producer']['model']) if 'model' in ver['producer'] else ''))
            out('    note    : %s' % ver.get('note', '')[:150])
            for f in ver['files']:
                out('    file    : %-46s %7d B  %s' % (f['path'], f['size'], f.get('role', '')))
        for e in n.get('edges', []):
            mark = '' if e['to'] in by_id else '   <- target not in package'
            out('    edge    : %s -> %s (%s)%s' % (e['kind'], e['to'], e.get('role'), mark))
        for line in details.get(nid, []):
            out('    detail  : %s' % line)

    out('\n[6] input_hash checks')
    for nid, decl, got, src in ih_rows:
        verdict = 'NOT RECHECKABLE' if got is None else ('match' if got == decl else 'MISMATCH')
        out('    %-34s %s  (inputs from: %s)' % (nid, verdict, ', '.join(src)))
    out('    spec_sha256: %s' % ('match' if spec_got == man.get('spec_sha256') else 'MISMATCH'))
    out('    license.sha256: %s' % ('match' if lic.get('file') in data and
                                     hashlib.sha256(data[lic['file']]).hexdigest() == lic.get('sha256') else 'MISMATCH'))

    # extraction
    out('\n[7] extraction to %s' % outdir)
    prim = man.get('primary', {})
    for slot, fallback_type in (('mesh', 'core.geom.game'), ('sound', 'core.audio.effect')):
        nid = prim.get(slot)
        if nid is None:
            cands = [n['node_id'] for n in nodes if n['type'] == fallback_type]
            nid = cands[0] if cands else None
            rep('primary-fallback', 'warn', slot, 'primary.%s absent; fell back to %s' % (slot, nid))
        if nid is None or nid not in active_ver or nid in dead:
            rep('extract-failed', 'error', slot, 'node %r unavailable' % nid)
            continue
        ver = active_ver[nid]
        p_, how = resolve_payload(by_id[nid]['type'], ver)
        if p_ is None:
            rep('payload-file-ambiguous', 'warn', nid, how)
            continue
        decl = next(f['sha256'] for f in ver['files'] if f['path'] == p_)
        dst = os.path.join(outdir, *p_.split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as fh:
            fh.write(data[p_])
        with open(dst, 'rb') as fh:
            got = hashlib.sha256(fh.read()).hexdigest()
        out('    primary.%-5s -> node %s -> %s  [%s]' % (slot, nid, p_, how))
        out('        written : %s' % dst)
        out('        declared: %s' % decl)
        out('        on disk : %s  %s' % (got, 'MATCH' if got == decl else 'MISMATCH'))
        if got != decl:
            rep('extract-hash-mismatch', 'error', p_, 'written bytes do not hash to the declared value')

    return print_report()


def verify_signature(data, msha):
    if 'SIGNATURE.json' not in data:
        rep('signature-absent', 'info', 'SIGNATURE.json', 'no signature chain')
        return 'absent'
    if not (ed25519_selftest() and message_selftest()):
        rep('signature-unverified', 'warn', 'SIGNATURE.json', 'Ed25519 or message self-test failed')
        return 'unverified'
    try:
        sj = strict_json(data['SIGNATURE.json'])
        chain = sj['chain']
        if sj.get('algorithm') != 'ed25519' or sj.get('encoding') != 'hex-lowercase':
            rep('signature-unverified', 'warn', 'SIGNATURE.json', 'algorithm/encoding not supported')
            return 'unverified'
    except (ValueError, KeyError) as ex:
        rep('signature-invalid', 'error', 'SIGNATURE.json', 'unparseable: %s' % ex)
        return 'present-and-invalid'
    prev = '0' * 64
    for i, e in enumerate(chain):
        if e.get('index') != i or e.get('prev_entry_sha256') != prev:
            rep('signature-invalid', 'error', 'chain[%d]' % i, 'index or prev_entry_sha256 wrong')
            return 'present-and-invalid'
        ok = ed25519_verify(bytes.fromhex(e['public_key']), sig_message(e), bytes.fromhex(e['signature']))
        if not ok:
            rep('signature-invalid', 'error', 'chain[%d]' % i, 'Ed25519 signature does not verify')
            return 'present-and-invalid'
        prev = hashlib.sha256(e['signature'].encode('utf-8')).hexdigest()
    if not chain or chain[-1]['manifest_sha256'] != msha or sj.get('manifest_sha256') != msha:
        rep('signature-invalid', 'error', 'SIGNATURE.json', 'last entry / top-level manifest_sha256 != sha256(MANIFEST.json)')
        return 'present-and-invalid'
    rep('signature-valid', 'info', 'SIGNATURE.json',
        '%d link(s) verify; key %s claims "%s" (no external trust root)' % (
            len(chain), chain[-1]['public_key'][:16] + '...', chain[-1]['signer']['name']))
    return 'signed-and-valid'


def inspect_node(n, ver, data, man):
    t = n['type']
    lines = []
    for f in ver['files']:
        b = data.get(f['path'])
        if b is None:
            continue
        p_ = f['path']
        try:
            if p_.endswith('.glb'):
                js, binc = parse_glb(b)
                prims = [pr for m in js.get('meshes', []) for pr in m['primitives']]
                vcount = sum(js['accessors'][pr['attributes']['POSITION']]['count'] for pr in prims)
                icount = sum(js['accessors'][pr['indices']]['count'] for pr in prims if 'indices' in pr)
                attrs = sorted({a for pr in prims for a in pr['attributes']})
                lines.append('%s: GLB v2, %d mesh(es), %d primitive(s), %d vertices, %d triangles, attributes %s'
                             % (p_, len(js.get('meshes', [])), len(prims), vcount, icount // 3, ','.join(attrs)))
                pos = [v for pr in prims for v in read_accessor(js, binc, pr['attributes']['POSITION'])]
                lo = [min(v[i] for v in pos) for i in range(3)]
                hi = [max(v[i] for v in pos) for i in range(3)]
                lines.append('%s: measured AABB min %s max %s' % (
                    p_, [round(x, 4) for x in lo], [round(x, 4) for x in hi]))
                if any(pr.get('mode', 4) != 4 for pr in prims):
                    lines.append('%s: WARNING non-triangle primitive mode' % p_)
                n['_aabb'] = (lo, hi)
            elif p_.endswith('.wav'):
                w = parse_wav(b)
                lines.append('%s: WAV fmt=%d %d ch %d Hz %d-bit, %d frames = %.3f s, peak %s dBFS, chunks %s' % (
                    p_, w['audio_format'], w['channels'], w['sample_rate'], w['bits'], w['frames'], w['seconds'],
                    '%.1f' % w['peak_dbfs'] if w['peak_dbfs'] is not None else '-inf', w['chunks']))
                desc = next((data[g['path']] for g in ver['files'] if g.get('role') == 'descriptor'), None)
                if desc:
                    af = strict_json(desc).get('audio_format', {})
                    if (af.get('sample_rate_hz'), af.get('channels'), af.get('bit_depth')) != (
                            w['sample_rate'], w['channels'], w['bits']):
                        rep('audio-format-disagrees', 'warn', n['node_id'], '%s vs descriptor audio_format' % p_)
            elif p_.endswith('.png'):
                ih, bad = parse_png(b)
                lines.append('%s: PNG %dx%d, %d-bit, %s channel(s), chunk CRCs %s' % (
                    p_, ih['width'], ih['height'], ih['bit_depth'], ih['channels'], 'ok' if not bad else 'BAD ' + str(bad)))
                metas = [m for m in n.get('meta', {}).get('images', []) if m.get('file') == p_]
                for m in metas:
                    if (m['width'], m['height'], m['bit_depth'], m['channels']) != (
                            ih['width'], ih['height'], ih['bit_depth'], ih['channels']):
                        rep('image-meta-disagrees', 'warn', n['node_id'], p_)
                if 'count' in n.get('meta', {}) and n['meta']['count'] != len(ver['files']):
                    rep('meta-count-disagrees', 'info', n['node_id'],
                        'meta.count=%d but the version lists %d file(s); meta.images names files not in this package'
                        % (n['meta']['count'], len(ver['files'])))
            elif t == 'core.pose.rest' or b[:2] == b'WK':
                magic, version, hdr = read_envelope(b)
                lines.append('%s: envelope %s v%d, kind %s, %d section(s), producer %s, epistemic %s, trials %s' % (
                    p_, magic.decode('ascii'), version, hdr['kind'], len(hdr['sections']),
                    hdr.get('producer'), hdr.get('epistemic'), hdr.get('trials')))
                if magic == b'WKRP':
                    rows, pts = decode_wkrp(b, hdr)
                    for k, r in enumerate(rows):
                        lines.append('  pose %d: quat wxyz %s, p=%.3f, %d contacts, support %.4f m2' % (
                            k, tuple(round(q, 4) for q in r['quat_wxyz']), r['probability'], r['contact_count'],
                            r['support_area_m2']))
                    lines.append('  contacts (model space, m): %s' % [tuple(round(c, 3) for c in p) for p in pts])
                if 'input_hash' in hdr and hdr['input_hash'] != ver.get('input_hash'):
                    rep('envelope-input-hash-disagrees', 'warn', n['node_id'], 'header vs manifest input_hash')
                hp = hdr.get('producer', {})
                if t != 'core.spec' and hp and hp.get('tool') != ver['producer'].get('tool'):
                    rep('producer-disagrees', 'warn', n['node_id'],
                        'envelope header producer %s != manifest producer %s' % (hp, ver['producer']))
            elif p_.endswith('.json'):
                j = strict_json(b)
                keys = list(j.keys()) if isinstance(j, dict) else []
                lines.append('%s: JSON ok, keys %s' % (p_, keys[:8]))
            else:
                b.decode('utf-8') if not p_.endswith(('.wkrp',)) else None
        except (ValueError, KeyError, IndexError, struct.error, UnicodeDecodeError) as ex:
            code = 'envelope-invalid' if (t == 'core.pose.rest' or b[:2] == b'WK') else 'payload-invalid'
            rep(code, 'error', n['node_id'], '%s: %s' % (p_, ex))
            lines.append('%s: INVALID (%s)' % (p_, ex))
    return lines


def print_report():
    out('\n[8] report (%d entries)' % len(REPORT))
    out('-' * 78)
    order = {'error': 0, 'warn': 1, 'info': 2}
    for sev, code, subj, msg in sorted(REPORT, key=lambda r: order[r[0]]):
        out('  %-5s %-28s %-34s %s' % (sev, code, subj, msg))
    errors = sum(1 for r in REPORT if r[0] == 'error')
    status = 1 if errors else 0
    if any(r[1] in ('container-refused', 'zip64-unsupported') for r in REPORT):
        status = 2
    out('\nexit status %d (%d error, %d warn, %d info)' % (
        status, errors, sum(1 for r in REPORT if r[0] == 'warn'), sum(1 for r in REPORT if r[0] == 'info')))
    return status


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main(sys.argv))
