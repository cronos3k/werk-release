#!/usr/bin/env python3
"""werk_reader.py - a reader for .werk packages, written only from the spec
that travels inside the package (spec/README.md, spec/MINI-SPECS.md,
spec/SPEC.md, spec/layouts/*.layout.txt).

usage: python -I werk_reader.py <package.werk> [--out DIR]

What it does, in SPEC.md section 10 checklist order:
  1. opens the store-mode zip by hand (MINI-SPECS 5: EOCD -> central dir ->
     local headers), detects and refuses zip64 (5.5), checks CRC-32 (6)
  2. reads MANIFEST.json strictly (UTF-8, no BOM, no duplicate keys, no NaN)
     and checks structurally what it uses
  3. checks every convention value against the set this reader supports
  4. verifies SIGNATURE.json's chain (SPEC 6, MINI-SPECS 12/12.1) with a
     stdlib-only Ed25519 verifier, proven first against the spec's vectors
  5/6. walks nodes[], takes the active version, checks size + sha256 of every
     file; also license.sha256, spec_sha256, input_hash where inputs exist
  7. dispatches by type for a structural look: GLB, WAV, PNG, WKRP envelope
  8. reports unknown types / dangling edges instead of guessing
  9. never follows a path not declared in some files[]
and finally extracts primary.mesh and primary.sound, resolving each node's
payload with SPEC 2.1's ordered rules (payload_file first, never files[0]).

Only the Python standard library is used. Nothing from inside the package is
executed.
"""
import hashlib
import json
import os
import struct
import sys
import zlib

# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

REPORT = []


def report(code, severity, subject, detail=''):
    REPORT.append((severity, code, subject, detail))


# --------------------------------------------------------------------------
# 1. container: store-mode zip (MINI-SPECS 5)
# --------------------------------------------------------------------------

class ContainerRefused(Exception):
    pass


def u16(b, o):
    return struct.unpack_from('<H', b, o)[0]


def u32(b, o):
    return struct.unpack_from('<I', b, o)[0]


def open_zip(buf):
    """Return {name: entry} from the central directory. MINI-SPECS 5.1-5.5."""
    size = len(buf)
    if size < 22:
        raise ContainerRefused('not a zip: shorter than an EOCD record')
    eocd = -1
    first = size - 22
    lowest = max(0, size - 22 - 65535)
    for off in range(first, lowest - 1, -1):
        if buf[off:off + 4] == b'PK\x05\x06':
            # the comment must end exactly at end of file
            if off + 22 + u16(buf, off + 20) == size:
                eocd = off
                break
    if eocd < 0:
        raise ContainerRefused('not a zip: no EOCD record found')
    n_disk, cd_disk, n_here, n_total, cd_size, cd_off = struct.unpack_from('<HHHHII', buf, eocd + 4)
    # 5.5 zip64 detection is normative even for a zip32-only reader
    if (n_here == 0xFFFF or n_total == 0xFFFF or cd_size == 0xFFFFFFFF or cd_off == 0xFFFFFFFF
            or (eocd >= 20 and buf[eocd - 20:eocd - 16] == b'PK\x06\x07')):
        report('zip64-unsupported', 'error', '<container>', 'zip64 container; this reader is zip32-only')
        raise ContainerRefused('zip64-unsupported')
    if n_disk != 0 or cd_disk != 0 or n_here != n_total:
        raise ContainerRefused('multi-disk zip')
    if cd_off + cd_size > eocd:
        raise ContainerRefused('central directory overruns EOCD')
    entries = {}
    order = []
    p = cd_off
    for _ in range(n_total):
        if buf[p:p + 4] != b'PK\x01\x02':
            raise ContainerRefused(f'bad central directory signature at {p}')
        flags, method = struct.unpack_from('<HH', buf, p + 8)
        crc, csize, usize, nlen, mlen, klen = struct.unpack_from('<IIIHHH', buf, p + 16)
        lho = u32(buf, p + 42)
        raw_name = buf[p + 46:p + 46 + nlen]
        name = raw_name.decode('utf-8') if flags & 0x800 else raw_name.decode('cp437')
        p += 46 + nlen + mlen + klen
        if csize == 0xFFFFFFFF or usize == 0xFFFFFFFF or lho == 0xFFFFFFFF:
            report('zip64-unsupported', 'error', name, 'zip64 entry sentinel')
            raise ContainerRefused('zip64-unsupported')
        # 5.4 name rules
        if name.startswith('/') or '\\' in name or ':' in name or '..' in name.split('/'):
            report('zip-name-illegal', 'error', name, 'absolute, drive-lettered or .. path; entry ignored')
            continue
        if name in entries:
            report('zip-duplicate-name', 'error', name, 'two central directory entries share a name')
            continue
        if flags & 0x8:
            report('zip-data-descriptor', 'warn', name, 'flag bit 3 set (werk writers MUST NOT)')
        # local header: re-read n and m from it (5.3)
        if buf[lho:lho + 4] != b'PK\x03\x04':
            report('zip-local-header-bad', 'error', name, f'no local header at {lho}')
            continue
        ln, lm = u16(buf, lho + 26), u16(buf, lho + 28)
        data_off = lho + 30 + ln + lm
        e = dict(name=name, method=method, crc=crc, csize=csize, usize=usize,
                 data_off=data_off, header_off=lho, flags=flags)
        entries[name] = e
        order.append(name)
    return entries, order


def entry_bytes(buf, e):
    """Bytes of one entry, or None with a report. Method 0 only (5.3)."""
    if e['method'] != 0:
        report('zip-method-unsupported', 'error', e['name'],
               f'compression method {e["method"]}; this reader supports store (0) only')
        return None
    data = buf[e['data_off']:e['data_off'] + e['csize']]
    if len(data) != e['csize'] or e['csize'] != e['usize']:
        report('zip-truncated', 'error', e['name'], 'entry data runs past end of file')
        return None
    if (zlib.crc32(data) & 0xFFFFFFFF) != e['crc']:
        report('zip-crc-mismatch', 'error', e['name'], 'CRC-32 of stored bytes disagrees with zip header')
    return data


# --------------------------------------------------------------------------
# 2. strict JSON (MINI-SPECS 2, 3)
# --------------------------------------------------------------------------

class StrictJSONError(ValueError):
    pass


def _no_dupes(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise StrictJSONError(f'duplicate object key {k!r}')
        d[k] = v
    return d


def _no_const(c):
    raise StrictJSONError(f'non-finite number {c}')


def strict_json(data):
    if data.startswith(b'\xef\xbb\xbf'):
        raise StrictJSONError('UTF-8 BOM present (must reject, not strip)')
    text = data.decode('utf-8')  # strict: raises on invalid UTF-8
    return json.loads(text, object_pairs_hook=_no_dupes, parse_constant=_no_const)


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
        if v == int(v) and abs(v) < 2 ** 53:
            return str(int(v))
        return repr(v)
    raise TypeError(type(v))


def sha256_hex(b):
    return hashlib.sha256(b).hexdigest()


# --------------------------------------------------------------------------
# 4. Ed25519 verification (MINI-SPECS 12), stdlib only
# --------------------------------------------------------------------------

P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493


def _inv(a):
    return pow(a, P - 2, P)


D = (-121665 * _inv(121666)) % P
D2 = (2 * D) % P
I = pow(2, (P - 1) // 4, P)


def _recover_x(y, sign):
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
    return x


def _decompress(b32):
    if len(b32) != 32:
        return None
    n = int.from_bytes(b32, 'little')
    y = n & ((1 << 255) - 1)
    sign = n >> 255
    if y >= P:
        return None
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, (x * y) % P)


def _add(p1, p2):
    X1, Y1, Z1, T1 = p1
    X2, Y2, Z2, T2 = p2
    A = (Y1 - X1) * (Y2 - X2) % P
    B = (Y1 + X1) * (Y2 + X2) % P
    C = T1 * D2 * T2 % P
    Dd = Z1 * 2 * Z2 % P
    E, F, G, H = B - A, Dd - C, Dd + C, B + A
    return (E * F % P, G * H % P, F * G % P, E * H % P)


def _mul(s, pt):
    q = (0, 1, 1, 0)  # neutral element
    while s > 0:
        if s & 1:
            q = _add(q, pt)
        pt = _add(pt, pt)
        s >>= 1
    return q


def _eq(p1, p2):
    return (p1[0] * p2[2] - p2[0] * p1[2]) % P == 0 and (p1[1] * p2[2] - p2[1] * p1[2]) % P == 0


_By = (4 * _inv(5)) % P
BASE = (_recover_x(_By, 0), _By, 1, (_recover_x(_By, 0) * _By) % P)


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


def ed25519_self_test():
    """The spec's own vectors (MINI-SPECS 12 and 12.1)."""
    ok1 = ed25519_verify(
        bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a'), b'',
        bytes.fromhex('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b'))
    bad = ed25519_verify(
        bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a'), b'x',
        bytes.fromhex('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b'))
    msg = sig_message('c421d2e85a9455f0be794ca8ee673f727a7ef67485d631e374f95c4a6d6ce61a', '0' * 64,
                      '2026-08-08T09:00:00Z', 'urn:werk:fixture:rfc8032-vector-1', 'service')
    ok_msg = len(msg) == 203 and sha256_hex(msg) == '11e260cc16bc454f39f1aa6d56679c868ba1e83d33e3c22a462040b32a92165a'
    ok2 = ed25519_verify(
        bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a'), msg,
        bytes.fromhex('55720b6fc38d680f8ca7523c0d8cec5045c7247f7158ab54eafd03d6ea0eedb1'
                      'aeb4902b4704a5c2e78d7713b375068748bea4fd116a2d3a49f6010074c6410d'))
    return ok1 and not bad and ok_msg and ok2


def sig_message(manifest_sha256, prev, signed_at, uri, kind):
    return '\n'.join(['werk-sig/1', manifest_sha256, prev, signed_at, uri, kind]).encode('utf-8')


def verify_signature(sig_bytes, manifest_bytes):
    """Returns one of the four fixed tokens (SPEC 10 step 4)."""
    if sig_bytes is None:
        report('signature-absent', 'warn', 'SIGNATURE.json', 'no signature chain: anonymous package')
        return 'absent'
    if not ed25519_self_test():
        report('signature-unverified', 'warn', 'SIGNATURE.json', 'Ed25519 self-test failed; not checking')
        return 'unverified'
    try:
        sig = strict_json(sig_bytes)
        chain = sig['chain']
        if sig.get('algorithm') != 'ed25519' or not chain:
            report('signature-unverified', 'warn', 'SIGNATURE.json', 'unsupported algorithm or empty chain')
            return 'unverified'
    except Exception as ex:
        report('signature-unverified', 'warn', 'SIGNATURE.json', f'cannot parse: {ex}')
        return 'unverified'
    actual = sha256_hex(manifest_bytes)
    prev_sig = None
    for i, ent in enumerate(chain):
        try:
            expect_prev = '0' * 64 if i == 0 else sha256_hex(prev_sig.encode('utf-8'))
            msg = sig_message(ent['manifest_sha256'], ent['prev_entry_sha256'], ent['signed_at'],
                              ent['signer']['uri'], ent['signer']['kind'])
            good = ed25519_verify(bytes.fromhex(ent['public_key']), msg, bytes.fromhex(ent['signature']))
        except Exception as ex:
            report('signature-unverified', 'warn', 'SIGNATURE.json', f'chain[{i}] unreadable: {ex}')
            return 'unverified'
        if ent['prev_entry_sha256'] != expect_prev:
            report('signature-invalid', 'error', 'SIGNATURE.json', f'chain[{i}] prev_entry_sha256 does not link')
            return 'present-and-invalid'
        if not good:
            report('signature-invalid', 'error', 'SIGNATURE.json', f'chain[{i}] Ed25519 signature fails')
            return 'present-and-invalid'
        prev_sig = ent['signature']
    if chain[-1]['manifest_sha256'] != actual:
        report('signature-invalid', 'error', 'SIGNATURE.json',
               f'last link signs manifest {chain[-1]["manifest_sha256"]}, present MANIFEST.json is {actual}')
        return 'present-and-invalid'
    if sig.get('manifest_sha256') != actual:
        report('signature-invalid', 'error', 'SIGNATURE.json', 'top-level manifest_sha256 disagrees with the anchor')
        return 'present-and-invalid'
    report('signature-valid', 'info', 'SIGNATURE.json',
           f'{len(chain)} link(s) verify; signer {chain[-1]["signer"]["uri"]} (no external root of trust)')
    return 'signed-and-valid'


# --------------------------------------------------------------------------
# 3. conventions this reader supports (it implements exactly these values)
# --------------------------------------------------------------------------

SUPPORTED_PROFILES = {'3d-entity/1'}
SUPPORTED_CONVENTIONS = {
    'endianness': 'le', 'units_per_meter': 1.0, 'length_unit': 'metre', 'angle_unit': 'radian',
    'time_unit': 'second', 'mass_unit': 'kilogram', 'up_axis': 'y', 'forward_axis': '-z',
    'right_axis': '+x', 'handedness': 'right', 'winding': 'ccw', 'quat_order': 'wxyz',
    'oct_encoding_pole': 'y', 'sh_l1_order': ['dc', 'y', 'z', 'x'], 'color_space_default': 'srgb',
    'uv_origin': 'top-left', 'alignment_bytes': 16, 'text_encoding': 'utf-8', 'id_case': 'kebab-case',
    'hash_algorithm': 'sha256', 'signature_algorithm': 'ed25519',
}

# One line per node type, from spec/README.md's table and SPEC.md section 3.
TYPE_MEANING = {
    'core.spec': 'the format specification travelling inside the file (law 2)',
    'core.loader': 'an embedded single-file reader program (inert data here; never executed)',
    'core.license': 'full licence text, embedded',
    'core.readme': 'one page for a human',
    'core.geom.source': 'archival master geometry (GLB)',
    'core.geom.game': 'runtime/game mesh (GLB) - the renderable mesh',
    'core.geom.lod': 'a level-of-detail mesh (GLB)',
    'core.tex': 'texture (PNG)',
    'core.material': 'PBR material parameters (JSON)',
    'core.imposter': 'octahedral imposter atlases (PNG + JSON)',
    'core.phys.colliders': 'collision shapes (JSON)',
    'core.phys.bounds': 'measured bounding volumes (JSON)',
    'core.phys.body': 'mass / centre of mass / inertia (JSON)',
    'core.field.flow': 'flow field + SDF grid (WKFF envelope)',
    'core.pose.rest': 'settled rest orientations from a drop simulation (WKRP envelope)',
    'core.skeleton': 'rig (JSON + WKSK mirror)',
    'core.anim.clip': 'animation clip (WKAC envelope + JSON)',
    'core.audio.package': 'the audio set descriptor (JSON)',
    'core.audio.effect': 'one sound effect: WAV takes + JSON sidecar',
    'core.audio.ambience': 'ambience sound: WAV + JSON sidecar',
    'core.destruct': 'fracture set (GLB + JSON)',
    'core.props': 'simulation properties (JSON)',
    'core.semantics': 'facet tags, palette and search text (JSON)',
    'core.provenance': 'who made what, from what (JSON)',
    'core.recipe': 'reproduction record (JSON)',
    'core.disclosure': 'machine-readable disclosure facts (JSON)',
    'core.embedding': 'style embedding + palette (WKEM envelope)',
    'core.geom.points': 'point cloud (WKPC envelope)',
    'core.geom.gsplat': '3D Gaussian splat (WKGS envelope)',
    'core.tool': 'embedded tool (JSON + source)',
    'core.tool.config': 'tool configuration (JSON)',
}

PAYLOAD_ROLE = {'core.audio.effect': 'best', 'core.audio.ambience': 'best',
                'core.imposter': 'atlas', 'core.recipe': 'record'}


def resolve_payload(node, version):
    """SPEC 2.1, normative order. Never files[0]."""
    files = version.get('files', [])
    paths = [f['path'] for f in files]
    pf = version.get('payload_file')
    if pf is not None:
        if paths.count(pf) == 1:
            return pf, 'payload_file'
        report('payload-file-invalid', 'warn', node['node_id'], f'payload_file {pf!r} not exactly one of files[]')
    if len(files) == 1:
        return paths[0], 'single file'
    marked = [f['path'] for f in files if f.get('role') == 'payload']
    if len(marked) == 1:
        return marked[0], 'role=payload'
    role = PAYLOAD_ROLE.get(node['type'])
    if role:
        hits = [f['path'] for f in files if f.get('role') == role]
        if len(hits) == 1:
            return hits[0], f'type payload role {role}'
    report('payload-file-ambiguous', 'warn', node['node_id'], f'candidates: {paths}')
    return None, None


# --------------------------------------------------------------------------
# 7. structural looks at payload encodings (MINI-SPECS 8-10, ENVELOPE)
# --------------------------------------------------------------------------

def describe_glb(b):
    if b[:4] != b'glTF':
        return None, 'not a GLB (bad magic)'
    ver, total = u32(b, 4), u32(b, 8)
    if ver != 2 or total != len(b):
        return None, f'GLB version {ver}, declared length {total} vs actual {len(b)}'
    off, js, binlen = 12, None, 0
    while off + 8 <= len(b):
        clen, ctype = u32(b, off), u32(b, off + 4)
        chunk = b[off + 8:off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(chunk.decode('utf-8'))
        elif ctype == 0x004E4942:
            binlen = clen
        off += 8 + clen
    if js is None:
        return None, 'GLB has no JSON chunk'
    tris = verts = 0
    attrs = set()
    for m in js.get('meshes', []):
        for prim in m.get('primitives', []):
            if prim.get('mode', 4) != 4:
                report('glb-nonconformant', 'warn', 'geom', 'primitive mode is not 4 (triangles)')
            attrs |= set(prim.get('attributes', {}))
            if 'indices' in prim:
                tris += js['accessors'][prim['indices']]['count'] // 3
            else:
                report('glb-nonconformant', 'warn', 'geom', 'non-indexed primitive (SPEC 3.10)')
            pos = prim.get('attributes', {}).get('POSITION')
            if pos is not None:
                verts += js['accessors'][pos]['count']
    info = dict(meshes=len(js.get('meshes', [])), vertices=verts, triangles=tris,
                attributes=sorted(attrs), bin_bytes=binlen, generator=js.get('asset', {}).get('generator'))
    return info, None


def describe_wav(b):
    if b[:4] != b'RIFF' or b[8:12] != b'WAVE':
        return None, 'not a RIFF/WAVE file'
    off, fmt, data_len = 12, None, None
    while off + 8 <= len(b):
        cid, csz = b[off:off + 4], u32(b, off + 4)
        if cid == b'fmt ':
            fmt = struct.unpack_from('<HHIIHH', b, off + 8)
        elif cid == b'data':
            data_len = csz
        off += 8 + csz + (csz & 1)
    if fmt is None or data_len is None:
        return None, 'WAV missing fmt or data chunk'
    af, ch, sr, br, ba, bits = fmt
    frames = data_len // ba if ba else 0
    return dict(format={1: 'PCM', 3: 'IEEE float', 0xFFFE: 'extensible'}.get(af, af), channels=ch,
                sample_rate_hz=sr, bits=bits, frames=frames,
                duration_s=round(frames / sr, 4) if sr else None), None


def describe_png(b):
    if b[:8] != b'\x89PNG\r\n\x1a\n':
        return None, 'not a PNG'
    off, bad_crc, ihdr = 8, 0, None
    while off + 12 <= len(b):
        ln = struct.unpack_from('>I', b, off)[0]
        typ = b[off + 4:off + 8]
        data = b[off + 8:off + 8 + ln]
        crc = struct.unpack_from('>I', b, off + 8 + ln)[0]
        if zlib.crc32(typ + data) & 0xFFFFFFFF != crc:
            bad_crc += 1
        if typ == b'IHDR':
            ihdr = struct.unpack('>IIBBBBB', data)
        off += 12 + ln
        if typ == b'IEND':
            break
    if ihdr is None:
        return None, 'PNG without IHDR'
    w, h, depth, ctype, _, _, interlace = ihdr
    return dict(width=w, height=h, bit_depth=depth, colour_type=ctype, interlace=interlace,
                chunk_crc_errors=bad_crc), (f'{bad_crc} PNG chunk CRC error(s)' if bad_crc else None)


def mp_decode(b, o=0):
    """MessagePack subset of ENVELOPE.layout.txt section 4. Big-endian inside."""
    t = b[o]
    if t <= 0x7f:
        return t, o + 1
    if t >= 0xe0:
        return t - 256, o + 1
    if 0xa0 <= t <= 0xbf:
        n = t & 0x1f
        return b[o + 1:o + 1 + n].decode('utf-8'), o + 1 + n
    if 0x90 <= t <= 0x9f:
        return _mp_arr(b, o + 1, t & 0x0f)
    if 0x80 <= t <= 0x8f:
        return _mp_map(b, o + 1, t & 0x0f)
    fixed = {0xcc: '>B', 0xcd: '>H', 0xce: '>I', 0xcf: '>Q', 0xd0: '>b', 0xd1: '>h', 0xd2: '>i',
             0xd3: '>q', 0xca: '>f', 0xcb: '>d'}
    if t in fixed:
        f = fixed[t]
        return struct.unpack_from(f, b, o + 1)[0], o + 1 + struct.calcsize(f)
    if t == 0xc0:
        return None, o + 1
    if t == 0xc2:
        return False, o + 1
    if t == 0xc3:
        return True, o + 1
    lens = {0xd9: '>B', 0xda: '>H', 0xdb: '>I', 0xc4: '>B', 0xc5: '>H', 0xc6: '>I'}
    if t in lens:
        f = lens[t]
        n = struct.unpack_from(f, b, o + 1)[0]
        s = o + 1 + struct.calcsize(f)
        raw = b[s:s + n]
        return (raw.decode('utf-8') if t in (0xd9, 0xda, 0xdb) else raw), s + n
    if t in (0xdc, 0xdd):
        f = '>H' if t == 0xdc else '>I'
        return _mp_arr(b, o + 1 + struct.calcsize(f), struct.unpack_from(f, b, o + 1)[0])
    if t in (0xde, 0xdf):
        f = '>H' if t == 0xde else '>I'
        return _mp_map(b, o + 1 + struct.calcsize(f), struct.unpack_from(f, b, o + 1)[0])
    raise ValueError(f'banned or unknown MessagePack byte 0x{t:02x} at {o}')


def _mp_arr(b, o, n):
    out = []
    for _ in range(n):
        v, o = mp_decode(b, o)
        out.append(v)
    return out, o


def _mp_map(b, o, n):
    out = {}
    for _ in range(n):
        k, o = mp_decode(b, o)
        v, o = mp_decode(b, o)
        if k in out:
            raise ValueError(f'duplicate header key {k!r}')
        out[k] = v
    return out, o


DTYPE_SIZE = {'u8': 1, 'i8': 1, 'u16': 2, 'i16': 2, 'u32': 4, 'i32': 4, 'u64': 8, 'i64': 8, 'f32': 4, 'f64': 8}
MAGIC_KIND = {b'WKFF': 'core.field.flow', b'WKRP': 'core.pose.rest', b'WKAC': 'core.anim.clip',
              b'WKSK': 'core.skeleton', b'WKEM': 'core.embedding', b'WKPC': 'core.geom.points',
              b'WKGS': 'core.geom.gsplat'}


def read_envelope(b):
    """ENVELOPE.layout.txt section 7, the normative reference reader."""
    magic = b[0:4]
    version, hlen = u32(b, 4), u32(b, 8)
    assert 12 + hlen <= len(b), 'header overruns file'
    header, end = mp_decode(b[12:12 + hlen])
    assert end == hlen, 'header length disagrees with MessagePack content'
    assert header['endianness'] == 'le', 'endianness not le'
    assert MAGIC_KIND.get(magic) == header['kind'], f'magic {magic!r} vs kind {header["kind"]}'
    P_ = 16 * -(-(12 + hlen) // 16)
    assert header['payload_origin'] == P_, 'payload_origin disagrees'
    assert P_ + header['payload_size'] == len(b), 'payload_size disagrees with file size'
    secs = {}
    prev_end = P_
    for s in header['sections']:
        assert s['offset'] % 16 == 0, f'section {s["name"]} misaligned'
        assert prev_end <= s['offset'] < prev_end + 16 or (s['size'] == 0), f'section {s["name"]} gap/order'
        assert s['offset'] + s['size'] <= len(b), f'section {s["name"]} overruns'
        esz = DTYPE_SIZE.get(s['dtype']) or s['stride']
        prod = 1
        if s['stride'] == esz:
            for d in s['shape']:
                prod *= d
            assert s['size'] == s['stride'] * prod, f'section {s["name"]} size rule'
        else:
            assert s['stride'] >= esz * s['shape'][-1], f'section {s["name"]} stride rule'
            for d in s['shape'][:-1]:
                prod *= d
            assert s['size'] == s['stride'] * prod, f'section {s["name"]} size rule'
        secs[s['name']] = b[s['offset']:s['offset'] + s['size']]
        prev_end = s['offset'] + s['size']
    assert 16 * -(-prev_end // 16) == len(b), 'trailing data after last section'
    return magic, version, header, secs


def describe_wkrp(b):
    magic, version, h, secs = read_envelope(b)
    poses = []
    raw = secs['poses']
    for i in range(h['pose_count']):
        w, x, y, z, cf, cc, prob, area = struct.unpack_from('<ffffIIff', raw, 32 * i)
        poses.append(dict(quat_wxyz=[round(w, 5), round(x, 5), round(y, 5), round(z, 5)],
                          contacts=cc, probability=round(prob, 4), support_area_m2=round(area, 4)))
    checks = []
    if sum(p['contacts'] for p in poses) != h['contact_count']:
        checks.append('contact_count sum mismatch')
    if any(poses[i]['probability'] < poses[i + 1]['probability'] for i in range(len(poses) - 1)):
        checks.append('entries not sorted by probability descending')
    if h.get('trials', 0) > 0 and abs(sum(p['probability'] for p in poses) - 1.0) > 1e-3:
        checks.append('probabilities do not sum to 1')
    return dict(version=version, pose_count=h['pose_count'], contact_count=h['contact_count'],
                trials=h.get('trials'), most_likely=poses[0] if poses else None), checks


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    out_dir = argv[argv.index('--out') + 1] if '--out' in argv else 'extracted'
    buf = open(path, 'rb').read()
    print(f'werk_reader: {path} ({len(buf)} bytes)')
    print(f'sha256 of container: {sha256_hex(buf)}')

    # 1. container
    try:
        entries, order = open_zip(buf)
    except ContainerRefused as ex:
        report('container-refused', 'error', '<container>', str(ex))
        return finish(2)
    print(f'\n[1] container: zip, {len(entries)} entries, all methods: '
          f'{sorted(set(e["method"] for e in entries.values()))}')
    blobs = {}
    for name in order:
        blobs[name] = entry_bytes(buf, entries[name])

    # 2. manifest
    mbytes = blobs.get('MANIFEST.json')
    if mbytes is None:
        report('manifest-missing', 'error', 'MANIFEST.json', 'missing or unreadable')
        return finish(2)
    try:
        man = strict_json(mbytes)
        assert isinstance(man.get('nodes'), list) and isinstance(man.get('werk'), dict)
    except Exception as ex:
        report('manifest-unparseable', 'error', 'MANIFEST.json', str(ex))
        return finish(2)
    print(f'[2] MANIFEST.json: {len(mbytes)} bytes, sha256 {sha256_hex(mbytes)}')
    print(f'    werk {man["werk"].get("major")}.{man["werk"].get("minor")}, profile {man.get("profile")!r}')
    ent = man.get('entity', {})
    print(f'    entity: {ent.get("name")} ({ent.get("uuid")})')
    if man['werk'].get('major') != 1:
        report('unsupported-major', 'error', 'MANIFEST.json', f'werk.major {man["werk"].get("major")}')
    profile_ok = man.get('profile') in SUPPORTED_PROFILES
    if not profile_ok:
        report('unsupported-profile', 'warn', 'MANIFEST.json', f'profile {man.get("profile")!r}')

    # 3. conventions
    conv = man.get('conventions', {})
    if profile_ok:
        bad = [k for k, v in SUPPORTED_CONVENTIONS.items() if conv.get(k) != v]
        for k in bad:
            report('unsupported-convention', 'error', 'conventions', f'{k} = {conv.get(k)!r}')
        print(f'[3] conventions: {len(SUPPORTED_CONVENTIONS) - len(bad)}/{len(SUPPORTED_CONVENTIONS)} supported'
              + (f'; unsupported: {bad}' if bad else ''))
    cont = man.get('container', {})
    if cont.get('zip_compression') != 'store':
        report('container-note', 'info', 'container', f'zip_compression {cont.get("zip_compression")!r}')

    # 4. signature
    sig_state = verify_signature(blobs.get('SIGNATURE.json') if 'SIGNATURE.json' in entries else None, mbytes)
    print(f'[4] signature: {sig_state}')

    # 5/6. nodes and files
    nodes = man['nodes']
    by_id = {}
    for n in nodes:
        if n['node_id'] in by_id:
            report('duplicate-node-id', 'error', n['node_id'], '')
        by_id[n['node_id']] = n
    declared = {}   # path -> (sha256, size)
    owner = {}      # path -> node_id
    dead = set()
    hash_rows = []
    active_version = {}
    for n in nodes:
        nid = n['node_id']
        vers = {v['v']: v for v in n.get('versions', [])}
        av = vers.get(n.get('active'))
        if av is None:
            older = [v for k, v in sorted(vers.items(), reverse=True)]
            av = older[0] if older else None
            report('active-version-invalid', 'warn', nid, f'active={n.get("active")}; fell back to v{av and av["v"]}')
        if av is None:
            dead.add(nid)
            continue
        active_version[nid] = av
        for v in vers.values():
            for f in v.get('files', []):
                p = f['path']
                if p in owner and owner[p] != nid:
                    report('file-claimed-twice', 'error', p, f'by {owner[p]} and {nid}')
                owner[p] = nid
                if p in declared and declared[p] != (f['sha256'], f['size']):
                    report('file-redeclared-differently', 'error', p, nid)
                declared[p] = (f['sha256'], f['size'])
        for f in av.get('files', []):
            p = f['path']
            data = blobs.get(p) if p in entries else None
            if p not in entries:
                report('file-missing', 'error', p, f'declared by {nid}, not in container')
                dead.add(nid)
                hash_rows.append((nid, p, f['sha256'], None, 'MISSING'))
                continue
            if data is None:
                dead.add(nid)
                hash_rows.append((nid, p, f['sha256'], None, 'UNREADABLE'))
                continue
            got = sha256_hex(data)
            status = 'ok'
            if len(data) != f['size']:
                report('size-mismatch', 'error', p, f'declared {f["size"]}, actual {len(data)}')
                status = 'SIZE'
                dead.add(nid)
            if got != f['sha256']:
                report('hash-mismatch', 'error', p, f'declared {f["sha256"]}, computed {got}')
                status = 'HASH' if status == 'ok' else status + '+HASH'
                dead.add(nid)
            hash_rows.append((nid, p, f['sha256'], got, status))

    # license.sha256 and spec_sha256 (SPEC 2)
    lic = man.get('license', {})
    if lic.get('file') in blobs and blobs[lic['file']] is not None:
        got = sha256_hex(blobs[lic['file']])
        hash_rows.append(('<license>', lic['file'], lic.get('sha256'), got,
                          'ok' if got == lic.get('sha256') else 'HASH'))
        if got != lic.get('sha256'):
            report('hash-mismatch', 'error', 'license.sha256', got)
    spec_paths = sorted((p for p in declared if p.startswith('spec/')), key=lambda s: s.encode('utf-8'))
    acc = b''.join(p.encode('utf-8') + b'\n' + bytes.fromhex(declared[p][0]) + b'\n' for p in spec_paths)
    spec_got = sha256_hex(acc)
    hash_rows.append(('<spec_sha256>', f'{len(spec_paths)} spec/ files', man.get('spec_sha256'), spec_got,
                      'ok' if spec_got == man.get('spec_sha256') else 'HASH'))
    if spec_got != man.get('spec_sha256'):
        report('spec-sha256-mismatch', 'error', 'spec_sha256', f'computed {spec_got}')

    # input_hash (MINI-SPECS 11, "What gets hashed")
    for nid, av in active_version.items():
        if 'input_hash' not in av:
            continue
        ins = av.get('input_files', [])
        missing = [p for p in ins if p not in declared]
        if missing:
            report('input-hash-uncheckable', 'info', nid, f'inputs not in this package: {missing}')
            hash_rows.append((nid, 'input_hash', av['input_hash'], None, 'inputs absent'))
            continue
        h = hashlib.sha256()
        for p in ins:
            h.update(bytes.fromhex(declared[p][0]))
        h.update(canonical_json(av.get('input_params') or {}).encode('utf-8'))
        got = h.hexdigest()
        st = 'ok' if got == av['input_hash'] else 'STALE'
        hash_rows.append((nid, 'input_hash', av['input_hash'], got, st))
        if st != 'ok':
            report('input-hash-stale', 'warn', nid, f'computed {got}')

    # nothing floats (SPEC 2)
    for name in order:
        if name.endswith('/') or name in ('MANIFEST.json', 'SIGNATURE.json'):
            continue
        if name not in declared:
            report('file-floating', 'warn', name, 'in container but in no node files[]; ignored')

    # edges; propagate requires-into-dead (SPEC 5)
    for n in nodes:
        for e in n.get('edges', []):
            if e['to'] not in by_id:
                sev = 'warn' if e['kind'] == 'requires' else 'info'
                report('edge-dangling', sev, n['node_id'],
                       f'{e["kind"]} edge (role {e.get("role")}) to {e["to"]!r}, which is not in this package')
    changed = True
    while changed:
        changed = False
        for n in nodes:
            if n['node_id'] in dead:
                continue
            for e in n.get('edges', []):
                if e['kind'] == 'requires' and e['to'] in dead:
                    dead.add(n['node_id'])
                    report('node-dead-requires', 'error', n['node_id'], f'requires dead node {e["to"]}')
                    changed = True

    # 7/8. dispatch by type for a structural look
    details = {}
    for n in nodes:
        nid, typ = n['node_id'], n['type']
        av = active_version.get(nid)
        if av is None or nid in dead:
            continue
        if typ not in TYPE_MEANING:
            if typ.startswith('x.'):
                report('node-extension', 'info', nid, f'extension type {typ}: listed and hash-checked, not interpreted')
            else:
                report('node-skipped-unknown-type', 'warn', nid, typ)
        for f in av['files']:
            p, b = f['path'], blobs.get(f['path'])
            if b is None:
                continue
            try:
                if p.endswith('.glb'):
                    info, err = describe_glb(b)
                elif p.endswith('.wav'):
                    info, err = describe_wav(b)
                elif p.endswith('.png'):
                    info, err = describe_png(b)
                elif b[:4] in MAGIC_KIND and typ in MAGIC_KIND.values():
                    info, checks = describe_wkrp(b) if b[:4] == b'WKRP' else (None, [])
                    # ENVELOPE section 3: header input_hash "Mandatory for derived
                    # nodes; the manifest also carries it, and the two MUST agree"
                    hdr = read_envelope(b)[2]
                    if hdr.get('kind') != typ:
                        checks.append(f'envelope kind {hdr.get("kind")} != node type {typ}')
                    if 'input_hash' in av and hdr.get('input_hash') != av['input_hash']:
                        checks.append(f'envelope input_hash {hdr.get("input_hash")!r} != manifest {av["input_hash"]}')
                    hp, mp = hdr.get('producer') or {}, av.get('producer') or {}
                    if hp and (hp.get('tool'), hp.get('version')) != (mp.get('tool'), mp.get('version')):
                        checks.append(f'envelope producer {hp} != manifest producer {mp}')
                    err = '; '.join(checks) or None
                elif p.endswith('.json'):
                    strict_json(b)
                    info, err = None, None
                else:
                    info, err = None, None
            except AssertionError as ex:
                info, err = None, f'envelope-invalid: {ex}'
                report('envelope-invalid', 'error', nid, f'{p}: {ex}')
                dead.add(nid)
            except Exception as ex:
                info, err = None, f'{type(ex).__name__}: {ex}'
            if err:
                report('payload-structure', 'warn', nid, f'{p}: {err}')
            if info:
                details[p] = info

    # listing
    print(f'\n[5] node graph: {len(nodes)} nodes')
    for n in nodes:
        nid, typ = n['node_id'], n['type']
        av = active_version.get(nid, {})
        meaning = TYPE_MEANING.get(typ, 'extension node (x.*): meaning supplied by the extension'
                                   if typ.startswith('x.') else 'UNKNOWN type')
        state = 'DEAD' if nid in dead else 'live'
        print(f'  - {nid}  [{typ}]  {state}')
        print(f'      meaning : {meaning}')
        print(f'      version : v{av.get("v")} of {len(n.get("versions", []))}, epistemic={av.get("epistemic")}, '
              f'producer={av.get("producer", {}).get("tool")} {av.get("producer", {}).get("version")}')
        if av.get('note'):
            print(f'      note    : {av["note"]}')
        for f in av.get('files', []):
            extra = f' role={f["role"]}' if f.get('role') else ''
            print(f'      file    : {f["path"]} ({f["size"]} B){extra}')
            if f['path'] in details:
                print(f'                {details[f["path"]]}')
        for e in n.get('edges', []):
            here = '' if e['to'] in by_id else '   <- not in package'
            print(f'      edge    : {e["kind"]} -> {e["to"]} ({e.get("role")}){here}')

    print(f'\n[6] hashes ({len(hash_rows)} checks):')
    for nid, p, want, got, st in hash_rows:
        print(f'  {st:13s} {nid:32s} {p}')
    n_ok = sum(1 for r in hash_rows if r[4] == 'ok')
    print(f'  -> {n_ok} ok, {sum(1 for r in hash_rows if r[4] not in ("ok", "inputs absent"))} failed, '
          f'{sum(1 for r in hash_rows if r[4] == "inputs absent")} uncheckable (inputs not in package)')

    # extraction of primary mesh and sound
    print('\n[7] extraction:')
    prim = man.get('primary') or {}
    os.makedirs(out_dir, exist_ok=True)
    for slot in ('mesh', 'sound'):
        nid = prim.get(slot)
        if nid is None:
            # SPEC 2 fallback, reported
            want = 'core.geom.game' if slot == 'mesh' else 'core.audio.effect'
            cands = [n['node_id'] for n in nodes if n['type'] == want]
            nid = cands[0] if cands else None
            report('primary-fallback', 'warn', slot, f'no primary.{slot}; fell back to {nid}')
        if nid not in by_id:
            report('primary-unresolvable', 'error', slot, f'primary.{slot} = {nid!r} names no node')
            continue
        if nid in dead:
            report('primary-dead', 'error', slot, f'{nid} is dead; not extracting')
            continue
        av = active_version[nid]
        p, how = resolve_payload(by_id[nid], av)
        if p is None:
            continue
        data = blobs[p]
        want_sha = next(f['sha256'] for f in av['files'] if f['path'] == p)
        dest = os.path.join(out_dir, os.path.basename(p))
        with open(dest, 'wb') as fh:
            fh.write(data)
        got = sha256_hex(open(dest, 'rb').read())
        st = 'MATCH' if got == want_sha else 'MISMATCH'
        if st != 'MATCH':
            report('extract-hash-mismatch', 'error', dest, got)
        print(f'  primary.{slot} -> node {nid} -> {p} (resolved by {how})')
        print(f'    written : {dest} ({len(data)} bytes)')
        print(f'    declared: {want_sha}')
        print(f'    computed: {got}  {st}')
    return finish(None)


def finish(forced):
    print('\n[8] report:')
    for sev, code, subj, det in REPORT:
        print(f'  {sev:5s} {code:28s} {subj}: {det}')
    if forced is not None:
        status = forced
    else:
        status = 1 if any(r[0] == 'error' for r in REPORT) else 0
    print(f'\nexit status {status}')
    return status


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main(sys.argv))
