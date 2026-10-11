"""Open crate-nc-v1.gltf, list its contents, verify integrity, extract the
primary mesh and one texture.

Every encoding rule used here is either read from the .gltf itself or
inferred empirically by testing candidate interpretations against values the
.gltf declares (byte lengths, counts, min/max). Nothing is looked up.

Usage: python -I crate_reader.py <package_dir> <out_dir>
"""
import hashlib
import json
import math
import os
import shutil
import struct
import sys

GLTF_NAME = 'crate-nc-v1.gltf'

# Component counts implied by the accessor "type" names. Confirmed below by
# checking count * ncomp * size == bufferView.byteLength for every accessor.
TYPE_NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}

# Candidate decodings for unknown componentType codes. The right one is
# chosen per code by testing against the file's own data.
CANDIDATES = {
    4: [('<f', 'float32 LE'), ('>f', 'float32 BE'), ('<i', 'int32 LE'),
        ('<I', 'uint32 LE')],
    2: [('<H', 'uint16 LE'), ('>H', 'uint16 BE'), ('<h', 'int16 LE')],
    1: [('<B', 'uint8'), ('<b', 'int8')],
}

problems = []


def check(ok, msg):
    print(('  [ok]   ' if ok else '  [FAIL] ') + msg)
    if not ok:
        problems.append(msg)
    return ok


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main(pkg, out):
    gltf_path = os.path.join(pkg, GLTF_NAME)
    raw = open(gltf_path, 'rb').read()
    doc = json.loads(raw)
    print(f'== Opened {GLTF_NAME} ({len(raw)} bytes, sha256 {sha256(raw)})')

    # ---------------------------------------------------------------- listing
    print('\n== Contents')
    a = doc.get('asset', {})
    print(f"asset: version {a.get('version')!r}, generator {a.get('generator')!r}"
          ' -- the file\'s self-description; no spec text is included')
    for si, s in enumerate(doc['scenes']):
        mark = ' (default, via top-level "scene")' if doc.get('scene') == si else ''
        print(f"scene[{si}] {s.get('name')!r}{mark}: root nodes {s['nodes']}")
    for ni, n in enumerate(doc['nodes']):
        m = doc['meshes'][n['mesh']] if 'mesh' in n else None
        xf = [k for k in ('matrix', 'translation', 'rotation', 'scale') if k in n]
        print(f"  node[{ni}] {n.get('name')!r} -> mesh[{n.get('mesh')}] "
              f"{m.get('name') if m else None!r}; transform keys: {xf or 'none (taken as identity)'}"
              f"; children: {n.get('children', [])}")
    for mi, m in enumerate(doc['meshes']):
        for pi, p in enumerate(m['primitives']):
            print(f"mesh[{mi}] {m.get('name')!r} primitive[{pi}]: "
                  f"attributes {p['attributes']}, indices accessor {p.get('indices')}, "
                  f"material {p.get('material')}, mode {p.get('mode', 'absent')}")
    for mi, m in enumerate(doc['materials']):
        print(f"material[{mi}] {m.get('name')!r}: {json.dumps({k: v for k, v in m.items() if k != 'name'})}")
    for ti, t in enumerate(doc['textures']):
        print(f"texture[{ti}]: image source {t.get('source')}, sampler {t.get('sampler')}")
    for ii, im in enumerate(doc['images']):
        print(f"image[{ii}] {im.get('name')!r}: uri {im.get('uri')!r}, mimeType {im.get('mimeType')!r}")
    for si, s in enumerate(doc.get('samplers', [])):
        print(f"sampler[{si}]: {s}  (numeric filter codes: meaning NOT stated in file)")
    for bi, b in enumerate(doc['buffers']):
        print(f"buffer[{bi}]: uri {b.get('uri')!r}, byteLength {b['byteLength']}")
    for vi, v in enumerate(doc['bufferViews']):
        print(f"bufferView[{vi}]: buffer {v['buffer']} bytes [{v.get('byteOffset', 0)}, "
              f"{v.get('byteOffset', 0) + v['byteLength']}) target {v.get('target')}")
    for ai, ac in enumerate(doc['accessors']):
        print(f"accessor[{ai}]: view {ac['bufferView']}, componentType {ac['componentType']}, "
              f"{ac['count']} x {ac['type']}" + (f", min {ac['min']} max {ac['max']}" if 'min' in ac else ''))

    # Usage map: which semantic each accessor serves (for meanings).
    usage = {}
    for mi, m in enumerate(doc['meshes']):
        for p in m['primitives']:
            for sem, ai in p['attributes'].items():
                usage[ai] = (mi, sem)
            if 'indices' in p:
                usage[p['indices']] = (mi, 'indices')
    tgt = {}
    for ai, (mi, sem) in usage.items():
        tgt.setdefault(doc['bufferViews'][doc['accessors'][ai]['bufferView']].get('target'), set()).add(
            'indices' if sem == 'indices' else 'vertex attribute')
    print('\nObserved correlation of bufferView "target" codes (meaning not stated in file):')
    for k, v in tgt.items():
        print(f'  target {k}: used only for {sorted(v)}')

    # -------------------------------------------------------------- integrity
    print('\n== Integrity')
    print('Declared hashes in package: searching JSON for hash-like fields...')
    hash_fields = []

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if any(h in k.lower() for h in ('hash', 'sha', 'digest', 'checksum', 'crc', 'md5')):
                    hash_fields.append((path + '/' + k, v))
                walk(v, path + '/' + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f'{path}[{i}]')
    walk(doc, '')
    print(f'  found {len(hash_fields)} declared hash field(s): {hash_fields}')

    buffers = []
    for b in doc['buffers']:
        p = os.path.join(pkg, b['uri'])
        data = open(p, 'rb').read() if os.path.exists(p) else None
        check(data is not None, f"buffer file {b['uri']} exists")
        check(data is not None and len(data) == b['byteLength'],
              f"{b['uri']} size {len(data) if data else None} == declared byteLength {b['byteLength']}")
        buffers.append(data)

    spans = []
    for vi, v in enumerate(doc['bufferViews']):
        s, e = v.get('byteOffset', 0), v.get('byteOffset', 0) + v['byteLength']
        check(e <= doc['buffers'][v['buffer']]['byteLength'], f'bufferView[{vi}] within buffer')
        spans.append((s, e, vi))
    spans.sort()
    gaps = [(a[1], b[0]) for a, b in zip(spans, spans[1:]) if a[1] != b[0]]
    check(not gaps and spans[0][0] == 0 and spans[-1][1] == doc['buffers'][0]['byteLength'],
          f'bufferViews tile buffer exactly, no gaps/overlaps (gaps: {gaps})')

    # Infer byte size per componentType code from byteLength arithmetic.
    csize = {}
    for ai, ac in enumerate(doc['accessors']):
        v = doc['bufferViews'][ac['bufferView']]
        n = ac['count'] * TYPE_NCOMP[ac['type']]
        sz, rem = divmod(v['byteLength'], n)
        check(rem == 0, f'accessor[{ai}] byteLength {v["byteLength"]} divisible by count*ncomp {n}')
        if csize.setdefault(ac['componentType'], sz) != sz:
            check(False, f'componentType {ac["componentType"]} has inconsistent size')
    print(f'  inferred component byte sizes: {csize}')

    # Choose a decoding per componentType by testing candidates.
    def raw_view(ac):
        v = doc['bufferViews'][ac['bufferView']]
        o = v.get('byteOffset', 0) + ac.get('byteOffset', 0)
        return buffers[v['buffer']][o:o + v['byteLength']]

    def decode(ac, fmt):
        n = ac['count'] * TYPE_NCOMP[ac['type']]
        flat = struct.unpack(fmt[0] + fmt[1:] * n, raw_view(ac))
        k = TYPE_NCOMP[ac['type']]
        return [flat[i:i + k] for i in range(0, n, k)]

    def score(ct, fmt):
        """Return (passes, reason) for decoding componentType ct with fmt."""
        for ai, ac in enumerate(doc['accessors']):
            if ac['componentType'] != ct:
                continue
            vals = decode(ac, fmt)
            if any(isinstance(x, float) and not math.isfinite(x) for t in vals for x in t):
                return False, f'non-finite in accessor {ai}'
            if 'min' in ac:
                k = TYPE_NCOMP[ac['type']]
                mn = [min(t[c] for t in vals) for c in range(k)]
                mx = [max(t[c] for t in vals) for c in range(k)]
                if not all(math.isclose(x, y, rel_tol=1e-6, abs_tol=1e-9) for x, y in zip(mn + mx, ac['min'] + ac['max'])):
                    return False, f'min/max mismatch in accessor {ai}'
            if usage.get(ai, (0, ''))[1] == 'indices':
                mi = usage[ai][0]
                nv = doc['accessors'][doc['meshes'][mi]['primitives'][0]['attributes']['POSITION']]['count']
                if not all(0 <= t[0] < nv for t in vals):
                    return False, f'index out of range in accessor {ai}'
        return True, 'consistent with all declared min/max and index ranges'

    decoding = {}
    for ct, sz in csize.items():
        for fmt, label in CANDIDATES[sz]:
            ok, why = score(ct, fmt)
            print(f'  componentType {ct} as {label}: {"ACCEPT" if ok else "reject"} ({why})')
            if ok and ct not in decoding:
                decoding[ct] = (fmt, label)
        check(ct in decoding, f'componentType {ct} has a decoding consistent with file data')

    data = {ai: decode(ac, decoding[ac['componentType']][0]) for ai, ac in enumerate(doc['accessors'])}

    for ai, ac in enumerate(doc['accessors']):
        if 'min' in ac:
            check(True, f'accessor[{ai}] computed min/max == declared')  # enforced by decoding choice
    for ai, (mi, sem) in usage.items():
        if sem == 'NORMAL':
            bad = sum(1 for t in data[ai] if abs(math.sqrt(sum(x * x for x in t)) - 1) > 1e-3)
            check(bad == 0, f'accessor[{ai}] NORMAL vectors unit length ({bad} not)')
        if sem.startswith('TEXCOORD'):
            lo = min(min(t) for t in data[ai]); hi = max(max(t) for t in data[ai])
            print(f'  [info] accessor[{ai}] {sem} range [{lo:.4f}, {hi:.4f}]')
        if sem == 'indices':
            check(ac_count(doc, ai) % 3 == 0, f'accessor[{ai}] index count divisible by 3 (triangle list hypothesis)')
    for im in doc['images']:
        p = os.path.join(pkg, im['uri'])
        check(os.path.exists(p), f"image file {im['uri']} exists")
        if os.path.exists(p):
            print(f"  [info] {im['uri']}: {os.path.getsize(p)} bytes, sha256 {sha256(open(p, 'rb').read())}"
                  ' (no declared hash to compare against)')

    # -------------------------------------------------------------- extraction
    print('\n== Extraction')
    os.makedirs(out, exist_ok=True)
    # "Primary" is not defined in the file. Choose the mesh with the most
    # triangles; it is also the node whose name has no suffix.
    def tri_count(mi):
        return sum(ac_count(doc, p['indices']) // 3 for p in doc['meshes'][mi]['primitives'])
    pm = max(range(len(doc['meshes'])), key=tri_count)
    node = next(n for n in doc['nodes'] if n.get('mesh') == pm)
    print(f"primary mesh: mesh[{pm}] {doc['meshes'][pm]['name']!r} (node {node['name']!r}), "
          f'{tri_count(pm)} triangles -- chosen as largest; file does not designate one')
    prim = doc['meshes'][pm]['primitives'][0]
    at = prim['attributes']
    P, N, T, I = data[at['POSITION']], data[at['NORMAL']], data[at['TEXCOORD_0']], data[prim['indices']]
    results = []
    obj_path = os.path.join(out, 'primary_mesh.obj')
    with open(obj_path, 'w', newline='\n') as f:
        f.write(f"# mesh[{pm}] {doc['meshes'][pm]['name']} from {GLTF_NAME}\n")
        f.write('# texcoords written as stored (no V flip applied)\n')
        for v in P: f.write('v %.9g %.9g %.9g\n' % v)
        for v in T: f.write('vt %.9g %.9g\n' % v)
        for v in N: f.write('vn %.9g %.9g %.9g\n' % v)
        for i in range(0, len(I), 3):
            a, b, c = (I[i][0] + 1, I[i + 1][0] + 1, I[i + 2][0] + 1)
            f.write(f'f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}\n')
    results.append(obj_path)
    # Raw byte-exact slices of the mesh's buffer data.
    for sem, ai in list(at.items()) + [('indices', prim['indices'])]:
        p = os.path.join(out, f'primary_mesh_{sem}.raw')
        open(p, 'wb').write(raw_view(doc['accessors'][ai]))
        results.append(p)
    # One texture: the base colour texture of the primitive's material.
    tex = doc['materials'][prim['material']]['pbrMetallicRoughness']['baseColorTexture']['index']
    img = doc['images'][doc['textures'][tex]['source']]
    src = os.path.join(pkg, img['uri'])
    dst = os.path.join(out, img['uri'])
    shutil.copyfile(src, dst)
    results.append(dst)
    check(sha256(open(src, 'rb').read()) == sha256(open(dst, 'rb').read()), 'texture copy byte-identical to source')

    for p in results:
        print(f'  {os.path.basename(p)}: {os.path.getsize(p)} bytes, sha256 {sha256(open(p, "rb").read())}, declared: NONE')

    print('\n== Summary')
    print(f'decodings chosen: { {k: v[1] for k, v in decoding.items()} }')
    print(f'declared hashes verified: 0 of 0 (package declares none)')
    print(f'problems: {len(problems)}')
    for m in problems:
        print('  -', m)
    return 1 if problems else 0


def ac_count(doc, ai):
    return doc['accessors'][ai]['count']


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
