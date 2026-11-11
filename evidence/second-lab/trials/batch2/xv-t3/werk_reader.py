#!/usr/bin/env python3
"""werk_reader.py - an independent reader for a werk 3D-entity package.

Written only from the documentation carried inside the package itself
(spec/README.md, spec/SPEC.md, spec/MINI-SPECS.md, spec/conventions-map.json).
The loaders bundled in the package's loaders/ directory were NOT read, run or
ported.

    python werk_reader.py crate-v1.werk [--out DIR] [--sound NODE_ID]

What it does, following SPEC.md section 10 (reader checklist):
  1. opens the store-mode zip (zip64 detection + refusal, method check, CRC)
  2. reads MANIFEST.json, structural check, werk.major, profile
  3. checks every convention against what this reader supports, refusing the
     governed node types through the package's own conventions map
  4. verifies the SIGNATURE.json chain with a from-spec Ed25519 verifier
  5/6. walks nodes[], verifies size + sha256 of every declared file
  + license hash, spec_sha256, every input_hash, total_size_bytes,
    "nothing floats" (every container entry belongs to exactly one node)
  7/8. dispatches GLB / WAV structural checks; skips unknown types, reporting
  then extracts primary.mesh and primary.sound (payload resolved per SPEC 2.1,
  never files[0]) and re-hashes the written bytes against the manifest.

Exit status (SPEC 10.2): 0 ok, 1 errors present, 2 container refused.
"""
import hashlib
import json
import os
import struct
import sys
import zipfile
import zlib

# ----------------------------------------------------------------------------
# report
# ----------------------------------------------------------------------------
REPORT = []


def report(code, severity, subject, detail=''):
    REPORT.append((severity, code, subject, detail))
    print('  [%-5s] %-32s %s %s' % (severity, code, subject, ('- ' + detail) if detail else ''))


def sha256(b):
    return hashlib.sha256(b).hexdigest()


# ----------------------------------------------------------------------------
# Ed25519 verification, from MINI-SPECS.md section 12 (verify only, public data)
# ----------------------------------------------------------------------------
P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493


def inv(a):
    return pow(a, P - 2, P)


D = (-121665 * inv(121666)) % P
I = pow(2, (P - 1) // 4, P)


def recover_x(y, sign):
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


def decompress(b):
    if len(b) != 32:
        return None
    n = int.from_bytes(b, 'little')
    y = n & ((1 << 255) - 1)
    sign = n >> 255
    if y >= P:
        return None
    x = recover_x(y, sign)
    if x is None:
        return None
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


_By = 4 * inv(5) % P
BASE = (recover_x(_By, 0), _By, 1, recover_x(_By, 0) * _By % P)


def ed25519_verify(pub, msg, sig):
    if len(sig) != 64:
        return False
    A = decompress(pub)
    R = decompress(sig[:32])
    if A is None or R is None:
        return False
    S = int.from_bytes(sig[32:], 'little')
    if S >= L:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), 'little') % L
    lhs = smul(8, smul(S, BASE))
    rhs = smul(8, padd(R, smul(k, A)))
    return peq(lhs, rhs)


def ed25519_selftest():
    # RFC 8032 test vector 1, as printed in MINI-SPECS.md section 12
    pub = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
    sig = bytes.fromhex('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b')
    ok = ed25519_verify(pub, b'', sig)
    bad = ed25519_verify(pub, b'x', sig)
    return ok and not bad


# ----------------------------------------------------------------------------
# container (MINI-SPECS.md section 5)
# ----------------------------------------------------------------------------
class Container:
    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as f:
            self.raw = f.read()
        self.check_zip64()
        self.zf = zipfile.ZipFile(path)
        self.entries = {}
        self.crc_bad = set()
        for i in self.zf.infolist():
            if i.filename.endswith('/'):
                continue  # directory entries are optional, never depended on
            n = i.filename
            if n.startswith('/') or '..' in n.split('/') or ':' in n or '\\' in n:
                raise ContainerRefused('unsafe-entry-name', n)
            self.entries[n] = i

    def check_zip64(self):
        b = self.raw
        lo = max(0, len(b) - 22 - 65535)
        pos = b.rfind(b'PK\x05\x06', lo)
        if pos < 0:
            raise ContainerRefused('no-eocd', 'end of central directory record not found')
        _, _, _, n_disk, n_tot, cd_size, cd_off, _ = struct.unpack('<IHHHHIIH', b[pos:pos + 22])
        if n_disk == 0xFFFF or n_tot == 0xFFFF or cd_size == 0xFFFFFFFF or cd_off == 0xFFFFFFFF \
                or (pos >= 20 and b[pos - 20:pos - 16] == b'PK\x06\x07'):
            raise ContainerRefused('zip64-unsupported', 'zip64 container; this reader is zip32-only')
        self.eocd = dict(offset=pos, entries=n_tot, cd_size=cd_size, cd_offset=cd_off)

    def read(self, name):
        """Entry bytes. A CRC-32 mismatch is recorded in self.crc_bad, never raised,
        so the sha256 check decides the node's fate and one bad file cannot stop
        the rest of the load (SPEC 10.1, law 3)."""
        i = self.entries[name]
        if i.compress_type == 0:
            lh = i.header_offset
            if self.raw[lh:lh + 4] != b'PK\x03\x04':
                raise ValueError('local header signature missing at %d' % lh)
            n, mlen = struct.unpack('<HH', self.raw[lh + 26:lh + 30])  # re-read from local header (MINI-SPECS 5.3)
            start = lh + 30 + n + mlen
            b = bytes(self.raw[start:start + i.compress_size])
        elif i.compress_type == 8:
            b = self._read_deflate(i)
        else:
            raise ValueError('unsupported compression method %d' % i.compress_type)
        if zlib.crc32(b) & 0xFFFFFFFF != i.CRC:
            self.crc_bad.add(name)
        return b

    def _read_deflate(self, i):
        lh = i.header_offset
        n, mlen = struct.unpack('<HH', self.raw[lh + 26:lh + 30])
        start = lh + 30 + n + mlen
        return zlib.decompress(bytes(self.raw[start:start + i.compress_size]), -15)


class ContainerRefused(Exception):
    pass


# ----------------------------------------------------------------------------
# what each node type means (spec/README.md table + SPEC.md section 3)
# ----------------------------------------------------------------------------
TYPE_MEANING = {
    'core.spec': 'the format specification carried inside the package (law 2)',
    'core.loader': 'embedded single-file reference reader (source; inert data here)',
    'core.license': 'full licence text',
    'core.readme': 'one paragraph for humans',
    'core.geom.source': 'archival source geometry (GLB); anchor for derived hashes',
    'core.geom.game': 'runtime/renderable mesh (GLB) - default primary mesh',
    'core.geom.lod': 'level-of-detail mesh (GLB)',
    'core.tex': 'texture (PNG)',
    'core.material': 'PBR material parameters (JSON)',
    'core.imposter': 'octahedral imposter atlases (PNG) + descriptor',
    'core.phys.colliders': 'collision shapes, part-local space (JSON)',
    'core.phys.bounds': 'bounding volumes, model space (JSON)',
    'core.phys.body': 'mass / centre of mass / inertia, model space (JSON)',
    'core.field.flow': 'flow field + SDF grid (WKFF binary)',
    'core.pose.rest': 'settled rest poses (WKRP binary)',
    'core.skeleton': 'rig (JSON + optional WKSK mirror)',
    'core.anim.clip': 'animation clip (WKAC binary + JSON)',
    'core.retarget.bind': 'solved retarget bind (JSON)',
    'core.audio.package': 'the sound set as a whole: splat-foley package manifest (JSON)',
    'core.audio.effect': 'one sound effect: WAV takes + per-effect sidecar JSON',
    'core.audio.ambience': 'one ambience loop: WAV takes + per-effect sidecar JSON',
    'core.destruct': 'fracture set (GLB + JSON)',
    'core.props': 'simulation property registry values, each epistemically stamped (JSON)',
    'core.semantics': 'facet tags, style embedding, palette (JSON)',
    'core.provenance': 'producers, inputs, costs, prompts (JSON)',
    'core.recipe': 'generation reproduction record (JSON)',
    'core.disclosure': 'machine-readable AI disclosure facts (JSON)',
    'core.embedding': 'descriptor vector + palette (WKEM binary)',
    'core.geom.points': 'point cloud (WKPC binary)',
    'core.geom.gsplat': 'Gaussian splat (WKGS binary)',
    'core.tool': 'embedded tool source + descriptor',
    'core.tool.config': 'tool configuration (JSON)',
}

# The convention values this reader implements for profile 3d-entity/1.
SUPPORTED_PROFILE = '3d-entity/1'
SUPPORTED_CONVENTIONS = {
    'endianness': 'le', 'units_per_meter': 1.0, 'length_unit': 'metre',
    'angle_unit': 'radian', 'time_unit': 'second', 'mass_unit': 'kilogram',
    'up_axis': 'y', 'forward_axis': '-z', 'right_axis': '+x',
    'handedness': 'right', 'winding': 'ccw', 'quat_order': 'wxyz',
    'oct_encoding_pole': 'y', 'sh_l1_order': ['dc', 'y', 'z', 'x'],
    'color_space_default': 'srgb', 'uv_origin': 'top-left',
    'alignment_bytes': 16, 'text_encoding': 'utf-8', 'id_case': 'kebab-case',
    'hash_algorithm': 'sha256', 'signature_algorithm': 'ed25519',
}
PAYLOAD_ROLE = {'core.audio.effect': 'best', 'core.audio.ambience': 'best',
                'core.imposter': 'atlas', 'core.recipe': 'record'}


def type_matches(t, pattern):
    if pattern.endswith('.*'):
        return t.startswith(pattern[:-1])
    return t == pattern


def canonical_json(v):
    # MINI-SPECS 3: sorted keys, no whitespace, minimal escapes. Only {} or
    # simple values occur in this package's input_params.
    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def strict_json(b, what):
    if b.startswith(b'\xef\xbb\xbf'):
        raise ValueError('%s has a UTF-8 BOM (MINI-SPECS 2: reject)' % what)

    def no_dupes(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise ValueError('duplicate key %r in %s' % (k, what))
            d[k] = v
        return d

    def no_const(c):
        raise ValueError('non-finite number %s in %s' % (c, what))
    return json.loads(b.decode('utf-8'), object_pairs_hook=no_dupes, parse_constant=no_const)


# ----------------------------------------------------------------------------
# payload resolution, SPEC.md section 2.1 (NORMATIVE order, never files[0])
# ----------------------------------------------------------------------------
def resolve_payload(node, version):
    files = version['files']
    paths = [f['path'] for f in files]
    if 'payload_file' in version:
        pf = version['payload_file']
        if paths.count(pf) != 1:
            return None, 'payload_file %r does not name exactly one files[] entry' % pf
        return pf, 'rule 1: payload_file'
    if len(files) == 1:
        return files[0]['path'], 'rule 2: single file'
    pl = [f for f in files if f.get('role') == 'payload']
    if len(pl) == 1:
        return pl[0]['path'], 'rule 3: role=payload'
    role = PAYLOAD_ROLE.get(node['type'])
    if role:
        c = [f for f in files if f.get('role') == role]
        if len(c) == 1:
            return c[0]['path'], 'rule 4: type payload role %r' % role
    return None, 'payload-file-ambiguous; candidates: %s' % [p for p in paths]


# ----------------------------------------------------------------------------
# GLB / WAV structural checks (MINI-SPECS 9, 10; SPEC 3.10)
# ----------------------------------------------------------------------------
def check_glb(b, renderable):
    out = {}
    if b[:4] != b'glTF':
        raise ValueError('bad GLB magic')
    ver, total = struct.unpack('<II', b[4:12])
    if ver != 2 or total != len(b):
        raise ValueError('GLB version %d / length %d vs %d' % (ver, total, len(b)))
    off, js, binc = 12, None, None
    while off < len(b):
        clen, ctype = struct.unpack('<II', b[off:off + 8])
        data = b[off + 8:off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(data.decode('utf-8'))
        elif ctype == 0x004E4942:
            binc = data
        off += 8 + clen
    if js is None:
        raise ValueError('GLB has no JSON chunk')
    comp_size = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
    ncomp = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}
    acc = js.get('accessors', [])
    views = js.get('bufferViews', [])
    tris = verts = 0
    attrs = set()
    for mesh in js.get('meshes', []):
        for prim in mesh['primitives']:
            if prim.get('mode', 4) != 4:
                raise ValueError('primitive mode %s is not triangles' % prim.get('mode'))
            if 'indices' not in prim:
                raise ValueError('non-indexed primitive')
            ia = acc[prim['indices']]
            if ia['componentType'] not in (5123, 5125):
                raise ValueError('indices componentType %d' % ia['componentType'])
            tris += ia['count'] // 3
            attrs |= set(prim['attributes'])
            verts += acc[prim['attributes']['POSITION']]['count']
            # every accessor must fit inside its buffer view
            for a_i in [prim['indices']] + list(prim['attributes'].values()):
                a = acc[a_i]
                v = views[a['bufferView']]
                elem = comp_size[a['componentType']] * ncomp[a['type']]
                stride = v.get('byteStride', elem)
                need = a.get('byteOffset', 0) + (a['count'] - 1) * stride + elem
                if need > v['byteLength'] or v.get('byteOffset', 0) + v['byteLength'] > len(binc or b''):
                    raise ValueError('accessor %d overruns its bufferView/BIN' % a_i)
    if 'POSITION' not in attrs:
        raise ValueError('no POSITION attribute')
    if renderable and 'NORMAL' not in attrs:
        raise ValueError('renderable mesh without NORMAL (SPEC 3.10)')
    out.update(triangles=tris, vertices=verts, attributes=sorted(attrs),
               generator=js.get('asset', {}).get('generator'))
    return out


def check_wav(b):
    if b[:4] != b'RIFF' or b[8:12] != b'WAVE':
        raise ValueError('not RIFF/WAVE')
    riff_size = struct.unpack('<I', b[4:8])[0]
    off, fmt, data_size = 12, None, None
    while off + 8 <= len(b):
        cid = b[off:off + 4]
        csz = struct.unpack('<I', b[off + 4:off + 8])[0]
        body = b[off + 8:off + 8 + csz]
        if cid == b'fmt ':
            af, ch, sr, br, ba, bps = struct.unpack('<HHIIHH', body[:16])
            fmt = dict(audio_format=af, channels=ch, sample_rate=sr, byte_rate=br,
                       block_align=ba, bits_per_sample=bps)
        elif cid == b'data':
            data_size = csz
        off += 8 + csz + (csz & 1)
    if fmt is None or data_size is None:
        raise ValueError('missing fmt or data chunk')
    fmt['frames'] = data_size // fmt['block_align']
    fmt['seconds'] = fmt['frames'] / fmt['sample_rate']
    fmt['riff_size_ok'] = (riff_size == len(b) - 8)
    return fmt


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main(argv):
    args = argv[1:]
    out_dir = 'extracted'
    sound_override = None
    if '--out' in args:
        i = args.index('--out'); out_dir = args[i + 1]; del args[i:i + 2]
    if '--sound' in args:
        i = args.index('--sound'); sound_override = args[i + 1]; del args[i:i + 2]
    if len(args) != 1:
        print(__doc__)
        return 2
    path = args[0]

    print('== 1. container: %s' % path)
    try:
        c = Container(path)
    except ContainerRefused as e:
        report(e.args[0], 'error', path, e.args[1])
        return 2
    except zipfile.BadZipFile as e:
        report('not-a-zip', 'error', path, str(e))
        return 2
    methods = sorted({i.compress_type for i in c.entries.values()})
    print('  %d entries, %d bytes, compression methods %s, EOCD at %d' %
          (len(c.entries), len(c.raw), methods, c.eocd['offset']))

    print('== 2. manifest')
    if 'MANIFEST.json' not in c.entries:
        report('manifest-absent', 'error', 'MANIFEST.json', 'recovery (SPEC 12) not implemented')
        return 2
    mbytes = c.read('MANIFEST.json')
    try:
        m = strict_json(mbytes, 'MANIFEST.json')
    except Exception as e:
        report('manifest-unparseable', 'error', 'MANIFEST.json', str(e))
        return 2
    if not isinstance(m.get('nodes'), list) or not all(isinstance(v.get('files'), list)
                                                       for n in m['nodes'] for v in n.get('versions', [])):
        report('manifest-structurally-invalid', 'error', 'MANIFEST.json')
        return 2
    print('  werk %s.%s  profile %s  sha256 %s' % (m['werk']['major'], m['werk']['minor'],
                                                 m.get('profile'), sha256(mbytes)))
    print('  entity: %s (%s)' % (m['entity']['name'], m['entity']['uuid']))
    print('  summary: %s' % m['entity']['summary'])
    print('  (structural check only - JSON Schema validation NOT performed)')
    if m['werk']['major'] != 1:
        report('unsupported-werk-major', 'error', 'MANIFEST.json', str(m['werk']))
        return 2
    profile_ok = m.get('profile') == SUPPORTED_PROFILE
    if not profile_ok:
        report('unsupported-profile', 'warn', m.get('profile'),
               'listing/verifying/extracting only, no payload meaning claimed')
    cont = m.get('container', {})
    if cont.get('form') != 'zip':
        report('container-form-note', 'info', 'container.form', repr(cont.get('form')))

    print('== 3. conventions')
    refused_types = {}
    if profile_ok:
        cmap = None
        cmap_path = m.get('conventions_map')
        if cmap_path and cmap_path in c.entries:
            cmap = strict_json(c.read(cmap_path), cmap_path)['conventions']
        conv = m.get('conventions', {})
        for k, want in SUPPORTED_CONVENTIONS.items():
            got = conv.get(k)
            if got == want:
                continue
            optional = cmap and cmap.get(k, {}).get('optional')
            if got is None and optional:
                continue
            scope = (cmap or {}).get(k, {}).get('scope', 'node')
            governs = (cmap or {}).get(k, {}).get('governs', [])
            report('unsupported-convention', 'error' if scope == 'container' else 'warn',
                   k, 'declared %r, supported %r; scope %s; refusing %s' % (got, want, scope, governs))
            if scope == 'container':
                return 2
            for g in governs:
                refused_types[g] = k
        for k in conv:
            if k not in SUPPORTED_CONVENTIONS and not (cmap and cmap.get(k, {}).get('optional')):
                report('unknown-convention', 'warn', k, repr(conv[k]))
        if not refused_types:
            print('  all %d declared conventions supported' % len(conv))

    print('== 4. signature')
    if 'SIGNATURE.json' not in c.entries:
        sig_state = 'absent'
        report('signature-absent', 'warn', 'SIGNATURE.json')
    elif not ed25519_selftest():
        sig_state = 'unverified'
        report('signature-unverified', 'warn', 'SIGNATURE.json', 'Ed25519 self-test failed')
    else:
        s = strict_json(c.read('SIGNATURE.json'), 'SIGNATURE.json')
        sig_state = 'signed-and-valid'
        prev_sig = None
        for i, e in enumerate(s.get('chain', [])):
            expect_prev = '0' * 64 if i == 0 else sha256(prev_sig.encode('utf-8'))
            msg = '\n'.join(['werk-sig/1', e['manifest_sha256'], e['prev_entry_sha256'],
                             e['signed_at'], e['signer']['uri'], e['signer']['kind']]).encode('utf-8')
            good = (e['prev_entry_sha256'] == expect_prev and
                    ed25519_verify(bytes.fromhex(e['public_key']), msg, bytes.fromhex(e['signature'])))
            print('  chain[%d] signer %s (%s) at %s: %s' % (i, e['signer']['uri'], e['signer']['kind'],
                                                        e['signed_at'], 'ok' if good else 'FAILED'))
            if not good:
                sig_state = 'present-and-invalid'
            prev_sig = e['signature']
        chain = s.get('chain', [])
        if not chain or chain[-1]['manifest_sha256'] != sha256(mbytes) or s.get('manifest_sha256') != sha256(mbytes):
            sig_state = 'present-and-invalid'
            print('  manifest anchor does NOT match the MANIFEST.json bytes present')
        else:
            print('  manifest anchor matches MANIFEST.json bytes')
        report({'signed-and-valid': 'signature-valid', 'present-and-invalid': 'signature-invalid'}[sig_state],
               'info' if sig_state == 'signed-and-valid' else 'error', 'SIGNATURE.json',
               'state: %s (DEV key - proves the chain verifies, nothing about authorship)' % sig_state)

    print('== 5/6. node graph + integrity')
    nodes = {n['node_id']: n for n in m['nodes']}
    dead = {}
    owner = {}
    file_hash = {}
    n_files = 0
    for n in m['nodes']:
        nid = n['node_id']
        vers = {v['v']: v for v in n['versions']}
        if n.get('active') not in vers:
            report('active-version-invalid', 'warn', nid, 'active=%r' % n.get('active'))
            if not vers:
                dead[nid] = 'no versions'
                continue
            n['active'] = max(vers)
        for v in n['versions']:
            for f in v['files']:
                p = f['path']
                prev = owner.get(p)
                if prev and prev != nid:
                    report('file-claimed-twice', 'error', p, 'by %s and %s' % (prev, nid))
                owner[p] = nid
        act = vers[n['active']]
        for f in act['files']:
            n_files += 1
            p = f['path']
            if p not in c.entries:
                report('file-missing', 'error', p, 'node %s' % nid)
                dead[nid] = 'missing file %s' % p
                continue
            try:
                b = c.read(p)
            except Exception as e:  # CRC mismatch, bad method
                report('container-read-failed', 'error', p, str(e))
                dead[nid] = 'unreadable %s' % p
                continue
            h = sha256(b)
            file_hash[p] = h
            if p in c.crc_bad:
                report('zip-crc-mismatch', 'error', p, 'stored CRC-32 disagrees with the bytes')
                dead[nid] = 'zip CRC mismatch %s' % p
            if len(b) != f['size']:
                report('size-mismatch', 'error', p, 'declared %d, actual %d' % (f['size'], len(b)))
                dead[nid] = 'size mismatch %s' % p
            if h != f['sha256']:
                report('hash-mismatch', 'error', p, 'declared %s, actual %s' % (f['sha256'], h))
                dead[nid] = 'hash mismatch %s' % p
        for pat, conv_name in refused_types.items():
            if type_matches(n['type'], pat) and nid not in dead:
                dead[nid] = 'unsupported convention %s' % conv_name
    # nothing floats
    for name in c.entries:
        if name in ('MANIFEST.json', 'SIGNATURE.json'):
            continue
        if name not in owner:
            report('file-floating', 'warn', name, 'container entry not declared by any node')
    # requires edges into dead nodes kill the source (SPEC 5), to a fixed point
    changed = True
    while changed:
        changed = False
        for n in m['nodes']:
            if n['node_id'] in dead:
                continue
            for e in n.get('edges', []):
                if e['to'] not in nodes:
                    report('edge-target-missing', 'warn', n['node_id'], e['to'])
                elif e['kind'] == 'requires' and e['to'] in dead:
                    dead[n['node_id']] = 'requires dead node %s' % e['to']
                    report('node-dead-by-edge', 'error', n['node_id'], 'requires %s' % e['to'])
                    changed = True
    for nid, why in dead.items():
        report('node-dead', 'error', nid, why)
    print('  %d nodes, %d active-version files hashed, %d dead' % (len(nodes), n_files, len(dead)))

    # listing with meanings
    print()
    print('  %-40s %-26s %-4s %-6s %s' % ('node_id', 'type', 'v', 'status', 'meaning / work note'))
    for n in m['nodes']:
        act = [v for v in n['versions'] if v['v'] == n['active']][0]
        meaning = TYPE_MEANING.get(n['type'])
        if meaning is None:
            meaning = 'extension node (x.*), skipped by core readers' if n['type'].startswith('x.') \
                else 'UNKNOWN TYPE - skipped'
            report('node-skipped-unknown-type', 'info', n['node_id'], n['type'])
        status = 'DEAD' if n['node_id'] in dead else 'ok'
        print('  %-40s %-26s %-4s %-6s %s' % (n['node_id'], n['type'], n['active'], status, meaning))
        print('  %-40s   note: %s' % ('', act.get('note', '')))
        print('  %-40s   %d file(s), producer %s %s%s, epistemic %s%s' % (
            '', len(act['files']), act['producer'].get('tool'), act['producer'].get('version'),
            (' / ' + act['producer']['model']) if act['producer'].get('model') else '',
            act.get('epistemic'), (' conf %s' % act['confidence']) if 'confidence' in act else ''))
        for e in n.get('edges', []):
            print('  %-40s   --%s(%s)--> %s' % ('', e['kind'], e.get('role', ''), e['to']))
    print()

    print('== package-level hashes')
    lic = m.get('license')
    if lic:
        lh = file_hash.get(lic['file']) or (sha256(c.read(lic['file'])) if lic['file'] in c.entries else None)
        if lh == lic['sha256']:
            print('  license.sha256 ok (%s, %s)' % (lic.get('spdx_id'), lh))
        else:
            report('license-hash-mismatch', 'error', lic['file'], 'declared %s actual %s' % (lic['sha256'], lh))
    # spec_sha256 (SPEC 2): declared spec/ files, sorted by UTF-8 path bytes
    spec_paths = sorted({f['path'] for n in m['nodes'] for v in n['versions'] for f in v['files']
                         if f['path'].startswith('spec/')}, key=lambda s: s.encode('utf-8'))
    hh = hashlib.sha256()
    for p in spec_paths:
        hh.update(p.encode('utf-8') + b'\n' + bytes.fromhex(sha256(c.read(p))) + b'\n')
    if hh.hexdigest() == m.get('spec_sha256'):
        print('  spec_sha256 ok over %d spec/ files (%s)' % (len(spec_paths), hh.hexdigest()))
    else:
        report('spec-sha256-mismatch', 'error', 'spec/', 'declared %s computed %s' % (m.get('spec_sha256'), hh.hexdigest()))
    # total_size_bytes (SPEC 2, S-30)
    distinct = {}
    for n in m['nodes']:
        for v in n['versions']:
            for f in v['files']:
                distinct[f['path']] = f['size']
    tot = sum(distinct.values())
    if 'total_size_bytes' in cont:
        if cont['total_size_bytes'] == tot:
            print('  total_size_bytes ok (%d)' % tot)
        else:
            report('total-size-mismatch', 'warn', 'container.total_size_bytes',
                   'declared %d computed %d' % (cont['total_size_bytes'], tot))
    else:
        print('  total_size_bytes not declared (optional); computed %d' % tot)
    # input_hash on every version (MINI-SPECS 11 "What gets hashed")
    n_ih = 0
    for n in m['nodes']:
        for v in n['versions']:
            if v.get('epistemic') in ('measured', 'inferred') and 'input_hash' not in v:
                report('input-hash-missing', 'warn', n['node_id'], 'v%s is %s' % (v['v'], v['epistemic']))
            if 'input_hash' not in v:
                continue
            h = hashlib.sha256()
            ok = True
            for p in v.get('input_files', []):
                if p not in c.entries:
                    ok = False
                    break
                h.update(bytes.fromhex(sha256(c.read(p))))
            h.update(canonical_json(v.get('input_params') or {}))
            n_ih += 1
            if not ok or h.hexdigest() != v['input_hash']:
                report('input-hash-stale', 'warn', n['node_id'],
                       'declared %s computed %s' % (v['input_hash'], h.hexdigest() if ok else 'n/a'))
    print('  input_hash checked on %d node versions' % n_ih)
    pp = cont.get('preview_prefix_bytes')
    if pp is not None:
        print('  preview_prefix_bytes = %d (a HINT per S-15, not checked as exact)' % pp)

    print('== 7. extraction')
    os.makedirs(out_dir, exist_ok=True)
    primary = m.get('primary', {}) or {}
    results = []

    def extract(slot, nid, fell_back):
        if nid not in nodes:
            report('primary-unresolved', 'error', slot, 'node %r not in graph' % nid)
            return
        n = nodes[nid]
        if nid in dead:
            report('primary-dead', 'error', slot, '%s is dead: %s' % (nid, dead[nid]))
            return
        act = [v for v in n['versions'] if v['v'] == n['active']][0]
        p, how = resolve_payload(n, act)
        if p is None:
            report('payload-file-ambiguous', 'warn', nid, how)
            return
        decl = [f for f in act['files'] if f['path'] == p][0]
        b = c.read(p)
        info = {}
        try:
            if n['type'].startswith('core.geom.'):
                info = check_glb(b, n['type'] in ('core.geom.game', 'core.geom.lod'))
            elif n['type'].startswith('core.audio.'):
                info = check_wav(b)
                desc = [f for f in act['files'] if f.get('role') == 'descriptor']
                if desc:
                    af = strict_json(c.read(desc[0]['path']), desc[0]['path']).get('audio_format', {})
                    exp = (af.get('sample_rate_hz'), af.get('channels'), af.get('bit_depth'))
                    got = (info['sample_rate'], info['channels'], info['bits_per_sample'])
                    info['matches_sidecar_audio_format'] = exp == got
                    if exp != got:
                        report('audio-format-disagrees', 'warn', p, 'sidecar %s, WAV %s' % (exp, got))
        except Exception as e:
            report('payload-invalid', 'error', p, str(e))
        dest = os.path.join(out_dir, p.replace('/', '_'))
        with open(dest, 'wb') as f:
            f.write(b)
        with open(dest, 'rb') as f:
            on_disk = sha256(f.read())
        match = on_disk == decl['sha256']
        print('  %s -> node %s%s -> %s (%s)' % (slot, nid, ' [FALLBACK]' if fell_back else '', p, how))
        print('     wrote %s  %d bytes' % (dest, len(b)))
        print('     declared sha256 %s' % decl['sha256'])
        print('     computed sha256 %s  %s' % (on_disk, 'MATCH' if match else 'MISMATCH'))
        for k, v in info.items():
            print('     %s: %s' % (k, v))
        if not match:
            report('extract-hash-mismatch', 'error', dest)
        results.append((slot, nid, p, dest, decl['sha256'], on_disk, match))

    mesh_id = primary.get('mesh')
    fb = False
    if not mesh_id:
        fb = True
        g = [n['node_id'] for n in m['nodes'] if n['type'] == 'core.geom.game']
        mesh_id = g[0] if g else None
        report('primary-fallback', 'info', 'primary.mesh', 'fell back to core.geom.game %s' % mesh_id)
    if mesh_id:
        extract('primary.mesh', mesh_id, fb)

    snd_id, fb = sound_override or primary.get('sound'), False
    if not snd_id:
        fb = True
        pkg = [n for n in m['nodes'] if n['type'] == 'core.audio.package']
        if pkg:
            pj = strict_json(c.read(pkg[0]['versions'][0]['files'][0]['path']), 'audio package')
            slug = pj.get('preview_effect')
            cand = [n['node_id'] for n in m['nodes'] if n['node_id'] == 'audio-' + str(slug)]
            snd_id = cand[0] if cand else None
        if not snd_id:
            eff = [n['node_id'] for n in m['nodes'] if n['type'] == 'core.audio.effect']
            snd_id = eff[0] if eff else None
        report('primary-fallback', 'info', 'primary.sound', 'fell back to %s' % snd_id)
    if snd_id:
        extract('primary.sound', snd_id, fb)

    print('== summary')
    errs = [r for r in REPORT if r[0] == 'error']
    warns = [r for r in REPORT if r[0] == 'warn']
    print('  signature state : %s' % sig_state)
    print('  dead nodes      : %d' % len(dead))
    print('  extracted       : %d, all hashes match: %s' % (len(results), all(r[6] for r in results)))
    print('  report entries  : %d error, %d warn' % (len(errs), len(warns)))
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
