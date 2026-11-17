#!/usr/bin/env python3
"""Reader for a werk 3D-entity package (profile 3d-entity/1).

Every rule here comes from the files inside the package:
  spec/SPEC.md            sections 1, 2, 2.1, 3, 5, 6, 10
  spec/MINI-SPECS.md      sections 3, 5, 9, 10, 11, 12
  spec/layouts/ENVELOPE.layout.txt, spec/layouts/restposes.layout.txt
  spec/conventions-map.json

Usage: python -I werk_reader.py PACKAGE.werk [OUTDIR]
The input package is opened read-only. Extracted files go to OUTDIR
(default: ./extracted).
"""
import hashlib
import json
import math
import os
import struct
import sys
import zipfile

# ---------------------------------------------------------------- reporting

REPORT = []  # (severity, code, subject, message)


def report(sev, code, subject, msg):
    REPORT.append((sev, code, subject, msg))
    print('  [%-5s] %-28s %-34s %s' % (sev, code, subject, msg))


def sha256_hex(b):
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------- container (MINI-SPECS 5)

def check_zip64(path):
    """MINI-SPECS 5.5: detect zip64 and refuse; a zip32 reader must not guess."""
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        n = min(size, 65535 + 22)
        f.seek(size - n)
        tail = f.read(n)
    for i in range(len(tail) - 22, -1, -1):
        if tail[i:i + 4] == b'PK\x05\x06':
            (_, _, _, ndisk, ntot, cdsize, cdoff, clen) = struct.unpack_from('<IHHHHIIH', tail, i)
            if i + 22 + clen != len(tail):
                continue  # not a real EOCD: comment length disagrees
            zip64 = (ndisk == 0xFFFF or ntot == 0xFFFF or cdsize == 0xFFFFFFFF
                     or cdoff == 0xFFFFFFFF
                     or (i >= 20 and tail[i - 20:i - 16] == b'PK\x06\x07'))
            return True, zip64
    return False, False


# ------------------------------------------------------ JSON (MINI-SPECS 3)

def strict_json(raw, what):
    if raw.startswith(b'\xef\xbb\xbf'):
        raise ValueError('%s: UTF-8 BOM present (MINI-SPECS 2 says reject)' % what)

    def no_dupes(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise ValueError('%s: duplicate key %r (MINI-SPECS 3 says reject)' % (what, k))
            d[k] = v
        return d

    def no_const(c):
        raise ValueError('%s: non-finite number %s' % (what, c))

    return json.loads(raw.decode('utf-8'), object_pairs_hook=no_dupes, parse_constant=no_const)


def canonical_json(v):
    """MINI-SPECS 3, 'Canonical JSON (for hashing only)'."""
    if isinstance(v, dict):
        items = sorted(v.items(), key=lambda kv: kv[0].encode('utf-8'))
        return '{' + ','.join(canonical_json(k) + ':' + canonical_json(x) for k, x in items) + '}'
    if isinstance(v, list):
        return '[' + ','.join(canonical_json(x) for x in v) + ']'
    if isinstance(v, str):
        out = ['"']
        short = {'"': '\\"', '\\': '\\\\', '\b': '\\b', '\f': '\\f', '\n': '\\n', '\r': '\\r', '\t': '\\t'}
        for ch in v:
            if ch in short:
                out.append(short[ch])
            elif ord(ch) < 0x20:
                out.append('\\u%04x' % ord(ch))
            else:
                out.append(ch)
        out.append('"')
        return ''.join(out)
    if v is True:
        return 'true'
    if v is False:
        return 'false'
    if v is None:
        return 'null'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v.is_integer() and abs(v) < 2 ** 53:
            return str(int(v))
        return repr(v)
    raise TypeError(type(v))


# ---------------------------------------------- Ed25519 (MINI-SPECS 12, verify only)

P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493


def inv(a):
    return pow(a, P - 2, P)


D = (-121665 * inv(121666)) % P
I = pow(2, (P - 1) // 4, P)


def decompress(b):
    if len(b) != 32:
        return None
    n = int.from_bytes(b, 'little')
    sign = n >> 255
    y = n & ((1 << 255) - 1)
    if y >= P:
        return None
    u = (y * y - 1) % P
    v = (D * y * y + 1) % P
    x = (u * pow(v, 3, P) * pow(u * pow(v, 7, P), (P - 5) // 8, P)) % P
    if (v * x * x) % P == (-u) % P:
        x = (x * I) % P
    if (v * x * x) % P != u % P:
        return None
    if x == 0 and sign == 1:
        return None
    if (x & 1) != sign:
        x = P - x
    return (x, y, 1, (x * y) % P)


def padd(p1, p2):
    X1, Y1, Z1, T1 = p1
    X2, Y2, Z2, T2 = p2
    A = (Y1 - X1) * (Y2 - X2) % P
    B = (Y1 + X1) * (Y2 + X2) % P
    C = T1 * 2 * D * T2 % P
    Dd = Z1 * 2 * Z2 % P
    E, F, G, H = B - A, Dd - C, Dd + C, B + A
    return (E * F % P, G * H % P, F * G % P, E * H % P)


def smul(k, pt):
    q = (0, 1, 1, 0)  # neutral element
    while k:
        if k & 1:
            q = padd(q, pt)
        pt = padd(pt, pt)
        k >>= 1
    return q


def peq(p1, p2):
    X1, Y1, Z1, _ = p1
    X2, Y2, Z2, _ = p2
    return (X1 * Z2 - X2 * Z1) % P == 0 and (Y1 * Z2 - Y2 * Z1) % P == 0


def base_point():
    y = 4 * inv(5) % P
    enc = y.to_bytes(32, 'little')  # sign bit 0 -> even x
    return decompress(enc)


B_PT = None


def ed25519_verify(pub, msg, sig):
    global B_PT
    if B_PT is None:
        B_PT = base_point()
    if len(sig) != 64:
        return False
    S = int.from_bytes(sig[32:], 'little')
    if S >= L:
        return False
    A = decompress(pub)
    R = decompress(sig[:32])
    if A is None or R is None:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), 'little') % L
    lhs = smul(S, B_PT)
    rhs = padd(R, smul(k, A))
    if peq(lhs, rhs):
        return True
    return peq(smul(8, lhs), smul(8, rhs))  # cofactored form, also accepted


def ed25519_selftest():
    pub = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
    sig = bytes.fromhex('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b')
    ok1 = ed25519_verify(pub, b'', sig)
    bad = bytearray(sig)
    bad[0] ^= 1
    ok2 = not ed25519_verify(pub, b'', bytes(bad))
    # MINI-SPECS 12.1 worked example: the message construction checkpoint.
    m = '\n'.join(['werk-sig/1', 'c421d2e85a9455f0be794ca8ee673f727a7ef67485d631e374f95c4a6d6ce61a',
                   '0' * 64, '2026-08-08T09:00:00Z', 'urn:werk:fixture:rfc8032-vector-1', 'service']).encode()
    ok3 = len(m) == 203 and sha256_hex(m) == '11e260cc16bc454f39f1aa6d56679c868ba1e83d33e3c22a462040b32a92165a'
    sig2 = bytes.fromhex('55720b6fc38d680f8ca7523c0d8cec5045c7247f7158ab54eafd03d6ea0eedb1'
                         'aeb4902b4704a5c2e78d7713b375068748bea4fd116a2d3a49f6010074c6410d')
    ok4 = ed25519_verify(pub, m, sig2)
    return ok1 and ok2 and ok3 and ok4


def sha_selftest():
    return (hashlib.sha256(b'abc').hexdigest() == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
            and hashlib.sha512(b'abc').hexdigest().startswith('ddaf35a193617aba'))


# ---------------------------------------- MessagePack subset (ENVELOPE 4)

class MPError(Exception):
    pass


def mp_decode(buf, i=0):
    if i >= len(buf):
        raise MPError('truncated')
    b = buf[i]
    i += 1

    def take(n):
        nonlocal i
        if i + n > len(buf):
            raise MPError('truncated')
        r = buf[i:i + n]
        i += n
        return r

    if b <= 0x7f:
        return b, i
    if b >= 0xe0:
        return b - 256, i
    if 0xa0 <= b <= 0xbf:
        return take(b & 0x1f).decode('utf-8'), i
    if 0x90 <= b <= 0x9f:
        return _mp_array(buf, i, b & 0x0f)
    if 0x80 <= b <= 0x8f:
        return _mp_map(buf, i, b & 0x0f)
    if b == 0xc0:
        return None, i
    if b == 0xc2:
        return False, i
    if b == 0xc3:
        return True, i
    fixed = {0xcc: '>B', 0xcd: '>H', 0xce: '>I', 0xcf: '>Q', 0xd0: '>b', 0xd1: '>h',
             0xd2: '>i', 0xd3: '>q', 0xca: '>f', 0xcb: '>d'}
    if b in fixed:
        fmt = fixed[b]
        return struct.unpack(fmt, take(struct.calcsize(fmt)))[0], i
    if b in (0xd9, 0xda, 0xdb):
        n = struct.unpack({0xd9: '>B', 0xda: '>H', 0xdb: '>I'}[b], take({0xd9: 1, 0xda: 2, 0xdb: 4}[b]))[0]
        return take(n).decode('utf-8'), i
    if b in (0xc4, 0xc5, 0xc6):
        n = struct.unpack({0xc4: '>B', 0xc5: '>H', 0xc6: '>I'}[b], take({0xc4: 1, 0xc5: 2, 0xc6: 4}[b]))[0]
        return bytes(take(n)), i
    if b in (0xdc, 0xdd):
        n = struct.unpack('>H' if b == 0xdc else '>I', take(2 if b == 0xdc else 4))[0]
        return _mp_array(buf, i, n)
    if b in (0xde, 0xdf):
        n = struct.unpack('>H' if b == 0xde else '>I', take(2 if b == 0xde else 4))[0]
        return _mp_map(buf, i, n)
    raise MPError('banned or unknown format byte 0x%02x' % b)


def _mp_array(buf, i, n):
    out = []
    for _ in range(n):
        v, i = mp_decode(buf, i)
        out.append(v)
    return out, i


def _mp_map(buf, i, n):
    out = {}
    for _ in range(n):
        k, i = mp_decode(buf, i)
        v, i = mp_decode(buf, i)
        if k in out:
            raise MPError('duplicate map key %r' % (k,))
        out[k] = v
    return out, i


DTYPE_SIZE = {'u8': 1, 'i8': 1, 'u16': 2, 'i16': 2, 'u32': 4, 'i32': 4, 'u64': 8, 'i64': 8, 'f32': 4, 'f64': 8}
MAGIC_KIND = {b'WKFF': 'core.field.flow', b'WKRP': 'core.pose.rest', b'WKAC': 'core.anim.clip',
              b'WKSK': 'core.skeleton', b'WKEM': 'core.embedding', b'WKPC': 'core.geom.points',
              b'WKGS': 'core.geom.gsplat'}


def read_envelope(buf):
    """ENVELOPE.layout.txt section 7. Raises ValueError naming the failed check."""
    if len(buf) < 12:
        raise ValueError('shorter than 12 bytes')
    magic = bytes(buf[0:4])
    version, header_len = struct.unpack_from('<II', buf, 4)
    if 12 + header_len > len(buf):
        raise ValueError('header_len runs past end of file')
    header, end = mp_decode(buf, 12)
    if end != 12 + header_len:
        raise ValueError('MessagePack header length %d != header_len %d' % (end - 12, header_len))
    if not isinstance(header, dict):
        raise ValueError('header is not a map')
    for k in ('kind', 'endianness', 'payload_origin', 'payload_size', 'sections'):
        if k not in header:
            raise ValueError('mandatory header key %r missing' % k)
    if magic in MAGIC_KIND and header['kind'] != MAGIC_KIND[magic]:
        raise ValueError('kind %r does not match magic %r' % (header['kind'], magic))
    if header['endianness'] != 'le':
        raise ValueError('endianness is not "le"')
    p = 16 * math.ceil((12 + header_len) / 16)
    if header['payload_origin'] != p:
        raise ValueError('payload_origin %d != computed %d' % (header['payload_origin'], p))
    if p + header['payload_size'] != len(buf):
        raise ValueError('payload_origin + payload_size != file size')
    sections = {}
    prev_end = p
    for idx, s in enumerate(header['sections']):
        off, size, stride, shape = s['offset'], s['size'], s['stride'], s['shape']
        if off % 16:
            raise ValueError('section %s offset not 16-aligned' % s['name'])
        if idx == 0 and off != p:
            raise ValueError('section 0 does not start at payload_origin')
        if off < prev_end or off - prev_end > 15:
            raise ValueError('section %s out of order or gap > 15' % s['name'])
        if off + size > len(buf):
            raise ValueError('section %s runs past end of file' % s['name'])
        esz = DTYPE_SIZE.get(s['dtype'], stride if s['dtype'] == 'record' else None)
        if esz is None:
            raise ValueError('unknown dtype %r' % s['dtype'])
        if stride == esz:
            if size != stride * math.prod(shape):
                raise ValueError('section %s size rule (branch 1) fails' % s['name'])
        else:
            if stride < esz * shape[-1] or size != stride * math.prod(shape[:-1]):
                raise ValueError('section %s size rule (branch 2) fails' % s['name'])
        prev_end = off + size
        sections[s['name']] = s
    if 16 * math.ceil(prev_end / 16) != p + header['payload_size']:
        raise ValueError('trailing data after last section')
    return magic, version, header, sections


def decode_wkrp(buf, header, sections):
    """restposes.layout.txt. Returns a short text summary; raises on invariant failure."""
    poses = sections['poses']
    contacts = sections['contacts']
    n = header['pose_count']
    entries = []
    for k in range(n):
        o = poses['offset'] + k * poses['stride']
        w, x, y, z, cf, cc, prob, area = struct.unpack_from('<4fII2f', buf, o)
        for f in (w, x, y, z, prob, area):
            if not math.isfinite(f):
                raise ValueError('NaN or infinity in pose %d' % k)
        if abs(math.sqrt(w * w + x * x + y * y + z * z) - 1.0) > 1e-6:
            raise ValueError('pose %d quaternion not unit length' % k)
        entries.append((w, x, y, z, cf, cc, prob, area))
    if sum(e[5] for e in entries) != header['contact_count']:
        raise ValueError('sum of contact_count != header contact_count')
    if any(entries[i][6] < entries[i + 1][6] for i in range(n - 1)):
        raise ValueError('poses not sorted by probability descending')
    if header.get('trials', 0) > 0 and abs(sum(e[6] for e in entries) - 1.0) > 1e-3:
        raise ValueError('probabilities do not sum to 1.0 +/- 1e-3')
    pts = [struct.unpack_from('<3f', buf, contacts['offset'] + c * contacts['stride'])
           for c in range(header['contact_count'])]
    lines = ['%d poses from %d trials, %d contact points' % (n, header.get('trials', 0), len(pts))]
    for k, e in enumerate(entries):
        lines.append('pose %d: q(wxyz)=(%.4f, %.4f, %.4f, %.4f) p=%.3f contacts=%d area=%.4f m^2'
                     % (k, e[0], e[1], e[2], e[3], e[6], e[5], e[7]))
    return lines


# --------------------------------------------- GLB and WAV (MINI-SPECS 9, 10)

def describe_glb(b):
    if b[:4] != b'glTF':
        raise ValueError('no glTF magic')
    ver, total = struct.unpack_from('<II', b, 4)
    if ver != 2 or total != len(b):
        raise ValueError('version %d / length %d vs file %d' % (ver, total, len(b)))
    jlen, jtype = struct.unpack_from('<II', b, 12)
    if jtype != 0x4E4F534A:
        raise ValueError('first chunk is not JSON')
    doc = json.loads(b[20:20 + jlen].decode('utf-8'))
    o = 20 + jlen
    binlen = 0
    if o < len(b):
        binlen, btype = struct.unpack_from('<II', b, o)
        if btype != 0x004E4942:
            raise ValueError('second chunk is not BIN')
    tris = verts = 0
    problems = []
    for m in doc.get('meshes', []):
        for prim in m['primitives']:
            if prim.get('mode', 4) != 4:
                problems.append('primitive mode %s is not triangles' % prim.get('mode'))
            if 'indices' not in prim:
                problems.append('non-indexed primitive')
            else:
                acc = doc['accessors'][prim['indices']]
                if acc['componentType'] not in (5123, 5125):
                    problems.append('index componentType %d' % acc['componentType'])
                tris += acc['count'] // 3
            attrs = prim['attributes']
            for need in ('POSITION', 'NORMAL'):
                if need not in attrs:
                    problems.append('missing %s (SPEC 3.10)' % need)
            verts += doc['accessors'][attrs['POSITION']]['count']
    return ('GLB v2, %d bytes, JSON %d B, BIN %d B, %d mesh(es), %d vertices, %d triangles, attributes %s'
            % (len(b), jlen, binlen, len(doc.get('meshes', [])), verts, tris,
               sorted({a for m in doc.get('meshes', []) for p in m['primitives'] for a in p['attributes']}))), problems


def describe_wav(b):
    if b[:4] != b'RIFF' or b[8:12] != b'WAVE':
        raise ValueError('not RIFF/WAVE')
    riff_size = struct.unpack_from('<I', b, 4)[0]
    i = 12
    fmt = None
    data_size = None
    while i + 8 <= len(b):
        cid = b[i:i + 4]
        size = struct.unpack_from('<I', b, i + 4)[0]
        if cid == b'fmt ':
            fmt = struct.unpack_from('<HHIIHH', b, i + 8)
        elif cid == b'data':
            data_size = size
        i += 8 + size + (size & 1)  # pad byte not counted in size
    if fmt is None or data_size is None:
        raise ValueError('missing fmt or data chunk')
    afmt, ch, rate, brate, align, bits = fmt
    frames = data_size // align
    notes = []
    if riff_size + 8 != len(b):
        notes.append('RIFF size %d + 8 != file size %d' % (riff_size, len(b)))
    return ('WAV format=%d (%s), %d ch, %d Hz, %d bit, %d frames = %.3f s'
            % (afmt, {1: 'PCM', 3: 'float', 0xFFFE: 'extensible'}.get(afmt, '?'), ch, rate, bits,
               frames, frames / rate)), notes


# ----------------------------------------------------- node-type meanings

TYPE_MEANING = {  # SPEC.md section 3 table and spec/README.md
    'core.spec': 'the format specification carried inside the file',
    'core.loader': 'an embedded reader program (source); inert data to this reader',
    'core.license': 'full licence text',
    'core.readme': 'one page for a human',
    'core.geom.source': 'archival master mesh (GLB)',
    'core.geom.game': 'runtime mesh (GLB); the default primary mesh',
    'core.geom.lod': 'level-of-detail mesh (GLB)',
    'core.material': 'PBR material parameters (JSON); authoritative over the GLB',
    'core.phys.bounds': 'measured bounding volumes in model space (JSON)',
    'core.semantics': 'facet tags, palette and search text (JSON)',
    'core.provenance': 'who made what, from what, with which tools (JSON)',
    'core.audio.effect': 'one sound effect: WAV takes plus a JSON sidecar',
    'core.audio.package': 'the set of sound effects (JSON)',
    'core.pose.rest': 'settled rest orientations from a drop simulation (WKRP envelope binary)',
}

SUPPORTED_CONVENTIONS = {  # SPEC.md section 2, the values this reader implements
    'endianness': 'le', 'units_per_meter': 1.0, 'length_unit': 'metre', 'angle_unit': 'radian',
    'time_unit': 'second', 'mass_unit': 'kilogram', 'up_axis': 'y', 'forward_axis': '-z',
    'right_axis': '+x', 'handedness': 'right', 'winding': 'ccw', 'quat_order': 'wxyz',
    'oct_encoding_pole': 'y', 'sh_l1_order': ['dc', 'y', 'z', 'x'], 'color_space_default': 'srgb',
    'uv_origin': 'top-left', 'alignment_bytes': 16, 'text_encoding': 'utf-8', 'id_case': 'kebab-case',
    'hash_algorithm': 'sha256', 'signature_algorithm': 'ed25519',
}


def type_matches(t, pattern):
    if pattern == '*':
        return True
    if pattern.endswith('.*'):
        return t.startswith(pattern[:-1])
    return t == pattern


def resolve_payload(node_type, version):
    """SPEC.md section 2.1, normative order. Never files[0]."""
    files = version['files']
    if 'payload_file' in version:
        hits = [f for f in files if f['path'] == version['payload_file']]
        if len(hits) == 1:
            return hits[0], 'rule 1 (payload_file)'
        return None, 'payload_file names no single entry of files[]'
    if len(files) == 1:
        return files[0], 'rule 2 (single file)'
    hits = [f for f in files if f.get('role') == 'payload']
    if len(hits) == 1:
        return hits[0], 'rule 3 (role payload)'
    role = {'core.audio.effect': 'best', 'core.audio.ambience': 'best', 'core.imposter': 'atlas',
            'core.recipe': 'record'}.get(node_type)
    if role:
        hits = [f for f in files if f.get('role') == role]
        if len(hits) == 1:
            return hits[0], 'rule 4 (role %s)' % role
    return None, 'payload-file-ambiguous'


# ------------------------------------------------------------------- main

def main(argv):
    path = argv[1]
    outdir = argv[2] if len(argv) > 2 else 'extracted'

    print('== self-tests (MINI-SPECS 11, 12 test vectors)')
    sha_ok = sha_selftest()
    ed_ok = ed25519_selftest()
    print('  sha256/sha512 vectors: %s; ed25519 RFC 8032 vector + 12.1 worked example: %s'
          % ('pass' if sha_ok else 'FAIL', 'pass' if ed_ok else 'FAIL'))

    print('\n== 1. container')
    found, zip64 = check_zip64(path)
    if not found:
        report('error', 'container-refused', path, 'no EOCD record: not a zip')
        return 2
    if zip64:
        report('error', 'zip64-unsupported', path, 'zip64 container; this reader is zip32-only')
        return 2
    z = zipfile.ZipFile(path)
    infos = {i.filename: i for i in z.infolist()}
    print('  %d entries, all store-mode: %s' % (len(infos), all(i.compress_type == 0 for i in infos.values())))
    for i in infos.values():
        if i.compress_type not in (0, 8):
            report('error', 'unsupported-compression', i.filename, 'method %d' % i.compress_type)
        n = i.filename
        if n.startswith('/') or '..' in n.split('/') or ':' in n or '\\' in n:
            report('error', 'unsafe-path', n, 'zip entry name breaks MINI-SPECS 5.4')
        if i.flag_bits & 0x8:
            report('warn', 'data-descriptor', n, 'general purpose flag bit 3 set')

    data = {}

    def read(name):
        if name not in data:
            try:
                data[name] = z.read(name)  # zipfile checks the CRC-32 here
            except zipfile.BadZipFile as e:
                data[name] = None
                report('error', 'crc-mismatch', name, str(e))
        return data[name]

    print('\n== 2. MANIFEST.json')
    if 'MANIFEST.json' not in infos:
        report('error', 'container-refused', 'MANIFEST.json', 'missing')
        return 2
    mraw = read('MANIFEST.json')
    try:
        man = strict_json(mraw, 'MANIFEST.json')
    except Exception as e:
        report('error', 'container-refused', 'MANIFEST.json', str(e))
        return 2
    print('  werk %s.%s  profile %s' % (man['werk']['major'], man['werk']['minor'], man.get('profile')))
    print('  entity: %s (%s)' % (man['entity']['name'], man['entity']['uuid']))
    print('  %s' % man['entity'].get('summary', ''))
    if man['werk']['major'] != 1:
        report('error', 'unsupported-major', 'werk.major', str(man['werk']['major']))
    if man.get('profile') != '3d-entity/1':
        report('warn', 'unsupported-profile', 'profile', 'payload meaning not claimed')
    print('  manifest sha256 %s' % sha256_hex(mraw))

    print('\n== 3. conventions')
    cmap = None
    cpath = man.get('conventions_map')
    if cpath and cpath in infos:
        cmap = strict_json(read(cpath), cpath)['conventions']
    refused_types = []
    for key, want in SUPPORTED_CONVENTIONS.items():
        have = man['conventions'].get(key, None)
        if have is None:
            if cmap and cmap.get(key, {}).get('optional'):
                continue
            report('error', 'missing-convention', key, 'not declared')
            continue
        if have != want:
            scope = cmap.get(key, {}).get('scope') if cmap else '?'
            governs = cmap.get(key, {}).get('governs', []) if cmap else []
            report('error', 'unsupported-convention', key, '%r (scope %s, refuses %s)' % (have, scope, governs))
            refused_types += governs
    for key in man['conventions']:
        if key not in SUPPORTED_CONVENTIONS and not (cmap and cmap.get(key, {}).get('optional')):
            report('info', 'unknown-convention', key, repr(man['conventions'][key]))
    print('  all %d conventions checked against conventions map %s' % (len(man['conventions']), cpath))

    print('\n== 4. signature (SPEC 6, MINI-SPECS 12.1)')
    sig_state = 'absent'
    if 'SIGNATURE.json' in infos:
        sig = strict_json(read('SIGNATURE.json'), 'SIGNATURE.json')
        if not ed_ok or sig.get('algorithm') != 'ed25519':
            sig_state = 'unverified'
        else:
            sig_state = 'signed-and-valid'
            prev = '0' * 64
            for e in sig['chain']:
                if e['prev_entry_sha256'] != prev:
                    sig_state = 'present-and-invalid'
                    report('error', 'signature-invalid', 'chain[%d]' % e['index'], 'prev_entry_sha256 does not link')
                msg = '\n'.join(['werk-sig/1', e['manifest_sha256'], e['prev_entry_sha256'], e['signed_at'],
                                 e['signer']['uri'], e['signer']['kind']]).encode('utf-8')
                ok = ed25519_verify(bytes.fromhex(e['public_key']), msg, bytes.fromhex(e['signature']))
                print('  chain[%d] signer %s key %s..: ed25519 %s'
                      % (e['index'], e['signer']['uri'], e['public_key'][:16], 'valid' if ok else 'INVALID'))
                if not ok:
                    sig_state = 'present-and-invalid'
                    report('error', 'signature-invalid', 'chain[%d]' % e['index'], 'Ed25519 check failed')
                prev = sha256_hex(e['signature'].encode('utf-8'))
            actual = sha256_hex(mraw)
            last = sig['chain'][-1]['manifest_sha256']
            if last != actual:
                sig_state = 'present-and-invalid'
                report('error', 'signature-invalid', 'MANIFEST.json',
                       'last chain entry anchors %s.. but MANIFEST.json hashes to %s..' % (last[:16], actual[:16]))
            if sig.get('manifest_sha256') != last:
                report('warn', 'signature-anchor-copy', 'SIGNATURE.json', 'top-level manifest_sha256 != last entry')
    code = {'signed-and-valid': 'signature-valid', 'absent': 'signature-absent',
            'present-and-invalid': 'signature-invalid', 'unverified': 'signature-unverified'}[sig_state]
    report('info' if sig_state == 'signed-and-valid' else 'error' if sig_state == 'present-and-invalid' else 'warn',
           code, 'SIGNATURE.json', sig_state)

    print('\n== 5/6. nodes, files, hashes')
    nodes = {n['node_id']: n for n in man['nodes']}
    declared_hash = {}
    owner = {}
    dead = {}
    for n in man['nodes']:
        nid = n['node_id']
        for v in n['versions']:
            for f in v['files']:
                if f['path'] in owner and owner[f['path']] != nid:
                    report('error', 'file-claimed-twice', f['path'], 'by %s and %s' % (owner[f['path']], nid))
                owner[f['path']] = nid
                declared_hash.setdefault(f['path'], f['sha256'])
    for n in man['nodes']:
        nid, t = n['node_id'], n['type']
        actives = [v for v in n['versions'] if v['v'] == n.get('active')]
        if not actives:
            report('error', 'active-invalid', nid, 'active=%r names no version' % n.get('active'))
            dead[nid] = 'no active version'
            continue
        v = actives[0]
        for f in v['files']:
            p = f['path']
            if p not in infos:
                report('error', 'file-missing', p, 'declared by %s, not in container' % nid)
                dead[nid] = 'file missing: ' + p
                continue
            b = read(p)
            if b is None:
                dead[nid] = 'crc failure: ' + p
                continue
            if len(b) != f['size']:
                report('error', 'size-mismatch', p, 'declared %d, actual %d' % (f['size'], len(b)))
                dead[nid] = 'size mismatch: ' + p
            h = sha256_hex(b)
            if h != f['sha256']:
                report('error', 'hash-mismatch', p, 'declared %s.., actual %s..' % (f['sha256'][:16], h[:16]))
                dead[nid] = 'hash mismatch: ' + p
        if any(type_matches(t, g) for g in refused_types):
            dead.setdefault(nid, 'refused: unsupported convention')
    floating = [p for p in infos if not p.endswith('/') and p not in owner
                and p not in ('MANIFEST.json', 'SIGNATURE.json')]
    for p in floating:
        report('warn', 'file-floating', p, 'in container, claimed by no node')
    nfiles = sum(len(v['files']) for n in man['nodes'] for v in n['versions'] if v['v'] == n.get('active'))
    nbad = sum(1 for r in REPORT if r[1] in ('hash-mismatch', 'size-mismatch', 'file-missing', 'crc-mismatch'))
    print('  %d declared files checked (size + sha256): %d problem(s)' % (nfiles, nbad))

    # preview_prefix_bytes is a HINT (SPEC 1, S-15): recompute and report, never fail.
    hint = man.get('container', {}).get('preview_prefix_bytes')
    if hint is not None:
        tier = man['container'].get('preview_tier') or ['MANIFEST.json', 'SIGNATURE.json', 'LICENSE', 'README.txt',
                                                        'loaders/', 'spec/', 'semantics/', 'imposters/']
        snode = nodes.get(man.get('primary', {}).get('sound'))
        if snode and not man['container'].get('preview_tier'):
            sv = [v for v in snode['versions'] if v['v'] == snode['active']][0]
            sf, _ = resolve_payload(snode['type'], sv)
            if sf:
                tier = tier + [sf['path']]
        end = 0
        with open(path, 'rb') as fh:
            for i in infos.values():
                if any(i.filename == t or (t.endswith('/') and i.filename.startswith(t)) for t in tier):
                    fh.seek(i.header_offset + 26)
                    nlen, xlen = struct.unpack('<HH', fh.read(4))
                    end = max(end, i.header_offset + 30 + nlen + xlen + i.compress_size)
        print('  preview_prefix_bytes hint %d, recomputed %d (%s)' % (hint, end, 'equal' if hint == end else 'differs; hint only'))
        if hint != end:
            report('info', 'preview-prefix-differs', 'container', 'hint %d, recomputed %d' % (hint, end))

    # license.sha256 and spec_sha256 (SPEC 2)
    lic = man.get('license', {})
    if lic.get('file') in infos:
        ok = sha256_hex(read(lic['file'])) == lic.get('sha256')
        print('  license.sha256 (%s): %s' % (lic['file'], 'match' if ok else 'MISMATCH'))
        if not ok:
            report('error', 'hash-mismatch', 'license.sha256', 'does not match LICENSE bytes')
    spec_paths = sorted({p for p in owner if p.startswith('spec/')}, key=lambda s: s.encode('utf-8'))
    acc = b''.join(p.encode('utf-8') + b'\n' + bytes.fromhex(declared_hash[p]) + b'\n' for p in spec_paths)
    spec_h = sha256_hex(acc)
    print('  spec_sha256 over %d spec/ files: %s' % (len(spec_paths), 'match' if spec_h == man.get('spec_sha256') else 'MISMATCH'))
    if spec_h != man.get('spec_sha256'):
        report('error', 'spec-sha256-mismatch', 'spec_sha256', 'computed %s' % spec_h)

    # input_hash (MINI-SPECS 11, "What gets hashed")
    print('\n== input_hash (staleness of derived data)')
    for n in man['nodes']:
        for v in n['versions']:
            if 'input_hash' not in v:
                continue
            ins = v.get('input_files', [])
            missing = [p for p in ins if p not in declared_hash]
            if missing:
                report('info', 'input-hash-unverifiable', n['node_id'],
                       'input(s) not in this package: %s' % ', '.join(missing))
                continue
            h = hashlib.sha256()
            for p in ins:
                h.update(bytes.fromhex(declared_hash[p]))
            h.update(canonical_json(v.get('input_params') or {}).encode('utf-8'))
            ok = h.hexdigest() == v['input_hash']
            print('  %-32s %s' % (n['node_id'], 'input_hash matches' if ok else 'input_hash STALE (computed %s..)' % h.hexdigest()[:16]))
            if not ok:
                report('warn', 'input-hash-stale', n['node_id'], 'derived data may be stale')

    # edges (SPEC 5)
    print('\n== edges')
    changed = True
    while changed:
        changed = False
        for n in man['nodes']:
            for e in n.get('edges', []):
                if e['kind'] == 'requires' and n['node_id'] not in dead and (e['to'] in dead or e['to'] not in nodes):
                    dead[n['node_id']] = 'requires dead/absent node %s' % e['to']
                    changed = True
    for n in man['nodes']:
        for e in n.get('edges', []):
            if e['to'] not in nodes:
                sev = 'error' if e['kind'] == 'requires' else 'info'
                report(sev, 'edge-target-absent', n['node_id'],
                       '%s edge (%s) -> %s, which is not in this package' % (e['kind'], e.get('role', ''), e['to']))

    # payload interpretation (SPEC 10 step 7)
    print('\n== payloads')
    detail = {}
    for n in man['nodes']:
        nid, t = n['node_id'], n['type']
        if nid in dead:
            continue
        v = [v for v in n['versions'] if v['v'] == n['active']][0]
        try:
            if t.startswith('core.geom.') and t not in ('core.geom.points', 'core.geom.gsplat'):
                f, _ = resolve_payload(t, v)
                desc, probs = describe_glb(read(f['path']))
                detail[nid] = [desc]
                for pr in probs:
                    report('warn' if t == 'core.geom.source' else 'error', 'glb-nonconformant', nid, pr)
            elif t in ('core.audio.effect', 'core.audio.ambience'):
                lines = []
                for f in v['files']:
                    if f.get('media_type') == 'audio/wav' or f['path'].endswith('.wav'):
                        desc, notes = describe_wav(read(f['path']))
                        lines.append('%-6s %s: %s' % (f.get('role', ''), f['path'], desc))
                        for nt in notes:
                            report('warn', 'wav-note', f['path'], nt)
                    else:
                        side = strict_json(read(f['path']), f['path'])
                        lines.append('sidecar %s: slug=%s prompt_used=%r' % (f['path'], side.get('slug'), side.get('prompt_used')))
                detail[nid] = lines
            elif t in TYPE_MEANING and t.startswith('core.') and any(f['path'].endswith('.json') for f in v['files']) \
                    and t not in ('core.spec',):
                for f in v['files']:
                    if f['path'].endswith('.json'):
                        strict_json(read(f['path']), f['path'])
                detail[nid] = ['JSON parses strictly (not schema-validated)']
            elif t == 'core.pose.rest':
                f, _ = resolve_payload(t, v)
                buf = read(f['path'])
                magic, ver, hdr, secs = read_envelope(buf)
                lines = ['envelope %s v%d, header kind=%s, producer=%s' % (magic.decode(), ver, hdr['kind'], hdr.get('producer'))]
                lines += decode_wkrp(buf, hdr, secs)
                for name in secs:
                    if name not in ('poses', 'contacts'):
                        report('info', 'section-skipped-unknown', nid, name)
                if 'input_hash' in hdr and hdr['input_hash'] != v.get('input_hash'):
                    report('warn', 'input-hash-disagrees', nid, 'envelope header and manifest differ')
                hp = hdr.get('producer') or {}
                if hp and hp.get('tool') != v['producer'].get('tool'):
                    report('info', 'producer-disagrees', nid,
                           'envelope header producer %s, manifest producer %s' % (hp.get('tool'), v['producer'].get('tool')))
                detail[nid] = lines
            elif t in ('core.spec', 'core.loader', 'core.license', 'core.readme'):
                detail[nid] = ['%d file(s), text; loaders are listed and hashed, never executed' % len(v['files'])]
            else:
                report('info', 'node-skipped-unknown-type', nid, '%s: listed and hash-verified, not interpreted' % t)
        except Exception as ex:
            dead[nid] = 'payload invalid: %s' % ex
            report('error', 'envelope-invalid' if t == 'core.pose.rest' else 'payload-invalid', nid, str(ex))

    print('\n== node graph')
    for n in man['nodes']:
        nid, t = n['node_id'], n['type']
        v = [v for v in n['versions'] if v['v'] == n.get('active')]
        v = v[0] if v else n['versions'][-1]
        status = 'DEAD (%s)' % dead[nid] if nid in dead else 'live'
        print('\n  %s  [%s]  v%s  %s' % (nid, t, n.get('active'), status))
        print('    meaning : %s' % TYPE_MEANING.get(t, 'extension node type (x.*): not interpreted by this reader' if t.startswith('x.') else 'unknown type'))
        print('    note    : %s' % v.get('note', ''))
        print('    producer: %s  epistemic: %s%s' % (v.get('producer'), v.get('epistemic'),
                                                  ('  confidence %s' % v['confidence']) if 'confidence' in v else ''))
        for f in v['files']:
            print('    file    : %-50s %8d  %s  %s' % (f['path'], f['size'], f['sha256'][:16] + '..', f.get('role', '')))
        for e in n.get('edges', []):
            print('    edge    : %s -> %s (%s)%s' % (e['kind'], e['to'], e.get('role', ''), '' if e['to'] in nodes else '  [target absent]'))
        for line in detail.get(nid, []):
            print('    detail  : %s' % line)

    print('\n== extraction (primary block, SPEC 2 and 2.1)')
    os.makedirs(outdir, exist_ok=True)
    prim = man.get('primary', {})
    results = []
    for slot, fallback_type in (('mesh', 'core.geom.game'), ('sound', 'core.audio.effect')):
        nid = prim.get(slot)
        if nid is None:
            cands = [n['node_id'] for n in man['nodes'] if n['type'] == fallback_type]
            nid = cands[0] if cands else None
            report('warn', 'primary-fallback', slot, 'primary.%s absent; fell back to %s' % (slot, nid))
        if nid not in nodes:
            report('error', 'primary-missing', slot, 'node %s not found' % nid)
            continue
        if nid in dead:
            report('error', 'primary-dead', slot, '%s is dead: %s' % (nid, dead[nid]))
            continue
        n = nodes[nid]
        v = [v for v in n['versions'] if v['v'] == n['active']][0]
        f, rule = resolve_payload(n['type'], v)
        if f is None:
            report('warn', 'payload-file-ambiguous', nid, rule)
            continue
        b = read(f['path'])
        out = os.path.join(outdir, f['path'].replace('/', '_'))
        with open(out, 'wb') as fh:
            fh.write(b)
        with open(out, 'rb') as fh:
            written = sha256_hex(fh.read())
        ok = written == f['sha256']
        print('  primary.%s -> node %s -> %s via %s' % (slot, nid, f['path'], rule))
        print('    wrote %s (%d bytes)\n    declared sha256 %s\n    on-disk  sha256 %s  %s'
              % (out, len(b), f['sha256'], written, 'MATCH' if ok else 'MISMATCH'))
        results.append((slot, nid, f['path'], out, f['sha256'], written, ok))
        if not ok:
            report('error', 'extract-hash-mismatch', out, 'written bytes differ from declared')

    errors = [r for r in REPORT if r[0] == 'error']
    print('\n== summary: signature %s; %d report entries (%d error, %d warn, %d info); %d dead node(s): %s'
          % (sig_state, len(REPORT), len(errors), sum(r[0] == 'warn' for r in REPORT),
             sum(r[0] == 'info' for r in REPORT), len(dead), ', '.join(sorted(dead)) or 'none'))
    return 1 if errors else 0


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)

    def flush(self):
        for st in self.streams:
            st.flush()


if __name__ == '__main__':
    outdir = sys.argv[2] if len(sys.argv) > 2 else 'extracted'
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, 'reader-log.txt'), 'w', encoding='utf-8') as log:
        sys.stdout = Tee(sys.__stdout__, log)
        rc = main(sys.argv)
        sys.stdout = sys.__stdout__
    sys.exit(rc)
