#!/usr/bin/env python3
"""werk_open.py - open a .werk package, list its node graph with meanings,
verify every declared hash (and the signature chain), and extract the primary
mesh and the primary sound to disk.

Every rule implemented here was taken from documents carried INSIDE the
package (spec/README.md, spec/SPEC.md, spec/MINI-SPECS.md,
spec/conventions-map.json, spec/schemas/manifest.schema.json). Section
references in comments point at those vendored files. Standard library only.

usage:  python werk_open.py PACKAGE.werk [OUTDIR]
exit:   0 = opened, no error entries; 1 = opened, >=1 error; 2 = container refused
        (SPEC.md 10.2)
"""
import hashlib
import json
import os
import re
import struct
import sys
import zlib

# --------------------------------------------------------------------------
# report (SPEC.md 10.2: every refusal is one entry with code, severity, subject)
# --------------------------------------------------------------------------
REPORT = []


def report(code, severity, subject, detail=''):
    if (code, severity, subject, detail) not in REPORT:
        REPORT.append((code, severity, subject, detail))


class ContainerRefused(Exception):
    pass


# --------------------------------------------------------------------------
# zip, store mode (MINI-SPECS.md 5). Written from the byte tables there rather
# than delegated to zipfile, so zip64 detection (5.5) and the method rule (5.3)
# are applied exactly as documented.
# --------------------------------------------------------------------------
def u16(b, o): return struct.unpack_from('<H', b, o)[0]
def u32(b, o): return struct.unpack_from('<I', b, o)[0]


class Zip:
    def __init__(self, path):
        with open(path, 'rb') as f:          # read-only; the package is never written
            self.data = f.read()
        d = self.data
        size = len(d)
        if size < 22:
            raise ContainerRefused('not-a-zip: shorter than an EOCD record')
        # 5.1: scan backwards from size-22 down to max(0, size-22-65535)
        eocd = -1
        for off in range(size - 22, max(0, size - 22 - 65535) - 1, -1):
            if d[off:off + 4] == b'PK\x05\x06' and off + 22 + u16(d, off + 20) == size:
                eocd = off
                break
        if eocd < 0:
            raise ContainerRefused('no-eocd: end of central directory not found')
        n_disk, n_total = u16(d, eocd + 8), u16(d, eocd + 10)
        cd_size, cd_off = u32(d, eocd + 12), u32(d, eocd + 16)
        # 5.5: zip64 must be recognised and, in this zip32 reader, refused
        if (0xFFFF in (n_disk, n_total) or 0xFFFFFFFF in (cd_size, cd_off)
                or (eocd >= 20 and d[eocd - 20:eocd - 16] == b'PK\x06\x07')):
            raise ContainerRefused('zip64-unsupported')
        self.entries = {}
        self.order = []
        p = cd_off
        for _ in range(n_total):
            if d[p:p + 4] != b'PK\x01\x02':
                raise ContainerRefused('central directory record signature missing at %d' % p)
            flags, method = u16(d, p + 8), u16(d, p + 10)
            crc, csize, usize = u32(d, p + 16), u32(d, p + 20), u32(d, p + 24)
            n, m, k = u16(d, p + 28), u16(d, p + 30), u16(d, p + 32)
            lho = u32(d, p + 42)
            name = d[p + 46:p + 46 + n].decode('utf-8' if flags & 0x800 else 'cp437')
            if name in self.entries:
                report('zip-duplicate-entry', 'error', name)
            self.entries[name] = dict(method=method, crc=crc, csize=csize,
                                      usize=usize, lho=lho, flags=flags)
            self.order.append(name)
            p += 46 + n + m + k
        for name in self.order:
            # 5.4: names are relative, forward slashes, no '..', no drive letter
            if name.startswith('/') or '\\' in name or '..' in name.split('/') or re.match(r'^[A-Za-z]:', name):
                report('zip-unsafe-name', 'error', name)

    def read(self, name):
        """Return the entry's bytes, or None (with a report entry) if unreadable."""
        e = self.entries.get(name)
        if e is None:
            return None
        d, o = self.data, e['lho']
        if d[o:o + 4] != b'PK\x03\x04':
            report('zip-local-header-invalid', 'error', name)
            return None
        n, m = u16(d, o + 26), u16(d, o + 28)   # 5.3: re-read n, m from the LOCAL header
        start = o + 30 + n + m
        raw = d[start:start + e['csize']]
        if e['method'] == 0:
            out = raw
        elif e['method'] == 8:                   # MINI-SPECS 7: raw deflate, stdlib zlib
            try:
                out = zlib.decompress(raw, -15)
            except zlib.error:
                report('zip-inflate-failed', 'error', name)
                return None
        else:
            report('zip-method-unsupported', 'error', name, 'method %d' % e['method'])
            return None
        if len(out) != e['usize'] or (zlib.crc32(out) & 0xFFFFFFFF) != e['crc']:
            report('zip-crc-mismatch', 'warn', name, 'zip CRC-32/size disagree; manifest sha256 decides')
        return out


def sha256(b): return hashlib.sha256(b).hexdigest()


# --------------------------------------------------------------------------
# JSON (MINI-SPECS.md 3): duplicate keys MUST be rejected, no NaN/Infinity.
# --------------------------------------------------------------------------
def _no_dupes(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError('duplicate key %r' % k)
        out[k] = v
    return out


def _no_const(x):
    raise ValueError('non-finite number %s' % x)


def parse_json(b):
    if b.startswith(b'\xef\xbb\xbf'):
        raise ValueError('BOM present')
    return json.loads(b.decode('utf-8'), object_pairs_hook=_no_dupes, parse_constant=_no_const)


def canonical_json(v):
    """MINI-SPECS 3 'Canonical JSON (for hashing only)'."""
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
        return ''.join(out) + '"'
    if v is True: return 'true'
    if v is False: return 'false'
    if v is None: return 'null'
    if isinstance(v, int): return str(v)
    if isinstance(v, float):
        # Ambiguity noted in REPORT.md: the spec does not say whether an
        # integral float (1.0) is "an integer". repr() is shortest round-trip.
        return repr(v)
    raise TypeError(type(v))


# --------------------------------------------------------------------------
# Ed25519 verify (MINI-SPECS.md 12), pure Python, verify only.
# --------------------------------------------------------------------------
P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
def _inv(a): return pow(a, P - 2, P)
D = (-121665 * _inv(121666)) % P
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


def _decode_point(b):
    if len(b) != 32:
        return None
    n = int.from_bytes(b, 'little')
    y, sign = n & ((1 << 255) - 1), n >> 255
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
    C = T1 * 2 * D * T2 % P
    Dd = Z1 * 2 * Z2 % P
    E, F, G, H = B - A, Dd - C, Dd + C, B + A
    return (E * F % P, G * H % P, F * G % P, E * H % P)


def _mul(s, pt):
    q = (0, 1, 1, 0)
    while s:
        if s & 1:
            q = _add(q, pt)
        pt = _add(pt, pt)
        s >>= 1
    return q


def _eq(p1, p2):
    return ((p1[0] * p2[2] - p2[0] * p1[2]) % P == 0 and
            (p1[1] * p2[2] - p2[1] * p1[2]) % P == 0)


_By = 4 * _inv(5) % P
BASE = (_recover_x(_By, 0), _By, 1, (_recover_x(_By, 0) * _By) % P)


def ed25519_verify(pub, msg, sig):
    if len(sig) != 64:
        return False
    A = _decode_point(pub)
    R = _decode_point(sig[:32])
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
    # MINI-SPECS 12: RFC 8032 test vector 1, empty message
    pub = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
    sig = bytes.fromhex('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b')
    ok = ed25519_verify(pub, b'', sig)
    bad = ed25519_verify(pub, b'x', sig)
    return ok and not bad


def sig_message(entry):
    """MINI-SPECS 12.1 / SPEC 6: six fields, LF-joined, no trailing LF."""
    fields = ['werk-sig/1', entry['manifest_sha256'], entry['prev_entry_sha256'],
              entry['signed_at'], entry['signer']['uri'], entry['signer']['kind']]
    for f in fields:
        if '\n' in f:
            raise ValueError('field contains LF')
    return '\n'.join(fields).encode('utf-8')


def verify_chain(sig_doc, manifest_bytes):
    """Returns one of the four fixed tokens (SPEC 10 step 4)."""
    chain = sig_doc.get('chain')
    if not isinstance(chain, list) or not chain:
        report('signature-invalid', 'error', 'SIGNATURE.json', 'empty or missing chain')
        return 'present-and-invalid'
    prev = '0' * 64
    for i, e in enumerate(chain):
        try:
            msg = sig_message(e)
            pub = bytes.fromhex(e['public_key'])
            sig = bytes.fromhex(e['signature'])
        except (KeyError, ValueError, TypeError) as ex:
            report('signature-invalid', 'error', 'SIGNATURE.json', 'chain[%d] malformed: %s' % (i, ex))
            return 'present-and-invalid'
        if e['prev_entry_sha256'] != prev:
            report('signature-invalid', 'error', 'SIGNATURE.json', 'chain[%d] prev_entry_sha256 mismatch' % i)
            return 'present-and-invalid'
        if not ed25519_verify(pub, msg, sig):
            report('signature-invalid', 'error', 'SIGNATURE.json', 'chain[%d] ed25519 check failed' % i)
            return 'present-and-invalid'
        prev = sha256(e['signature'].encode('utf-8'))
    actual = sha256(manifest_bytes)
    if chain[-1]['manifest_sha256'] != actual:
        report('signature-invalid', 'error', 'SIGNATURE.json',
               'last entry anchors %s but MANIFEST.json hashes to %s' % (chain[-1]['manifest_sha256'], actual))
        return 'present-and-invalid'
    if sig_doc.get('manifest_sha256') != actual:
        report('signature-invalid', 'error', 'SIGNATURE.json', 'top-level manifest_sha256 disagrees')
        return 'present-and-invalid'
    report('signature-valid', 'info', 'SIGNATURE.json',
           '%d link(s); signer %s. No external root of trust (SPEC 6).' % (len(chain), chain[-1]['signer'].get('uri')))
    return 'signed-and-valid'


# --------------------------------------------------------------------------
# meanings, read out of the package's own spec (SPEC.md section 3 table)
# --------------------------------------------------------------------------
def type_meanings(spec_md):
    """Map node type -> (payload, schema/layout) from SPEC.md 3's table, plus a
    human title from the '### 3.x Title -- `type`' headings."""
    table, titles = {}, {}
    for line in spec_md.splitlines():
        m = re.match(r'^\| `([a-z0-9.]+)` [^|]*\| ([^|]+) \| ([^|]+) \|$', line)
        if m and m.group(1) not in table:
            table[m.group(1)] = (m.group(2).strip(), m.group(3).strip())
        h = re.match(r'^### 3\.\d+a? (.+?) — `([a-z0-9.*]+)`', line)
        if h:
            titles[h.group(2)] = h.group(1)
    return table, titles


FALLBACK_TITLES = {
    # Types with no 3.x heading; wording taken from SPEC.md 1's tree comments
    # and spec/README.md's table.
    'core.spec': 'the format specification, travelling with the file (law 2)',
    'core.loader': 'embedded single-file zero-dependency reader (SPEC 7)',
    'core.license': 'full licence text, embedded',
    'core.readme': 'one paragraph for humans',
    'core.geom.source': 'source/archival mesh - the anchor derivations hash against (SPEC 3.10)',
    'core.geom.game': 'runtime (game) mesh - the renderable one (SPEC 3.10)',
    'core.material': 'PBR parameter JSON for one material id',
    'core.phys.bounds': 'measured bounds (physics/)',
    'core.provenance': 'producers, inputs, costs, prompts',
    'core.audio.package': 'the sound-world index (SPEC 3.9)',
    'core.audio.effect': 'one sound effect: WAV takes + JSON sidecar (SPEC 3.9)',
    'core.audio.ambience': 'one ambience: WAV takes + JSON sidecar (SPEC 3.9)',
}


# --------------------------------------------------------------------------
# payload resolution (SPEC.md 2.1, normative order)
# --------------------------------------------------------------------------
PAYLOAD_ROLE = {'core.audio.effect': 'best', 'core.audio.ambience': 'best',
                'core.imposter': 'atlas', 'core.recipe': 'record'}


def resolve_payload(node, ver):
    files = ver.get('files', [])
    paths = [f['path'] for f in files]
    pf = ver.get('payload_file')
    if pf is not None:                                         # rule 1
        if paths.count(pf) == 1:
            return pf, 'payload_file'
        report('payload-file-invalid', 'error', node['node_id'], 'payload_file %r not exactly one of files[]' % pf)
        return None, None
    if len(files) == 1:                                        # rule 2
        return paths[0], 'single-file'
    pl = [f['path'] for f in files if f.get('role') == 'payload']
    if len(pl) == 1:                                           # rule 3
        return pl[0], 'role=payload'
    role = PAYLOAD_ROLE.get(node['type'])
    if role:                                                   # rule 4
        c = [f['path'] for f in files if f.get('role') == role]
        if len(c) == 1:
            return c[0], 'role=%s' % role
    if node['type'] == 'core.anim.clip':
        c = [p for p in paths if p.endswith('.wkac')]
        if len(c) == 1:
            return c[0], 'single .wkac'
    report('payload-file-ambiguous', 'warn', node['node_id'], 'candidates: %s' % paths)   # rule 5
    return None, None


# --------------------------------------------------------------------------
# format sanity checks for what we extract (MINI-SPECS 9 and 10)
# --------------------------------------------------------------------------
def describe_glb(b):
    if len(b) < 20 or b[:4] != b'glTF':
        return None, 'not a GLB (magic)'
    ver, total = u32(b, 4), u32(b, 8)
    if ver != 2 or total != len(b):
        return None, 'GLB header: version %d, length %d vs %d' % (ver, total, len(b))
    clen, ctype = u32(b, 12), u32(b, 16)
    if ctype != 0x4E4F534A:
        return None, 'first chunk is not JSON'
    doc = json.loads(b[20:20 + clen].decode('utf-8'))
    prims, tris, verts, attrs = 0, 0, 0, set()
    for mesh in doc.get('meshes', []):
        for pr in mesh.get('primitives', []):
            prims += 1
            attrs |= set(pr.get('attributes', {}))
            if 'indices' in pr:
                tris += doc['accessors'][pr['indices']]['count'] // 3
            if 'POSITION' in pr.get('attributes', {}):
                verts += doc['accessors'][pr['attributes']['POSITION']]['count']
    return doc, 'GLB v2, %d bytes, %d primitive(s), %d vertices, %d triangles, attributes %s' % (
        len(b), prims, verts, tris, sorted(attrs))


def describe_wav(b):
    if len(b) < 12 or b[:4] != b'RIFF' or b[8:12] != b'WAVE':
        return 'not a RIFF/WAVE file'
    p, fmt, data_len = 12, None, None
    while p + 8 <= len(b):
        cid, size = b[p:p + 4], u32(b, p + 4)
        if cid == b'fmt ':
            fmt = struct.unpack_from('<HHIIHH', b, p + 8)
        elif cid == b'data':
            data_len = size
        p += 8 + size + (size & 1)          # the pad byte is not counted in size
    if not fmt or data_len is None:
        return 'WAV missing fmt or data chunk'
    af, ch, sr, _br, ba, bps = fmt
    frames = data_len // ba if ba else 0
    return 'WAV format %d (%s), %d ch, %d Hz, %d-bit, %d frames = %.3f s' % (
        af, {1: 'PCM', 3: 'float', 0xFFFE: 'extensible'}.get(af, '?'), ch, sr, bps, frames, frames / sr if sr else 0)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    pkg = argv[1]
    outdir = argv[2] if len(argv) > 2 else 'extracted'
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    # ---- 1. container ------------------------------------------------------
    try:
        z = Zip(pkg)
    except ContainerRefused as ex:
        print('CONTAINER REFUSED:', ex)
        return 2
    print('== container: %s (%d bytes, %d zip entries)' % (pkg, len(z.data), len(z.order)))

    # ---- 2. manifest -------------------------------------------------------
    mbytes = z.read('MANIFEST.json')
    if mbytes is None:
        print('CONTAINER REFUSED: manifest-absent (SPEC 12.1; recovery not implemented)')
        return 2
    try:
        man = parse_json(mbytes)
    except (ValueError, UnicodeDecodeError) as ex:
        print('CONTAINER REFUSED: manifest-unparseable: %s' % ex)
        return 2
    if not isinstance(man.get('nodes'), list) or not all(
            isinstance(n, dict) and isinstance(n.get('versions'), list) for n in man['nodes']):
        print('CONTAINER REFUSED: manifest-structurally-invalid')
        return 2
    werk = man.get('werk', {})
    print('   werk %s.%s, profile %s' % (werk.get('major'), werk.get('minor'), man.get('profile')))
    print('   entity: %s (%s)' % (man['entity'].get('name'), man['entity'].get('uuid')))
    if werk.get('major') != 1:
        report('unsupported-major', 'error', 'MANIFEST.json', 'werk.major %r' % werk.get('major'))
    if man.get('profile') != '3d-entity/1':
        report('unsupported-profile', 'warn', 'MANIFEST.json', man.get('profile'))
    report('manifest-structural-check-only', 'info', 'MANIFEST.json',
           'structural check, not a JSON-Schema validation (SPEC 10 step 2 [B])')

    # ---- 3. conventions (SPEC 10 step 3, 10.1, 10.2) -----------------------
    # What THIS reader supports. Taken from the const pins in
    # spec/schemas/manifest.schema.json for profile 3d-entity/1. The reader
    # only ever interprets GLB headers and WAV headers, so most of these are
    # "supported" in the sense that nothing here could misread them.
    SUPPORTED = {
        'endianness': 'le', 'units_per_meter': 1.0, 'length_unit': 'metre', 'angle_unit': 'radian',
        'time_unit': 'second', 'mass_unit': 'kilogram', 'up_axis': 'y', 'forward_axis': '-z',
        'right_axis': '+x', 'handedness': 'right', 'winding': 'ccw', 'quat_order': 'wxyz',
        'oct_encoding_pole': 'y', 'sh_l1_order': ['dc', 'y', 'z', 'x'], 'color_space_default': 'srgb',
        'uv_origin': 'top-left', 'alignment_bytes': 16, 'text_encoding': 'utf-8',
        'id_case': 'kebab-case', 'hash_algorithm': 'sha256', 'signature_algorithm': 'ed25519',
    }
    cmap_path = man.get('conventions_map')
    cmap = {}
    if cmap_path:
        cb = z.read(cmap_path)
        if cb is not None:
            cmap = parse_json(cb).get('conventions', {})
    refused_types = set()
    conv = man.get('conventions', {})
    container_refuse = False
    for key, want in SUPPORTED.items():
        got = conv.get(key)
        entry = cmap.get(key, {})
        if got == want:
            continue
        if got is None and entry.get('optional'):
            continue
        scope = entry.get('scope', 'node')
        report('unsupported-convention', 'error', 'conventions.' + key, 'declared %r, reader supports %r; scope %s' % (got, want, scope))
        if scope == 'container':
            container_refuse = True
        refused_types |= set(entry.get('governs', []))
    if container_refuse:
        print('CONTAINER REFUSED: a container-scoped convention is unsupported')
        return 2

    def type_refused(t):
        for g in refused_types:
            if g == t or (g.endswith('*') and t.startswith(g[:-1])):
                return True
        return False

    # ---- 4. signature (SPEC 6, MINI-SPECS 12) ------------------------------
    sbytes = z.read('SIGNATURE.json')
    if sbytes is None:
        sig_state = 'absent'
        report('signature-absent', 'warn', 'SIGNATURE.json')
    elif not ed25519_selftest():
        sig_state = 'unverified'
        report('signature-unverified', 'warn', 'SIGNATURE.json', 'Ed25519 self-test failed; not checking')
    else:
        try:
            sig_state = verify_chain(parse_json(sbytes), mbytes)
        except (ValueError, UnicodeDecodeError) as ex:
            sig_state = 'present-and-invalid'
            report('signature-invalid', 'error', 'SIGNATURE.json', 'unparseable: %s' % ex)

    # ---- 5/6. walk nodes, verify every declared file -----------------------
    nodes = man['nodes']
    by_id = {}
    for n in nodes:
        if n.get('node_id') in by_id:
            report('duplicate-node-id', 'error', n.get('node_id'))
        by_id[n.get('node_id')] = n
    claimed = {}          # path -> node_id (S-18: a path belongs to ONE node)
    file_ok = {}          # path -> bool
    file_decl = {}        # path -> declared sha256
    dead = {}             # node_id -> reason
    active_ver = {}
    for n in nodes:
        nid = n['node_id']
        vers = {v.get('v'): v for v in n['versions']}
        ver = vers.get(n.get('active'))
        if ver is None:
            older = sorted((k for k in vers if isinstance(k, int)), reverse=True)
            if older:
                ver = vers[older[0]]
                report('active-version-fallback', 'warn', nid, 'active %r invalid; using v%s' % (n.get('active'), older[0]))
            else:
                dead[nid] = 'no valid version'
                report('node-dead', 'error', nid, 'no valid version')
                continue
        active_ver[nid] = ver
        for v in n['versions']:
            for f in v.get('files', []):
                path = f['path']
                owner = claimed.setdefault(path, nid)
                if owner != nid:
                    report('path-claimed-by-two-nodes', 'error', path, '%s and %s' % (owner, nid))
                if path in file_ok:
                    if file_decl[path] != f['sha256']:
                        report('path-declared-inconsistently', 'error', path)
                    continue
                file_decl[path] = f['sha256']
                b = z.read(path)
                if b is None:
                    file_ok[path] = False
                    report('file-missing', 'error', path, 'declared by %s' % nid)
                elif len(b) != f['size']:
                    file_ok[path] = False
                    report('size-mismatch', 'error', path, 'declared %d, actual %d' % (f['size'], len(b)))
                elif sha256(b) != f['sha256']:
                    file_ok[path] = False
                    report('hash-mismatch', 'error', path, 'declared %s, actual %s' % (f['sha256'], sha256(b)))
                else:
                    file_ok[path] = True
        bad = [f['path'] for f in ver.get('files', []) if not file_ok.get(f['path'])]
        if bad:
            dead[nid] = 'bad file(s): %s' % bad
            report('node-dead', 'error', nid, dead[nid])
        if type_refused(n['type']) and nid not in dead:
            dead[nid] = 'unsupported convention'

    # requires-edges into dead nodes kill the source (SPEC 5); iterate to fixpoint
    changed = True
    while changed:
        changed = False
        for n in nodes:
            nid = n['node_id']
            if nid in dead:
                continue
            for e in n.get('edges', []):
                if e.get('to') not in by_id:
                    report('edge-target-missing', 'warn', nid, 'edge to %r' % e.get('to'))
                elif e.get('kind') == 'requires' and e['to'] in dead:
                    dead[nid] = 'requires dead node %s' % e['to']
                    report('node-dead', 'error', nid, dead[nid])
                    changed = True
                elif e.get('kind') == 'enhances' and e['to'] in dead:
                    report('feature-lost', 'warn', nid, 'enhances dead node %s' % e['to'])

    # nothing floats (SPEC 2): every entry except MANIFEST/SIGNATURE is claimed
    for name in z.order:
        if name.endswith('/'):
            continue
        if name not in ('MANIFEST.json', 'SIGNATURE.json') and name not in claimed:
            report('floating-entry', 'warn', name, 'in the zip but in no node files[]; never followed')
    # license.sha256
    lic = man.get('license', {})
    lb = z.read(lic.get('file', 'LICENSE'))
    if lb is None or sha256(lb) != lic.get('sha256'):
        report('license-hash-mismatch', 'error', 'LICENSE')
    # spec_sha256 (SPEC 2, S-29)
    spec_paths = sorted((p for p in claimed if p.startswith('spec/')), key=lambda s: s.encode('utf-8'))
    h = hashlib.sha256()
    for p in spec_paths:
        h.update(p.encode('utf-8') + b'\n' + bytes.fromhex(file_decl[p]) + b'\n')
    spec_ok = h.hexdigest() == man.get('spec_sha256')
    if not spec_ok:
        report('spec-sha256-mismatch', 'error', 'spec/', 'declared %s computed %s' % (man.get('spec_sha256'), h.hexdigest()))
    # input_hash (MINI-SPECS 11 'What gets hashed')
    ih_checked = ih_bad = 0
    for n in nodes:
        ver = active_ver.get(n['node_id'])
        if not ver or 'input_hash' not in ver:
            if ver and ver.get('epistemic') in ('measured', 'inferred'):
                report('input-hash-missing', 'warn', n['node_id'])
            continue
        h = hashlib.sha256()
        okin = True
        for p in ver.get('input_files', []):
            b = z.read(p)
            if b is None:
                okin = False
                break
            h.update(hashlib.sha256(b).digest())
        h.update(canonical_json(ver.get('input_params') or {}).encode('utf-8'))
        ih_checked += 1
        if not okin or h.hexdigest() != ver['input_hash']:
            ih_bad += 1
            report('input-hash-stale', 'warn', n['node_id'], 'declared %s computed %s' % (ver['input_hash'], h.hexdigest()))
    # total_size_bytes (S-30), advisory
    tsb = man.get('container', {}).get('total_size_bytes')
    real_total = sum(z.entries[p]['usize'] for p in claimed if p in z.entries)
    if tsb is not None and tsb != real_total:
        report('total-size-disagrees', 'info', 'container.total_size_bytes', 'declared %d computed %d' % (tsb, real_total))

    # ---- listing: the node graph with meanings -----------------------------
    spec_md = (z.read('spec/SPEC.md') or b'').decode('utf-8', 'replace')
    table, titles = type_meanings(spec_md)
    print('\n== node graph: %d nodes' % len(nodes))
    for n in nodes:
        nid, t = n['node_id'], n['type']
        ver = active_ver.get(nid, {})
        if t in titles:
            meaning = titles[t]
        elif t in FALLBACK_TITLES:
            meaning = FALLBACK_TITLES[t]
        elif t.startswith('x.'):
            meaning = 'EXTENSION (x.*) - not specified by core; skipped for interpretation, hashes still verified'
            report('node-skipped-unknown-type', 'info', nid, t)
        else:
            meaning = 'UNKNOWN TYPE - skipped'
            report('node-skipped-unknown-type', 'warn', nid, t)
        payload_kind = table.get(t, ('?', '?'))[0]
        state = 'DEAD (%s)' % dead[nid] if nid in dead else 'ok'
        files = ver.get('files', [])
        print('\n* %s  [%s]  v%s  %s' % (nid, t, ver.get('v'), state))
        print('    meaning : %s; payload kind: %s' % (meaning, payload_kind))
        where = ', '.join(x for x in (n.get('part_id') and 'part=' + n['part_id'],
                                      n.get('material_id') and 'material=' + n['material_id']) if x)
        if where:
            print('    joins   : %s' % where)
        print('    stamp   : %s by %s %s%s%s' % (
            ver.get('epistemic'), ver.get('producer', {}).get('tool'), ver.get('producer', {}).get('version'),
            (' model=' + ver['producer']['model']) if ver.get('producer', {}).get('model') else '',
            (' confidence=%s' % ver['confidence']) if 'confidence' in ver else ''))
        print('    note    : %s' % ver.get('note'))
        for e in n.get('edges', []):
            print('    edge    : %s --%s%s--> %s' % (nid, e.get('kind'), ('/' + e['role']) if e.get('role') else '', e.get('to')))
        print('    files   : %d, %d bytes, all hashes ok: %s' % (
            len(files), sum(f['size'] for f in files), all(file_ok.get(f['path']) for f in files)))
        if len(files) <= 6:
            for f in files:
                print('      - %s%s  %d B  sha256 %s' % (f['path'], (' (role ' + f['role'] + ')') if f.get('role') else '', f['size'], 'OK' if file_ok.get(f['path']) else 'BAD'))

    # ---- extraction: primary mesh + primary sound --------------------------
    print('\n== primary')
    primary = man.get('primary') or {}
    os.makedirs(outdir, exist_ok=True)
    extracted = []

    def pick(slot, fallback):
        nid = primary.get(slot)
        if nid is None:
            nid = fallback()
            report('primary-fallback', 'warn', 'primary.' + slot, 'absent; fell back to %r' % nid)
        return nid

    def fb_mesh():
        for n in nodes:
            if n['type'] == 'core.geom.game':
                return n['node_id']

    def fb_sound():
        pkgn = next((n for n in nodes if n['type'] == 'core.audio.package'), None)
        if pkgn and active_ver.get(pkgn['node_id']):
            pb = z.read(resolve_payload(pkgn, active_ver[pkgn['node_id']])[0] or '')
            slug = parse_json(pb).get('preview_effect') if pb else None
            for n in nodes:
                if n['type'] == 'core.audio.effect' and n['node_id'].endswith(slug or '\0'):
                    return n['node_id']
        return next((n['node_id'] for n in nodes if n['type'] == 'core.audio.effect'), None)

    for slot, fb in (('mesh', fb_mesh), ('sound', fb_sound)):
        nid = pick(slot, fb)
        n = by_id.get(nid)
        if n is None:
            report('primary-unresolvable', 'error', 'primary.' + slot, repr(nid))
            continue
        if nid in dead:
            report('primary-dead', 'error', 'primary.' + slot, '%s is dead: %s' % (nid, dead[nid]))
            continue
        ver = active_ver[nid]
        path, rule = resolve_payload(n, ver)
        if path is None:
            report('primary-unresolvable', 'error', 'primary.' + slot, 'no payload for %s' % nid)
            continue
        if path not in [f['path'] for f in ver['files']] or path not in claimed:
            report('path-not-declared', 'error', path)        # SPEC 10 step 9
            continue
        b = z.read(path)
        declared = next(f['sha256'] for f in ver['files'] if f['path'] == path)
        dest = os.path.join(outdir, path.replace('/', os.sep))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wb') as f:
            f.write(b)
        with open(dest, 'rb') as f:           # hash what actually landed on disk
            on_disk = sha256(f.read())
        if slot == 'mesh':
            _, desc = describe_glb(b)
        else:
            desc = describe_wav(b)
        match = on_disk == declared
        if not match:
            report('extract-hash-mismatch', 'error', dest)
        extracted.append((slot, nid, path, rule, dest, declared, on_disk, match, desc))
        print('  %-5s -> node %s -> %s (resolved by %s)' % (slot, nid, path, rule))
        print('          wrote %s' % dest)
        print('          %s' % desc)
        print('          declared sha256 %s' % declared)
        print('          on-disk  sha256 %s  %s' % (on_disk, 'MATCH' if match else 'MISMATCH'))

    # ---- summary ----------------------------------------------------------
    nfiles = len(file_ok)
    print('\n== integrity')
    print('  declared files verified : %d/%d (size + sha256)' % (sum(file_ok.values()), nfiles))
    print('  license.sha256          : %s' % ('ok' if not any(r[0] == 'license-hash-mismatch' for r in REPORT) else 'MISMATCH'))
    print('  spec_sha256             : %s' % ('ok' if spec_ok else 'MISMATCH'))
    print('  input_hash              : %d checked, %d stale' % (ih_checked, ih_bad))
    print('  zip CRC-32              : %s' % ('ok' if not any(r[0] == 'zip-crc-mismatch' for r in REPORT) else 'MISMATCH'))
    print('  signature chain         : %s' % sig_state)
    print('  dead nodes              : %s' % (sorted(dead) or 'none'))
    print('\n== report (%d entries)' % len(REPORT))
    for code, sev, subj, det in REPORT:
        print('  [%-5s] %-32s %s %s' % (sev, code, subj, ('- ' + det) if det else ''))
    return 1 if any(r[1] == 'error' for r in REPORT) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
