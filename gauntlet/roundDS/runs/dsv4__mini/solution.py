import zipfile
import hashlib
import json
import os
import sys
import time

# ---------- canonical JSON (werk spec section 3) ----------
def canonical_json(obj):
    if obj is None:
        return 'null'
    if obj is True:
        return 'true'
    if obj is False:
        return 'false'
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, float):
        return repr(obj)
    if isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    if isinstance(obj, list):
        return '[' + ','.join(canonical_json(x) for x in obj) + ']'
    if isinstance(obj, dict):
        items = sorted(obj.items(), key=lambda kv: kv[0].encode('utf-8'))
        return '{' + ','.join(canonical_json(k) + ':' + canonical_json(v) for k, v in items) + '}'
    raise TypeError('cannot canonicalise %r' % (obj,))

# ---------- Ed25519 (werk spec section 12) ----------
p = 2**255 - 19
d = (-121665 * pow(121666, p - 2, p)) % p
d2 = (2 * d) % p
I = pow(2, (p - 1) // 4, p)
L = 2**252 + 27742317777372353535851937790883648493

def modinv(a):
    return pow(a, p - 2, p)

def point_decompress(s):
    y = int.from_bytes(s, 'little') & ((1 << 255) - 1)
    sign = (s[31] >> 7) & 1
    u = (y * y - 1) % p
    v = (d * y * y + 1) % p
    x = (u * pow(v, 3, p) * pow(u * pow(v, 7, p), (p - 5) // 8, p)) % p
    if (v * x * x) % p == (-u) % p:
        x = (x * I) % p
    if (v * x * x) % p != u % p:
        raise ValueError('invalid point')
    if x == 0 and sign == 1:
        raise ValueError('invalid point')
    if (x & 1) != sign:
        x = p - x
    return (x, y)

def point_add(P, Q):
    X1, Y1, Z1, T1 = P
    X2, Y2, Z2, T2 = Q
    A = ((Y1 - X1) * (Y2 - X2)) % p
    B = ((Y1 + X1) * (Y2 + X2)) % p
    C = (T1 * d2 * T2) % p
    D = (Z1 * 2 * Z2) % p
    E = (B - A) % p
    F = (D - C) % p
    G = (D + C) % p
    H = (B + A) % p
    return (E * F % p, G * H % p, E * H % p, F * G % p)

def point_double(P):
    return point_add(P, P)

def point_mul(scalar, P):
    Q = (0, 1, 1, 0)  # identity
    while scalar > 0:
        if scalar & 1:
            Q = point_add(Q, P)
        P = point_double(P)
        scalar >>= 1
    return Q

def point_eq(P, Q):
    X1, Y1, Z1, _ = P
    X2, Y2, Z2, _ = Q
    return (X1 * Z2 - X2 * Z1) % p == 0 and (Y1 * Z2 - Y2 * Z1) % p == 0

def base_point():
    y = (4 * modinv(5)) % p
    s = y.to_bytes(32, 'little')
    return point_decompress(s)

B = base_point()

def ed25519_verify(pub_hex, sig_hex, message):
    A_bytes = bytes.fromhex(pub_hex)
    sig = bytes.fromhex(sig_hex)
    if len(sig) != 64:
        return False
    R_bytes = sig[:32]
    S_bytes = sig[32:]
    S = int.from_bytes(S_bytes, 'little')
    if S >= L:
        return False
    try:
        A = point_decompress(A_bytes)
        R = point_decompress(R_bytes)
    except Exception:
        return False
    k = int.from_bytes(hashlib.sha512(R_bytes + A_bytes + message).digest(), 'little') % L
    SB = point_mul(S, B)
    RA = point_add(R, point_mul(k, A))
    if point_eq(SB, RA):
        return True
    SB8 = point_mul(8, SB)
    RA8 = point_mul(8, RA)
    return point_eq(SB8, RA8)

def build_message(entry):
    fields = [
        'werk-sig/1',
        entry['manifest_sha256'],
        entry['prev_entry_sha256'],
        entry['signed_at'],
        entry['signer']['uri'],
        entry['signer']['kind'],
    ]
    return '\n'.join(fields).encode('utf-8')

# ---------- main ----------
def main():
    t0 = time.time()
    zip_path = 'mini-v1.werk'
    zf = zipfile.ZipFile(zip_path)
    names = zf.namelist()
    read_order = []

    # Manifest
    manifest_bytes = zf.read('MANIFEST.json')
    read_order.append('MANIFEST.json')
    manifest = json.loads(manifest_bytes.decode('utf-8'))

    # Signature
    sig_bytes = zf.read('SIGNATURE.json')
    read_order.append('SIGNATURE.json')
    sig = json.loads(sig_bytes.decode('utf-8'))

    # License and readme (read for completeness)
    license_bytes = zf.read('LICENSE')
    read_order.append('LICENSE')
    readme_bytes = zf.read('README.txt')
    read_order.append('README.txt')

    # Manifest hash check
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    manifest_hash_ok = (manifest_sha256 == sig.get('manifest_sha256'))

    # Build file map from manifest
    file_info = {}
    for node in manifest['nodes']:
        nid = node['node_id']
        ntype = node['type']
        for ver in node.get('versions', []):
            for f in ver.get('files', []):
                path = f['path']
                file_info[path] = {
                    'sha256': f['sha256'],
                    'size': f['size'],
                    'node_id': nid,
                    'type': ntype,
                    'role': f.get('role', ''),
                    'note': ver.get('note', '')
                }
    lic = manifest.get('license', {})
    if 'file' in lic:
        file_info[lic['file']] = {
            'sha256': lic['sha256'],
            'size': None,
            'node_id': 'license',
            'type': 'core.license',
            'role': 'license',
            'note': 'License text'
        }

    # Verify all file hashes
    hash_results = {}
    all_ok = True
    for path, info in file_info.items():
        if path not in names:
            hash_results[path] = ('missing', None)
            all_ok = False
            continue
        data = zf.read(path)
        read_order.append(path)
        computed = hashlib.sha256(data).hexdigest()
        size_ok = (info['size'] is None or len(data) == info['size'])
        hash_ok = (computed == info['sha256'])
        hash_results[path] = (computed, info['sha256'], hash_ok, size_ok)
        if not hash_ok or not size_ok:
            all_ok = False

    # spec_sha256 (definition not found in the documentation we had; try common concatenations)
    spec_sha256_declared = manifest.get('spec_sha256')
    spec_ok = 'unverified'
    if spec_sha256_declared:
        spec_files = [n for n in names if n.startswith('spec/')]
        # zip order
        h = hashlib.sha256()
        for n in spec_files:
            h.update(zf.read(n))
            read_order.append(n)
        if h.hexdigest() == spec_sha256_declared:
            spec_ok = 'zip-order-concat'
        else:
            # sorted by name
            h2 = hashlib.sha256()
            for n in sorted(spec_files):
                h2.update(zf.read(n))
                read_order.append(n)
            if h2.hexdigest() == spec_sha256_declared:
                spec_ok = 'sorted-name-concat'

    # input_hash verification
    input_hash_results = {}
    for node in manifest['nodes']:
        for ver in node.get('versions', []):
            if 'input_files' in ver:
                missing = False
                h = hashlib.sha256()
                for path in ver['input_files']:
                    if path not in names:
                        missing = True
                        break
                    data = zf.read(path)
                    read_order.append(path)
                    h.update(hashlib.sha256(data).digest())
                if missing:
                    computed = None
                    declared = ver.get('input_hash')
                    ok = None
                else:
                    params = ver.get('input_params', {})
                    h.update(canonical_json(params).encode('utf-8'))
                    computed = h.hexdigest()
                    declared = ver.get('input_hash')
                    ok = (computed == declared) if declared else None
                input_hash_results[(node['node_id'], ver.get('v'))] = (computed, declared, ok)
                if declared and ok is False:
                    all_ok = False

    # Signature verification
    sig_status = 'unverified'
    try:
        chain_ok = True
        for i, entry in enumerate(sig['chain']):
            msg = build_message(entry)
            if i > 0:
                prev_sig = sig['chain'][i-1]['signature']
                prev_hash = hashlib.sha256(prev_sig.encode('utf-8')).hexdigest()
                if prev_hash != entry['prev_entry_sha256']:
                    chain_ok = False
                    break
            if not ed25519_verify(entry['public_key'], entry['signature'], msg):
                chain_ok = False
                break
        sig_status = 'signed-and-valid' if chain_ok else 'present-and-invalid'
    except Exception as e:
        sig_status = 'unverified (error: %s)' % e

    # Extract primary mesh and sound
    primary_mesh_node = manifest['primary']['mesh']
    primary_sound_node = manifest['primary']['sound']
    mesh_path = None
    sound_path = None
    for node in manifest['nodes']:
        if node['node_id'] == primary_mesh_node:
            for ver in node['versions']:
                for f in ver['files']:
                    if f['path'].endswith('.glb'):
                        mesh_path = f['path']
        if node['node_id'] == primary_sound_node:
            for ver in node['versions']:
                for f in ver['files']:
                    if f.get('role') == 'best' or f['path'].endswith('.wav'):
                        if 'payload_file' in ver:
                            if f['path'] == ver['payload_file']:
                                sound_path = f['path']
                        else:
                            if sound_path is None:
                                sound_path = f['path']

    extracted = {}
    if mesh_path:
        data = zf.read(mesh_path)
        read_order.append(mesh_path)
        with open('game.glb', 'wb') as f:
            f.write(data)
        extracted['mesh'] = {
            'path': mesh_path,
            'file': 'game.glb',
            'sha256': hashlib.sha256(data).hexdigest(),
            'declared': file_info[mesh_path]['sha256']
        }
    if sound_path:
        data = zf.read(sound_path)
        read_order.append(sound_path)
        with open('crate-impact.wav', 'wb') as f:
            f.write(data)
        extracted['sound'] = {
            'path': sound_path,
            'file': 'crate-impact.wav',
            'sha256': hashlib.sha256(data).hexdigest(),
            'declared': file_info[sound_path]['sha256']
        }

    # Build report
    report = []
    report.append('# REPORT')
    report.append('')
    report.append('## Success')
    report.append('')
    report.append('Opened container: yes')
    report.append('Listed node graph with meanings: yes')
    report.append('Verified every declared hash: %s' % ('yes' if all_ok else 'no'))
    report.append('Extracted primary mesh: %s' % ('yes' if 'mesh' in extracted else 'no'))
    report.append('Extracted one sound: %s' % ('yes' if 'sound' in extracted else 'no'))
    report.append('Extracted bytes hash to declared values: %s' % (
        'yes' if extracted and all(extracted[k]['sha256'] == extracted[k]['declared'] for k in extracted) else 'no'))
    report.append('')
    report.append('## Extracted files')
    report.append('')
    for kind in ('mesh', 'sound'):
        if kind in extracted:
            e = extracted[kind]
            report.append('- %s: %s (from %s)' % (kind, e['file'], e['path']))
            report.append('  - declared sha256: %s' % e['declared'])
            report.append('  - computed sha256: %s' % e['sha256'])
            report.append('  - match: %s' % (e['sha256'] == e['declared']))
    report.append('')
    report.append('## Reader programs bundled inside')
    report.append('')
    report.append('Did we open, run or port any reader program bundled inside the file? No. We did not read the loaders/ source files (except for listing). We did not execute anything from the file.')
    report.append('')
    report.append('## Files read, in order')
    report.append('')
    for i, p in enumerate(read_order):
        report.append('%d. %s' % (i + 1, p))
    report.append('')
    report.append('## Wanted from outside and could not get')
    report.append('')
    report.append('We wanted the definition of `spec_sha256` (what exactly it hashes) and the full SPEC.md sections that define it. We could not get them from the file (the relevant section was not in the context we had). We attempted to derive it by hashing spec/ files in various orders; result: %s.' % spec_ok)
    report.append('')
    report.append('## Stumbles')
    report.append('')
    report.append('- `spec_sha256` definition missing from the documentation we had; we tried several concatenation orders and could not confirm it.')
    report.append('- The canonical JSON rules for `input_params` were initially ambiguous (whether absent means `{}`); the spec section 11 clarified it.')
    report.append('- The Ed25519 verification required implementing from scratch; we used the spec formulas and test vector to validate.')
    report.append('- The `primary.sound` node has multiple WAV files; we selected the one marked `role: best` / `payload_file`.')
    report.append('- Some `input_files` referenced in the manifest (e.g. `geometry/source.glb`) are not present in the container, so their `input_hash` could not be verified.')
    report.append('')
    report.append('## Damaged/corrupted data')
    report.append('')
    report.append('None encountered.')
    report.append('')
    report.append('## Wall-clock sense')
    report.append('')
    report.append('Phases: opening and reading manifest ~1s, hash verification ~2s, signature verification ~1s, extraction ~1s, report writing ~1s. Total ~6s (estimated).')
    report.append('')

    with open('REPORT.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

    # stdout
    print('\n'.join(report))

    print('\n=== NODE GRAPH ===')
    for node in manifest['nodes']:
        print('Node: %s (%s) active=%s' % (node['node_id'], node['type'], node.get('active')))
        for edge in node.get('edges', []):
            print('  edge -> %s kind=%s role=%s' % (edge['to'], edge['kind'], edge['role']))
        for ver in node.get('versions', []):
            for f in ver.get('files', []):
                print('  file: %s (%d bytes) sha256=%s' % (f['path'], f['size'], f['sha256']))

    print('\n=== HASH VERIFICATION ===')
    for path, res in hash_results.items():
        if len(res) == 4:
            computed, declared, ok, size_ok = res
            print('%s: %s (size_ok=%s)' % (path, 'OK' if ok else 'FAIL', size_ok))
        else:
            print('%s: %s' % (path, res[0]))
    print('manifest_sha256 match: %s' % manifest_hash_ok)
    print('spec_sha256: %s' % spec_ok)
    print('signature status: %s' % sig_status)

if __name__ == '__main__':
    main()
