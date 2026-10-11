"""Reader for crate-nc-v1.gltf.

Every structural rule used here is derived from the package itself (see
REPORT.md).  Numeric codes whose meaning the package does not state are
inferred empirically and the inference is *checked* at run time; if a check
fails the program says so instead of trusting the assumption.

Usage:  python -I crate_reader.py <package_dir> <out_dir>
"""
import hashlib
import json
import math
import os
import struct
import sys

PKG = 'crate-nc-v1.gltf'

# Component counts implied by the "type" strings.  VEC3 / VEC2 / SCALAR are
# self-describing; the counts are confirmed below against byteLength / count.
TYPE_COMPONENTS = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}

# Empirical hypotheses for componentType codes.  Each one is verified per
# accessor (element size vs. bufferView length, decoded values vs. min/max).
COMPONENT_HYPOTHESIS = {
    5126: ('<f', 4, 'float32 little-endian (inferred: 4-byte, decodes to declared min/max)'),
    5123: ('<H', 2, 'uint16 little-endian (inferred: 2-byte, all values < vertex count)'),
}

# bufferView.target codes: meaning inferred from which accessors use them.
TARGET_MEANING = {
    34962: 'vertex-attribute data (inferred: used only by POSITION/NORMAL/TEXCOORD_0 accessors)',
    34963: 'index data (inferred: used only by primitive "indices" accessors)',
}

# Not derivable from the package; reported as opaque.
SAMPLER_NOTE = 'opaque filter code; meaning not stated anywhere in the package'


class Report:
    def __init__(self):
        self.ok = True
        self.lines = []

    def say(self, s=''):
        print(s)
        self.lines.append(s)

    def check(self, cond, what):
        self.say(('  [PASS] ' if cond else '  [FAIL] ') + what)
        if not cond:
            self.ok = False
        return cond


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def load(pkg_dir):
    with open(os.path.join(pkg_dir, PKG), 'rb') as f:
        raw = f.read()
    doc = json.loads(raw.decode('utf-8'))
    return raw, doc


def read_buffer(pkg_dir, uri):
    # Only plain relative file names in the package directory are accepted.
    if os.path.basename(uri) != uri or uri.startswith('.'):
        raise ValueError('refusing non-local uri %r' % uri)
    with open(os.path.join(pkg_dir, uri), 'rb') as f:
        return f.read()


def decode_accessor(doc, buffers, idx):
    acc = doc['accessors'][idx]
    bv = doc['bufferViews'][acc['bufferView']]
    fmt, size, _ = COMPONENT_HYPOTHESIS[acc['componentType']]
    ncomp = TYPE_COMPONENTS[acc['type']]
    start = bv.get('byteOffset', 0) + acc.get('byteOffset', 0)
    n = acc['count'] * ncomp
    data = buffers[bv['buffer']][start:start + n * size]
    flat = struct.unpack('<%d%s' % (n, fmt[1]), data)
    if ncomp == 1:
        return list(flat)
    return [flat[i:i + ncomp] for i in range(0, n, ncomp)]


def list_contents(doc, r):
    r.say('== CONTENTS ==')
    a = doc.get('asset', {})
    r.say('asset: version=%s generator=%r  (producer tool + format version string)'
          % (a.get('version'), a.get('generator')))
    r.say('default scene: %s' % doc.get('scene'))
    for si, s in enumerate(doc.get('scenes', [])):
        r.say('scene[%d] %r  -- root of the node graph' % (si, s.get('name')))
        for ni in s.get('nodes', []):
            n = doc['nodes'][ni]
            m = doc['meshes'][n['mesh']] if 'mesh' in n else None
            xf = [k for k in ('matrix', 'translation', 'rotation', 'scale') if k in n]
            r.say('  node[%d] %r -> mesh[%s] %r  (object placed in scene; transform: %s; children: %s)'
                  % (ni, n.get('name'), n.get('mesh'), m and m.get('name'),
                     ','.join(xf) or 'none/identity', n.get('children', 'none')))
            for pi, p in enumerate(m['primitives'] if m else []):
                r.say('    primitive[%d]: material=%s indices=accessor[%s] mode=%s'
                      % (pi, p.get('material'), p.get('indices'),
                         p.get('mode', 'absent (index count divisible by 3 -> treated as triangles)')))
                for name, ai in p['attributes'].items():
                    acc = doc['accessors'][ai]
                    r.say('      %-10s accessor[%d] %s x %d' % (name, ai, acc['type'], acc['count']))
    for i, m in enumerate(doc.get('materials', [])):
        pbr = m.get('pbrMetallicRoughness', {})
        r.say('material[%d] %r: doubleSided=%s baseColorTexture=texture[%s] metallic=%s roughness=%s'
              % (i, m.get('name'), m.get('doubleSided'),
                 pbr.get('baseColorTexture', {}).get('index'),
                 pbr.get('metallicFactor'), pbr.get('roughnessFactor')))
    for i, t in enumerate(doc.get('textures', [])):
        r.say('texture[%d]: image[%s] via sampler[%s]  (texture = image + sampling settings)'
              % (i, t.get('source'), t.get('sampler')))
    for i, im in enumerate(doc.get('images', [])):
        r.say('image[%d] %r: uri=%s mimeType=%s' % (i, im.get('name'), im.get('uri'), im.get('mimeType')))
    for i, s in enumerate(doc.get('samplers', [])):
        r.say('sampler[%d]: magFilter=%s minFilter=%s  (%s)'
              % (i, s.get('magFilter'), s.get('minFilter'), SAMPLER_NOTE))
    for i, b in enumerate(doc.get('buffers', [])):
        r.say('buffer[%d]: uri=%s byteLength=%d  (raw binary blob)' % (i, b.get('uri'), b['byteLength']))
    for i, bv in enumerate(doc.get('bufferViews', [])):
        r.say('bufferView[%d]: buffer[%d] offset=%d length=%d target=%s -> %s'
              % (i, bv['buffer'], bv.get('byteOffset', 0), bv['byteLength'], bv.get('target'),
                 TARGET_MEANING.get(bv.get('target'), 'unknown')))
    for i, acc in enumerate(doc.get('accessors', [])):
        r.say('accessor[%d]: bufferView[%d] %s x %d, componentType=%d -> %s'
              % (i, acc['bufferView'], acc['type'], acc['count'], acc['componentType'],
                 COMPONENT_HYPOTHESIS.get(acc['componentType'], (0, 0, 'UNKNOWN'))[2]))


def verify(doc, raw, buffers, pkg_dir, r):
    r.say('')
    r.say('== INTEGRITY ==')
    declared = [k for k in _walk_keys(doc) if any(h in k.lower() for h in ('hash', 'sha', 'digest', 'crc', 'checksum'))]
    r.say('declared hashes/checksums found in manifest: %d %s' % (len(declared), declared))
    r.say('(nothing to compare against; computed sha256 values are recorded below)')
    r.say('  %s  %s' % (sha256(raw), PKG))
    for b in doc['buffers']:
        r.say('  %s  %s' % (sha256(buffers[doc['buffers'].index(b)]), b['uri']))
    for im in doc.get('images', []):
        r.say('  %s  %s' % (sha256(read_buffer(pkg_dir, im['uri'])), im['uri']))

    r.say('structural checks:')
    for i, b in enumerate(doc['buffers']):
        r.check(len(buffers[i]) == b['byteLength'],
                'buffer[%d] file size %d == declared byteLength %d' % (i, len(buffers[i]), b['byteLength']))
    # bufferViews in bounds, non-overlapping, aligned
    spans = []
    for i, bv in enumerate(doc['bufferViews']):
        off, ln = bv.get('byteOffset', 0), bv['byteLength']
        r.check(off + ln <= doc['buffers'][bv['buffer']]['byteLength'], 'bufferView[%d] within buffer' % i)
        spans.append((off, off + ln, i))
    spans.sort()
    gaps = [(a[1], b[0]) for a, b in zip(spans, spans[1:]) if a[1] != b[0]]
    r.check(not any(s < e for e, s in gaps), 'bufferViews do not overlap')
    r.say('  [INFO] bufferViews tile buffer contiguously from %d to %d, gaps=%s'
          % (spans[0][0], spans[-1][1], gaps or 'none'))
    # target meaning consistency
    index_accs = {p['indices'] for m in doc['meshes'] for p in m['primitives'] if 'indices' in p}
    for i, acc in enumerate(doc['accessors']):
        tgt = doc['bufferViews'][acc['bufferView']].get('target')
        r.check((tgt == 34963) == (i in index_accs),
                'accessor[%d] target %s consistent with %s role' % (i, tgt, 'index' if i in index_accs else 'attribute'))
    # accessor size, codec hypothesis, min/max, index range, normals
    for mi, m in enumerate(doc['meshes']):
        for p in m['primitives']:
            vcount = doc['accessors'][p['attributes']['POSITION']]['count']
            for name, ai in list(p['attributes'].items()) + [('indices', p.get('indices'))]:
                acc = doc['accessors'][ai]
                bv = doc['bufferViews'][acc['bufferView']]
                ct = acc['componentType']
                if not r.check(ct in COMPONENT_HYPOTHESIS, 'accessor[%d] componentType %d has a hypothesis' % (ai, ct)):
                    continue
                elem = TYPE_COMPONENTS[acc['type']] * COMPONENT_HYPOTHESIS[ct][1]
                r.check(acc['count'] * elem == bv['byteLength'] - acc.get('byteOffset', 0),
                        'accessor[%d] %s: count %d x %d bytes == bufferView length %d'
                        % (ai, name, acc['count'], elem, bv['byteLength']))
                if name != 'indices':
                    r.check(name == 'POSITION' or acc['count'] == vcount,
                            'accessor[%d] %s count matches POSITION count %d' % (ai, name, vcount))
                vals = decode_accessor(doc, buffers, ai)
                if name == 'indices':
                    r.check(len(vals) % 3 == 0, 'mesh[%d] index count %d divisible by 3' % (mi, len(vals)))
                    r.check(max(vals) < vcount, 'mesh[%d] indices max %d < vertex count %d' % (mi, max(vals), vcount))
                    used = len(set(vals))
                    r.say('  [INFO] mesh[%d] indices reference %d/%d vertices, min=%d' % (mi, used, vcount, min(vals)))
                    degenerate = sum(1 for t in range(0, len(vals), 3)
                                     if len({vals[t], vals[t + 1], vals[t + 2]}) < 3)
                    r.check(degenerate == 0, 'mesh[%d] %d degenerate triangles' % (mi, degenerate))
                    continue
                r.check(all(math.isfinite(c) for v in vals for c in v), 'accessor[%d] %s all values finite' % (ai, name))
                if 'min' in acc and 'max' in acc:
                    n = len(acc['min'])
                    cmin = [min(v[k] for v in vals) for k in range(n)]
                    cmax = [max(v[k] for v in vals) for k in range(n)]
                    # declared min/max are printed float32 values; compare after rounding to float32
                    f32 = lambda x: struct.unpack('<f', struct.pack('<f', x))[0]
                    r.check([f32(x) for x in acc['min']] == cmin and [f32(x) for x in acc['max']] == cmax,
                            'accessor[%d] %s decoded min/max == declared min/max (confirms float32 LE)' % (ai, name))
                if name == 'NORMAL':
                    worst = max(abs(math.sqrt(sum(c * c for c in v)) - 1) for v in vals)
                    r.check(worst < 1e-3, 'accessor[%d] NORMAL vectors unit length (max dev %.2e)' % (ai, worst))
                if name.startswith('TEXCOORD'):
                    lo = min(min(v) for v in vals); hi = max(max(v) for v in vals)
                    r.say('  [INFO] accessor[%d] %s range [%.4f, %.4f]' % (ai, name, lo, hi))
    # image signature: compare the first bytes with what the mimeType string names
    for im in doc.get('images', []):
        b = read_buffer(pkg_dir, im['uri'])
        r.check(b[1:4] == b'PNG', 'image %s magic bytes contain "PNG" (mimeType %s)' % (im['uri'], im.get('mimeType')))


def _walk_keys(o, path=''):
    if isinstance(o, dict):
        for k, v in o.items():
            yield path + '/' + k
            yield from _walk_keys(v, path + '/' + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk_keys(v, '%s[%d]' % (path, i))


def pick_primary_mesh(doc):
    # No "primary" marker exists.  Heuristic: the node whose name is the bare
    # object name (others are "<that>_lid", "<that>_latch"), cross-checked
    # against largest vertex count.
    nodes = [n for n in doc['nodes'] if 'mesh' in n]
    names = [n['name'] for n in nodes]
    base = [n for n in nodes if all(o == n['name'] or o.startswith(n['name'] + '_') for o in names)]
    biggest = max(nodes, key=lambda n: doc['accessors'][doc['meshes'][n['mesh']]['primitives'][0]['attributes']['POSITION']]['count'])
    chosen = base[0] if len(base) == 1 else biggest
    return chosen, chosen is biggest


def extract(doc, buffers, pkg_dir, out_dir, r):
    r.say('')
    r.say('== EXTRACTION ==')
    os.makedirs(out_dir, exist_ok=True)
    node, agree = pick_primary_mesh(doc)
    mi = node['mesh']
    mesh = doc['meshes'][mi]
    r.say('primary mesh: node %r -> mesh[%d] %r (name-heuristic and largest-vertex-count agree: %s)'
          % (node['name'], mi, mesh['name'], agree))
    prim = mesh['primitives'][0]
    acc_ids = list(prim['attributes'].values()) + [prim['indices']]
    views = sorted(doc['accessors'][a]['bufferView'] for a in acc_ids)
    bvs = [doc['bufferViews'][v] for v in views]
    lo = bvs[0]['byteOffset']; hi = bvs[-1]['byteOffset'] + bvs[-1]['byteLength']
    contiguous = all(a['byteOffset'] + a['byteLength'] == b['byteOffset'] for a, b in zip(bvs, bvs[1:]))
    r.check(contiguous, 'mesh bufferViews %s are contiguous in buffer (%d..%d)' % (views, lo, hi))
    raw = buffers[bvs[0]['buffer']][lo:hi]
    p_raw = os.path.join(out_dir, 'primary_mesh_%s.bin' % node['name'])
    with open(p_raw, 'wb') as f:
        f.write(raw)

    pos = decode_accessor(doc, buffers, prim['attributes']['POSITION'])
    nrm = decode_accessor(doc, buffers, prim['attributes']['NORMAL'])
    uv = decode_accessor(doc, buffers, prim['attributes']['TEXCOORD_0'])
    idx = decode_accessor(doc, buffers, prim['indices'])
    lines = ['# extracted from %s mesh[%d] %r node %r' % (PKG, mi, mesh['name'], node['name']),
             '# %d vertices, %d triangles; UV v written as-is (no flip)' % (len(pos), len(idx) // 3)]
    lines += ['v %r %r %r' % v for v in pos]
    lines += ['vn %r %r %r' % v for v in nrm]
    lines += ['vt %r %r' % v for v in uv]
    for t in range(0, len(idx), 3):
        a, b, c = (i + 1 for i in idx[t:t + 3])
        lines.append('f %d/%d/%d %d/%d/%d %d/%d/%d' % (a, a, a, b, b, b, c, c, c))
    p_obj = os.path.join(out_dir, 'primary_mesh_%s.obj' % node['name'])
    with open(p_obj, 'w', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')

    mat = doc['materials'][prim['material']]
    tex = doc['textures'][mat['pbrMetallicRoughness']['baseColorTexture']['index']]
    im = doc['images'][tex['source']]
    src = read_buffer(pkg_dir, im['uri'])
    p_tex = os.path.join(out_dir, os.path.basename(im['uri']))
    with open(p_tex, 'wb') as f:
        f.write(src)
    with open(p_tex, 'rb') as f:
        r.check(sha256(f.read()) == sha256(src), 'extracted texture byte-identical to package image')

    r.say('extracted files (no declared hashes exist in the manifest to compare with):')
    for p in (p_raw, p_obj, p_tex):
        with open(p, 'rb') as f:
            r.say('  %s  %s (%d bytes)' % (sha256(f.read()), os.path.basename(p), os.path.getsize(p)))
    r.say('  raw mesh slice = buffer bytes [%d, %d) of %s' % (lo, hi, doc['buffers'][0]['uri']))


def main():
    pkg_dir, out_dir = sys.argv[1], sys.argv[2]
    r = Report()
    raw, doc = load(pkg_dir)
    buffers = [read_buffer(pkg_dir, b['uri']) for b in doc['buffers']]
    list_contents(doc, r)
    verify(doc, raw, buffers, pkg_dir, r)
    extract(doc, buffers, pkg_dir, out_dir, r)
    r.say('')
    r.say('OVERALL: %s' % ('ALL CHECKS PASSED' if r.ok else 'SOME CHECKS FAILED'))
    with open(os.path.join(out_dir, 'run_log.txt'), 'w', newline='\n') as f:
        f.write('\n'.join(r.lines) + '\n')
    sys.exit(0 if r.ok else 1)


if __name__ == '__main__':
    main()
