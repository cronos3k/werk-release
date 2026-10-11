#!/usr/bin/env python3
"""werk_reader.py - an independent reader for a .werk package.

Written only from the documentation carried inside mini-v1.werk
(spec/README.md, spec/SPEC.md, spec/MINI-SPECS.md, spec/layouts/*,
spec/examples/restposes.example.hex.txt, spec/conventions-map.json).
The bundled loaders/ were never opened.

Usage:  python -I werk_reader.py PACKAGE.werk [OUTDIR]

Does, in order:
  1. opens the store-mode zip from its end (MINI-SPECS §5), refuses zip64
  2. reads MANIFEST.json (UTF-8, no BOM, no duplicate keys)
  3. checks conventions against what this reader supports
  4. verifies SIGNATURE.json (Ed25519, MINI-SPECS §12; self-tested first)
  5. walks nodes[], checks size + sha256 of every file, license.sha256,
     spec_sha256, input_hash wherever every input is present, nothing-floats
  6. dispatches by type (WKRP envelope, GLB, WAV, PNG structural checks)
  7. lists the node graph with meanings
  8. extracts primary.mesh and primary.sound via SPEC §2.1 and re-hashes them
Exit status per SPEC §10.2: 0 ok, 1 error entries, 2 container refused.
"""
import sys, os, struct, json, hashlib, math

# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------
REPORT = []


def report(code, severity, subject, msg=''):
    REPORT.append((severity, code, subject, msg))


# --------------------------------------------------------------------------
# CRC-32 (MINI-SPECS §6)
# --------------------------------------------------------------------------
_CRC_TABLE = []
for _n in range(256):
    _c = _n
    for _ in range(8):
        _c = (_c >> 1) ^ (0xEDB88320 if _c & 1 else 0)
    _CRC_TABLE.append(_c)


def crc32(data):
    crc = 0xFFFFFFFF
    for b in data:
        crc = (crc >> 8) ^ _CRC_TABLE[(crc ^ b) & 0xFF]
    return crc ^ 0xFFFFFFFF


assert crc32(b'123456789') == 0xCBF43926

# SHA-256 / SHA-512 test vectors from MINI-SPECS §11, so hashlib is proved, not trusted
assert hashlib.sha256(b'abc').hexdigest() == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
assert hashlib.sha512(b'abc').hexdigest().startswith('ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a')


# --------------------------------------------------------------------------
# zip, store mode (MINI-SPECS §5)
# --------------------------------------------------------------------------
class ContainerRefused(Exception):
    pass


def open_zip(buf):
    size = len(buf)
    if size < 22:
        raise ContainerRefused('not-a-zip: shorter than an EOCD')
    lowest = max(0, size - 22 - 65535)
    eocd = -1
    for off in range(size - 22, lowest - 1, -1):
        if buf[off:off + 4] == b'PK\x05\x06':
            clen = struct.unpack_from('<H', buf, off + 20)[0]
            if off + 22 + clen == size:
                eocd = off
                break
    if eocd < 0:
        raise ContainerRefused('no-eocd')
    disk, cd_disk, n_here, n_total, cd_size, cd_off, clen = struct.unpack_from('<HHHHIIH', buf, eocd + 4)
    # zip64 detection (§5.5) - required even of zip32-only readers
    if (n_here == 0xFFFF or n_total == 0xFFFF or cd_size == 0xFFFFFFFF or cd_off == 0xFFFFFFFF
            or (eocd >= 20 and buf[eocd - 20:eocd - 16] == b'PK\x06\x07')):
        raise ContainerRefused('zip64-unsupported')
    if cd_off + cd_size > eocd:
        raise ContainerRefused('central directory outside file')
    entries = {}
    order = []
    p = cd_off
    for _ in range(n_total):
        if buf[p:p + 4] != b'PK\x01\x02':
            raise ContainerRefused('bad central directory signature at %d' % p)
        (vmade, vneed, flags, method, mt, md, crc, csz, usz, nlen, xlen, klen,
         dstart, iattr, eattr, lho) = struct.unpack_from('<HHHHHHIIIHHHHHII', buf, p + 4)
        name = buf[p + 46:p + 46 + nlen].decode('utf-8')
        p += 46 + nlen + xlen + klen
        if csz == 0xFFFFFFFF or usz == 0xFFFFFFFF or lho == 0xFFFFFFFF:
            raise ContainerRefused('zip64-unsupported (entry %s)' % name)
        if name.endswith('/'):
            continue  # directory entries optional (§5.4)
        # §5.4 name rules
        if name.startswith('/') or '\\' in name or ':' in name or '..' in name.split('/'):
            report('zip-bad-name', 'error', name, 'illegal entry name; not read')
            continue
        if flags & 0x08:
            report('zip-data-descriptor', 'warn', name, 'flag bit 3 set (werk writers MUST NOT)')
        if buf[lho:lho + 4] != b'PK\x03\x04':
            report('zip-bad-local-header', 'error', name, 'no local header at %d' % lho)
            continue
        ln, lx = struct.unpack_from('<HH', buf, lho + 26)
        lmethod = struct.unpack_from('<H', buf, lho + 8)[0]
        data_off = lho + 30 + ln + lx
        e = dict(name=name, method=method, crc=crc, csize=csz, usize=usz, offset=data_off, lho=lho)
        if method != 0 or lmethod != 0:
            e['data'] = None
            report('zip-method-unsupported', 'error', name, 'method %d; this reader supports store only' % method)
        elif data_off + csz > size:
            e['data'] = None
            report('zip-entry-truncated', 'error', name)
        else:
            d = buf[data_off:data_off + csz]
            if csz != usz:
                report('zip-size-mismatch', 'error', name, 'stored entry with csize != usize')
            if crc32(d) != crc:
                report('zip-crc-mismatch', 'error', name, 'CRC-32 %08x, central directory says %08x' % (crc32(d), crc))
            e['data'] = d
        if name in entries:
            report('zip-duplicate-entry', 'error', name)
        entries[name] = e
        order.append(name)
    return entries, order, dict(eocd=eocd, cd_off=cd_off, cd_size=cd_size, n=n_total)


# --------------------------------------------------------------------------
# JSON (MINI-SPECS §2, §3)
# --------------------------------------------------------------------------
def _no_dupes(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError('duplicate key %r' % k)
        d[k] = v
    return d


def _no_nonfinite(tok):
    raise ValueError('non-finite number %s' % tok)


def parse_json(data):
    if data[:3] == b'\xef\xbb\xbf':
        raise ValueError('UTF-8 BOM present (MUST be rejected)')
    return json.loads(data.decode('utf-8'), object_pairs_hook=_no_dupes, parse_constant=_no_nonfinite)


def canonical_json(v):
    """MINI-SPECS §3 'Canonical JSON (for hashing only)'."""
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


# --------------------------------------------------------------------------
# Ed25519 verify (MINI-SPECS §12), written from the parameters in that section
# --------------------------------------------------------------------------
P_ = 2 ** 255 - 19
L_ = 2 ** 252 + 27742317777372353535851937790883648493


def _inv(a):
    return pow(a, P_ - 2, P_)


D_ = (-121665 * _inv(121666)) % P_
I_ = pow(2, (P_ - 1) // 4, P_)


def _recover_x(y, sign):
    u = (y * y - 1) % P_
    v = (D_ * y * y + 1) % P_
    x = (u * pow(v, 3, P_) * pow(u * pow(v, 7, P_), (P_ - 5) // 8, P_)) % P_
    if (v * x * x - (-u)) % P_ == 0:
        x = (x * I_) % P_
    if (v * x * x - u) % P_ != 0:
        return None
    if x == 0 and sign == 1:
        return None
    if (x & 1) != sign:
        x = P_ - x
    return x


def _decompress(b):
    if len(b) != 32:
        return None
    n = int.from_bytes(b, 'little')
    sign = n >> 255
    y = n & ((1 << 255) - 1)
    if y >= P_:
        return None
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, (x * y) % P_)


def _add(p, q):
    X1, Y1, Z1, T1 = p
    X2, Y2, Z2, T2 = q
    A = (Y1 - X1) * (Y2 - X2) % P_
    B = (Y1 + X1) * (Y2 + X2) % P_
    C = T1 * 2 * D_ * T2 % P_
    Dd = Z1 * 2 * Z2 % P_
    E, F, G, H = B - A, Dd - C, Dd + C, B + A
    return (E * F % P_, G * H % P_, F * G % P_, E * H % P_)


def _mul(s, p):
    q = (0, 1, 1, 0)  # neutral
    while s > 0:
        if s & 1:
            q = _add(q, p)
        p = _add(p, p)
        s >>= 1
    return q


def _eq(p, q):
    X1, Y1, Z1, _ = p
    X2, Y2, Z2, _ = q
    return (X1 * Z2 - X2 * Z1) % P_ == 0 and (Y1 * Z2 - Y2 * Z1) % P_ == 0


_By = (4 * _inv(5)) % P_
_B = (_recover_x(_By, 0), _By, 1, (_recover_x(_By, 0) * _By) % P_)


def ed25519_verify(pub, msg, sig):
    if len(sig) != 64:
        return False
    A = _decompress(pub)
    R = _decompress(sig[:32])
    if A is None or R is None:
        return False
    S = int.from_bytes(sig[32:], 'little')
    if S >= L_:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), 'little') % L_
    lhs = _mul(8, _mul(S, _B))
    rhs = _mul(8, _add(R, _mul(k, A)))
    return _eq(lhs, rhs)


def ed25519_selftest():
    """RFC 8032 vector 1 and the signed-message example, both quoted in MINI-SPECS §12."""
    pub = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
    sig = bytes.fromhex('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b')
    if not ed25519_verify(pub, b'', sig):
        return False
    if ed25519_verify(pub, b'x', sig):
        return False
    msg = sig_message('c421d2e85a9455f0be794ca8ee673f727a7ef67485d631e374f95c4a6d6ce61a', '0' * 64,
                      '2026-08-08T09:00:00Z', 'urn:werk:fixture:rfc8032-vector-1', 'service')
    if len(msg) != 203 or hashlib.sha256(msg).hexdigest() != '11e260cc16bc454f39f1aa6d56679c868ba1e83d33e3c22a462040b32a92165a':
        return False
    sig2 = bytes.fromhex('55720b6fc38d680f8ca7523c0d8cec5045c7247f7158ab54eafd03d6ea0eedb1'
                         'aeb4902b4704a5c2e78d7713b375068748bea4fd116a2d3a49f6010074c6410d')
    return ed25519_verify(pub, msg, sig2)


def sig_message(manifest_sha256, prev, signed_at, uri, kind):
    """MINI-SPECS §12.1 / SPEC §6."""
    fields = ['werk-sig/1', manifest_sha256, prev, signed_at, uri, kind]
    for f in fields:
        if '\n' in f:
            raise ValueError('LF inside a signed field')
    return '\n'.join(fields).encode('utf-8')


def verify_signature(entries, manifest_bytes):
    """Returns one of the four fixed tokens (SPEC §10 step 4)."""
    e = entries.get('SIGNATURE.json')
    if e is None:
        report('signature-absent', 'warn', 'SIGNATURE.json', 'package is anonymous')
        return 'absent', []
    if e['data'] is None:
        report('signature-unverified', 'warn', 'SIGNATURE.json', 'entry unreadable')
        return 'unverified', []
    if not ed25519_selftest():
        report('signature-unverified', 'warn', 'SIGNATURE.json', 'own Ed25519 failed its self-test; did not check')
        return 'unverified', []
    try:
        s = parse_json(e['data'])
        chain = s['chain']
    except Exception as ex:
        report('signature-invalid', 'error', 'SIGNATURE.json', 'unparseable: %s' % ex)
        return 'present-and-invalid', []
    if s.get('algorithm') != 'ed25519':
        report('signature-unverified', 'warn', 'SIGNATURE.json', 'algorithm %r not supported' % s.get('algorithm'))
        return 'unverified', []
    actual = hashlib.sha256(manifest_bytes).hexdigest()
    lines = []
    ok = True
    prev_sig = None
    for i, c in enumerate(chain):
        expect_prev = '0' * 64 if i == 0 else hashlib.sha256(prev_sig.encode('utf-8')).hexdigest()
        if c.get('prev_entry_sha256') != expect_prev:
            ok = False
            lines.append('entry %d: prev_entry_sha256 wrong' % i)
        msg = sig_message(c['manifest_sha256'], c['prev_entry_sha256'], c['signed_at'],
                          c['signer']['uri'], c['signer']['kind'])
        good = ed25519_verify(bytes.fromhex(c['public_key']), msg, bytes.fromhex(c['signature']))
        lines.append('entry %d: signer=%s key=%s... ed25519=%s' % (i, c['signer']['uri'], c['public_key'][:16],
                                                                      'valid' if good else 'INVALID'))
        ok = ok and good
        prev_sig = c['signature']
    if chain:
        last = chain[-1]['manifest_sha256']
        if last != actual:
            ok = False
            lines.append('last entry manifest_sha256 %s != actual %s' % (last, actual))
        if s.get('manifest_sha256') != actual:
            ok = False
            lines.append('top-level manifest_sha256 != actual')
    else:
        ok = False
        lines.append('empty chain')
    if ok:
        report('signature-valid', 'info', 'SIGNATURE.json', 'chain of %d verifies; key is a published DEV key, not a trust anchor' % len(chain))
        return 'signed-and-valid', lines
    report('signature-invalid', 'error', 'SIGNATURE.json', '; '.join(lines))
    return 'present-and-invalid', lines


# --------------------------------------------------------------------------
# conventions (SPEC §2, §10 step 3, §10.1-10.2)
# --------------------------------------------------------------------------
SUPPORTED = {
    '3d-entity/1': {
        'endianness': 'le', 'units_per_meter': 1.0, 'length_unit': 'metre', 'angle_unit': 'radian',
        'time_unit': 'second', 'mass_unit': 'kilogram', 'up_axis': 'y', 'forward_axis': '-z',
        'right_axis': '+x', 'handedness': 'right', 'winding': 'ccw', 'quat_order': 'wxyz',
        'oct_encoding_pole': 'y', 'sh_l1_order': ['dc', 'y', 'z', 'x'], 'color_space_default': 'srgb',
        'uv_origin': 'top-left', 'alignment_bytes': 16, 'text_encoding': 'utf-8', 'id_case': 'kebab-case',
        'hash_algorithm': 'sha256', 'signature_algorithm': 'ed25519',
    }
}


def _type_matches(t, pattern):
    if pattern == '*':
        return True
    if pattern.endswith('*'):
        return t.startswith(pattern[:-1])
    return t == pattern


def check_conventions(man, cmap):
    """Returns the set of node types refused, or None for container refusal."""
    prof = man.get('profile')
    if prof not in SUPPORTED:
        report('unsupported-profile', 'warn', 'MANIFEST.json', 'profile %r: listing and hashing only' % prof)
        return {'*'}
    want = SUPPORTED[prof]
    have = man.get('conventions', {})
    refused = set()
    for k, v in want.items():
        if k not in have:
            report('missing-convention', 'error', 'MANIFEST.json', k)
            continue
        if have[k] != v:
            entry = (cmap or {}).get('conventions', {}).get(k, {})
            scope = entry.get('scope', 'node')
            report('unsupported-convention', 'error', 'MANIFEST.json', '%s=%r (scope %s)' % (k, have[k], scope))
            if scope == 'container':
                return None
            refused.update(entry.get('governs', []))
    for k in have:
        if k not in want:
            report('unknown-convention', 'info', 'MANIFEST.json', k)
    return refused


# --------------------------------------------------------------------------
# MessagePack subset + envelope (ENVELOPE.layout.txt §1-§7)
# --------------------------------------------------------------------------
class EnvelopeError(Exception):
    pass


def mp_decode(b, i=0):
    t = b[i]
    i += 1
    if t <= 0x7f:
        return t, i
    if t >= 0xe0:
        return t - 256, i
    if 0xa0 <= t <= 0xbf:
        n = t & 0x1f
        return b[i:i + n].decode('utf-8'), i + n
    if 0x90 <= t <= 0x9f:
        return _mp_arr(b, i, t & 0x0f)
    if 0x80 <= t <= 0x8f:
        return _mp_map(b, i, t & 0x0f)
    if t == 0xc0:
        return None, i
    if t == 0xc2:
        return False, i
    if t == 0xc3:
        return True, i
    fixed = {0xcc: '>B', 0xcd: '>H', 0xce: '>I', 0xcf: '>Q', 0xd0: '>b', 0xd1: '>h', 0xd2: '>i', 0xd3: '>q',
             0xca: '>f', 0xcb: '>d'}
    if t in fixed:
        f = fixed[t]
        n = struct.calcsize(f)
        return struct.unpack_from(f, b, i)[0], i + n
    if t in (0xd9, 0xda, 0xdb, 0xc4, 0xc5, 0xc6):
        f = {0xd9: '>B', 0xda: '>H', 0xdb: '>I', 0xc4: '>B', 0xc5: '>H', 0xc6: '>I'}[t]
        ln = struct.calcsize(f)
        n = struct.unpack_from(f, b, i)[0]
        i += ln
        raw = b[i:i + n]
        return (raw.decode('utf-8') if t in (0xd9, 0xda, 0xdb) else bytes(raw)), i + n
    if t in (0xdc, 0xdd):
        f = '>H' if t == 0xdc else '>I'
        n = struct.unpack_from(f, b, i)[0]
        return _mp_arr(b, i + struct.calcsize(f), n)
    if t in (0xde, 0xdf):
        f = '>H' if t == 0xde else '>I'
        n = struct.unpack_from(f, b, i)[0]
        return _mp_map(b, i + struct.calcsize(f), n)
    raise EnvelopeError('banned or unknown MessagePack byte 0x%02x' % t)


def _mp_arr(b, i, n):
    out = []
    for _ in range(n):
        v, i = mp_decode(b, i)
        out.append(v)
    return out, i


def _mp_map(b, i, n):
    out = {}
    for _ in range(n):
        k, i = mp_decode(b, i)
        v, i = mp_decode(b, i)
        if k in out:
            raise EnvelopeError('duplicate header key %r' % k)
        out[k] = v
    return out, i


DTYPE_SIZE = {'u8': 1, 'i8': 1, 'u16': 2, 'i16': 2, 'u32': 4, 'i32': 4, 'u64': 8, 'i64': 8, 'f32': 4, 'f64': 8}
MAGIC_KIND = {b'WKFF': 'core.field.flow', b'WKRP': 'core.pose.rest', b'WKAC': 'core.anim.clip',
              b'WKSK': 'core.skeleton', b'WKEM': 'core.embedding', b'WKPC': 'core.geom.points',
              b'WKGS': 'core.geom.gsplat'}


def read_envelope(buf):
    if len(buf) < 12:
        raise EnvelopeError('shorter than 12 bytes')
    magic = bytes(buf[0:4])
    version, header_len = struct.unpack_from('<II', buf, 4)
    if header_len < 1 or 12 + header_len > len(buf):
        raise EnvelopeError('header_len %d does not fit' % header_len)
    header, end = mp_decode(buf, 12)
    if end != 12 + header_len:
        raise EnvelopeError('header map ends at %d, header_len says %d' % (end, 12 + header_len))
    if not isinstance(header, dict):
        raise EnvelopeError('header is not a map')
    for k in ('kind', 'endianness', 'payload_origin', 'payload_size', 'sections'):
        if k not in header:
            raise EnvelopeError('mandatory header key %r missing' % k)
    if MAGIC_KIND.get(magic) != header['kind']:
        raise EnvelopeError('magic %r does not match kind %r' % (magic, header['kind']))
    if header['endianness'] != 'le':
        raise EnvelopeError('endianness %r' % header['endianness'])
    P = 16 * math.ceil((12 + header_len) / 16)
    if header['payload_origin'] != P:
        raise EnvelopeError('payload_origin %d != computed %d' % (header['payload_origin'], P))
    if P + header['payload_size'] != len(buf):
        raise EnvelopeError('payload_origin+payload_size %d != file size %d' % (P + header['payload_size'], len(buf)))
    sections = {}
    cursor = P
    last_end = P
    for s in header['sections']:
        off, sz, st = s['offset'], s['size'], s['stride']
        if off % 16:
            raise EnvelopeError('section %s offset %d not 16-aligned' % (s['name'], off))
        if off < cursor or off - cursor > 15:
            raise EnvelopeError('section %s at %d: gap/order violation after %d' % (s['name'], off, cursor))
        if off + sz > len(buf):
            raise EnvelopeError('section %s does not fit' % s['name'])
        esz = DTYPE_SIZE.get(s['dtype'], st) if s['dtype'] != 'record' else st
        if s['dtype'] not in DTYPE_SIZE and s['dtype'] != 'record':
            raise EnvelopeError('unknown dtype %r' % s['dtype'])
        shape = s['shape']
        if st == esz:
            if sz != st * _prod(shape):
                raise EnvelopeError('section %s size rule (branch 1) fails' % s['name'])
        else:
            if not (st >= esz * shape[-1]) or sz != st * _prod(shape[:-1]):
                raise EnvelopeError('section %s size rule (branch 2) fails' % s['name'])
        if s['name'] in sections:
            raise EnvelopeError('duplicate section name %s' % s['name'])
        sections[s['name']] = s
        cursor = off + sz
        last_end = cursor
    if 16 * math.ceil(last_end / 16) != P + header['payload_size']:
        raise EnvelopeError('trailing data after last section')
    return magic, version, header, sections


def _prod(xs):
    r = 1
    for x in xs:
        r *= x
    return r


def decode_wkrp(buf, header, sections):
    """restposes.layout.txt. Returns (poses, contacts)."""
    known = {'poses', 'contacts'}
    for n in sections:
        if n not in known:
            report('section-skipped-unknown', 'info', 'core.pose.rest', n)
    ps, cs = sections['poses'], sections['contacts']
    if ps['dtype'] != 'record' or ps['stride'] != 32 or cs['dtype'] != 'f32' or cs['stride'] != 12:
        raise EnvelopeError('WKRP section shapes differ from layout')
    poses = []
    for i in range(ps['shape'][0]):
        w, x, y, z, cf, cc, pr, area = struct.unpack_from('<4fIIff', buf, ps['offset'] + 32 * i)
        poses.append(dict(quat_wxyz=(w, x, y, z), contact_first=cf, contact_count=cc, probability=pr, support_area_m2=area))
    contacts = [struct.unpack_from('<3f', buf, cs['offset'] + 12 * c) for c in range(cs['shape'][0])]
    for v in [f for p in poses for f in p['quat_wxyz']] + [f for c in contacts for f in c]:
        if not math.isfinite(v):
            raise EnvelopeError('NaN/inf in payload')
    if header['pose_count'] != len(poses) or header['contact_count'] != len(contacts):
        raise EnvelopeError('pose_count/contact_count disagree with section shapes')
    if sum(p['contact_count'] for p in poses) != header['contact_count']:
        raise EnvelopeError('sum(contact_count) != header contact_count')
    for i in range(1, len(poses)):
        if poses[i]['probability'] > poses[i - 1]['probability']:
            raise EnvelopeError('poses not sorted by probability descending')
    for p in poses:
        if p['contact_count'] < 1 or p['contact_first'] + p['contact_count'] > len(contacts):
            raise EnvelopeError('contact index out of range')
        n = math.sqrt(sum(q * q for q in p['quat_wxyz']))
        if abs(n - 1.0) > 1e-6:
            raise EnvelopeError('quaternion not unit (|q|=%r)' % n)
        if p['quat_wxyz'][0] < 0:
            report('quat-noncanonical-sign', 'warn', 'core.pose.rest', 'w < 0')
    if header.get('trials', 0) > 0:
        tot = sum(p['probability'] for p in poses)
        if abs(tot - 1.0) > 1e-3:
            raise EnvelopeError('probabilities sum to %r' % tot)
    elif any(p['probability'] != 0.0 for p in poses):
        raise EnvelopeError('trials == 0 but probability nonzero')
    return poses, contacts


# --------------------------------------------------------------------------
# GLB / WAV / PNG (MINI-SPECS §8-§10)
# --------------------------------------------------------------------------
def read_glb(b):
    if b[0:4] != b'glTF':
        raise ValueError('not glTF magic')
    ver, total = struct.unpack_from('<II', b, 4)
    if ver != 2 or total != len(b):
        raise ValueError('version %d / length %d vs %d' % (ver, total, len(b)))
    off = 12
    js = binc = None
    while off < len(b):
        ln, ty = struct.unpack_from('<II', b, off)
        chunk = b[off + 8:off + 8 + ln]
        if ty == 0x4E4F534A:
            js = parse_json(bytes(chunk).rstrip(b' '))
        elif ty == 0x004E4942:
            binc = chunk
        off += 8 + ln
    if js is None:
        raise ValueError('no JSON chunk')
    info = dict(json=js, bin=binc)
    prims = []
    for m in js.get('meshes', []):
        for pr in m['primitives']:
            attrs = pr['attributes']
            acc = js['accessors']
            d = dict(mode=pr.get('mode', 4), attributes=sorted(attrs))
            d['vertices'] = acc[attrs['POSITION']]['count']
            if 'indices' in pr:
                d['triangles'] = acc[pr['indices']]['count'] // 3
            d['pos_min'] = acc[attrs['POSITION']].get('min')
            d['pos_max'] = acc[attrs['POSITION']].get('max')
            # compute bounds from the BIN data ourselves rather than trust min/max
            d['pos_min_computed'], d['pos_max_computed'] = _accessor_minmax(js, binc, attrs['POSITION'])
            prims.append(d)
    info['primitives'] = prims
    return info


def _accessor_minmax(js, binc, ai):
    a = js['accessors'][ai]
    bv = js['bufferViews'][a['bufferView']]
    if a['componentType'] != 5126 or a['type'] != 'VEC3':
        return None, None
    stride = bv.get('byteStride', 12)
    base = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for i in range(a['count']):
        v = struct.unpack_from('<3f', binc, base + i * stride)
        for k in range(3):
            lo[k] = min(lo[k], v[k])
            hi[k] = max(hi[k], v[k])
    return lo, hi


def read_wav(b):
    if b[0:4] != b'RIFF' or b[8:12] != b'WAVE':
        raise ValueError('not RIFF/WAVE')
    riff_size = struct.unpack_from('<I', b, 4)[0]
    if riff_size + 8 != len(b):
        report('wav-riff-size', 'warn', 'wav', 'RIFF size %d + 8 != file %d' % (riff_size, len(b)))
    off = 12
    fmt = None
    data_len = None
    chunks = []
    while off + 8 <= len(b):
        cid = b[off:off + 4].decode('ascii', 'replace')
        sz = struct.unpack_from('<I', b, off + 4)[0]
        chunks.append(cid)
        if cid == 'fmt ':
            af, ch, sr, br, ba, bps = struct.unpack_from('<HHIIHH', b, off + 8)
            fmt = dict(audio_format=af, channels=ch, sample_rate=sr, byte_rate=br, block_align=ba, bits=bps)
        elif cid == 'data':
            data_len = sz
        off += 8 + sz + (sz & 1)
    if fmt is None or data_len is None:
        raise ValueError('missing fmt or data chunk')
    fmt['frames'] = data_len // fmt['block_align']
    fmt['seconds'] = fmt['frames'] / fmt['sample_rate']
    fmt['chunks'] = chunks
    return fmt


def read_png(b):
    if b[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('bad PNG signature')
    off = 8
    ihdr = None
    bad = 0
    while off < len(b):
        ln = struct.unpack_from('>I', b, off)[0]
        ty = b[off + 4:off + 8]
        body = b[off + 8:off + 8 + ln]
        crc = struct.unpack_from('>I', b, off + 8 + ln)[0]
        if crc32(bytes(ty) + bytes(body)) != crc:
            bad += 1
        if ty == b'IHDR':
            w, h, bd, ct = struct.unpack_from('>IIBB', body, 0)
            ihdr = dict(width=w, height=h, bit_depth=bd, colour_type=ct)
        off += 12 + ln
        if ty == b'IEND':
            break
    if bad:
        raise ValueError('%d PNG chunk CRC mismatches' % bad)
    return ihdr


# --------------------------------------------------------------------------
# meanings (summarised from SPEC.md §3 and spec/README.md tables)
# --------------------------------------------------------------------------
TYPE_MEANING = {
    'core.geom.game': 'runtime game mesh (GLB); the default primary mesh',
    'core.geom.source': 'archival source mesh (GLB)',
    'core.geom.lod': 'level-of-detail mesh (GLB)',
    'core.material': 'PBR material parameters (JSON); authoritative over GLB materials',
    'core.phys.bounds': 'measured bounding box / sphere for culling and placement (JSON)',
    'core.semantics': 'facet tags, palette, search text (JSON); renders a browser listing',
    'core.provenance': 'who made what, from what, with which models (JSON)',
    'core.audio.effect': 'one sound effect: WAV takes + JSON descriptor; payload role "best"',
    'core.spec': 'the format specification carried inside the package',
    'core.loader': 'bundled reader source code (inert data to this reader)',
    'core.license': 'full licence text',
    'core.readme': 'human readme',
    'core.pose.rest': 'settled rest orientations from a drop simulation (WKRP envelope)',
}


def meaning(t):
    if t in TYPE_MEANING:
        return TYPE_MEANING[t]
    if t.startswith('x.'):
        return 'extension node (%s) - opaque to core readers, listed and hashed only' % t
    return 'unknown type'


# --------------------------------------------------------------------------
# payload resolution (SPEC §2.1)
# --------------------------------------------------------------------------
PAYLOAD_ROLE = {'core.audio.effect': 'best', 'core.audio.ambience': 'best', 'core.imposter': 'atlas',
                'core.recipe': 'record'}


def active_version(node):
    vs = {v['v']: v for v in node.get('versions', [])}
    a = node.get('active')
    if a in vs:
        return vs[a], False
    if vs:
        report('active-invalid', 'warn', node['node_id'], 'active=%r; fell back to newest v%d' % (a, max(vs)))
        return vs[max(vs)], True
    return None, False


def resolve_payload(node, ver):
    files = ver['files']
    paths = [f['path'] for f in files]
    pf = ver.get('payload_file')
    if pf is not None:
        if paths.count(pf) == 1:
            return pf, 'rule 1 (payload_file)'
        report('payload-file-invalid', 'error', node['node_id'], 'payload_file %r not exactly one files[] entry' % pf)
    if len(files) == 1:
        return paths[0], 'rule 2 (single file)'
    pl = [f['path'] for f in files if f.get('role') == 'payload']
    if len(pl) == 1:
        return pl[0], 'rule 3 (role payload)'
    r = PAYLOAD_ROLE.get(node['type'])
    if r:
        c = [f['path'] for f in files if f.get('role') == r]
        if len(c) == 1:
            return c[0], 'rule 4 (type role %s)' % r
    report('payload-file-ambiguous', 'warn', node['node_id'], 'candidates: %s' % ', '.join(paths))
    return None, 'rule 5 (ambiguous)'


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    pkg = argv[1]
    outdir = argv[2] if len(argv) > 2 else 'extracted'
    buf = open(pkg, 'rb').read()
    print('=' * 78)
    print('werk_reader: %s (%d bytes)' % (pkg, len(buf)))
    print('=' * 78)

    # 1. container
    try:
        entries, order, zinfo = open_zip(buf)
    except ContainerRefused as ex:
        report(str(ex).split(':')[0].split(' ')[0], 'error', pkg, str(ex))
        dump_report()
        return 2
    print('\n[1] CONTAINER: zip, %d entries, central directory @%d (%d bytes), EOCD @%d' %
          (len(entries), zinfo['cd_off'], zinfo['cd_size'], zinfo['eocd']))

    # 2. manifest
    me = entries.get('MANIFEST.json')
    if me is None or me['data'] is None:
        report('manifest-missing', 'error', 'MANIFEST.json')
        dump_report()
        return 2
    mbytes = bytes(me['data'])
    try:
        man = parse_json(mbytes)
    except Exception as ex:
        report('manifest-unparseable', 'error', 'MANIFEST.json', str(ex))
        dump_report()
        return 2
    for k, t in (('werk', dict), ('profile', str), ('conventions', dict), ('nodes', list), ('container', dict)):
        if not isinstance(man.get(k), t):
            report('manifest-structure', 'error', 'MANIFEST.json', 'key %r missing or not %s' % (k, t.__name__))
    if man.get('werk', {}).get('major') != 1:
        report('unsupported-major', 'error', 'MANIFEST.json', 'werk.major=%r' % man.get('werk', {}).get('major'))
    if man.get('manifest_schema') not in (None, 'spec/schemas/manifest.schema.json'):
        report('manifest-schema-declared', 'info', 'MANIFEST.json', man['manifest_schema'])
    ent = man.get('entity', {})
    print('\n[2] MANIFEST: werk %s.%s, profile %s' % (man['werk']['major'], man['werk']['minor'], man['profile']))
    print('    entity  : %s  (%s)' % (ent.get('name'), ent.get('uuid')))
    print('    summary : %s' % ent.get('summary'))
    print('    sha256  : %s' % hashlib.sha256(mbytes).hexdigest())
    print('    (structural check only; the manifest was NOT validated against manifest.schema.json)')
    c = man.get('container', {})
    if c.get('zip_compression') != 'store':
        report('container-compression', 'info', 'MANIFEST.json', 'declares %r' % c.get('zip_compression'))

    # conventions map (declared path)
    cmap = None
    cmp_path = man.get('conventions_map')
    if cmp_path and cmp_path in entries and entries[cmp_path]['data'] is not None:
        cmap = parse_json(bytes(entries[cmp_path]['data']))

    # 3. conventions
    refused = check_conventions(man, cmap)
    if refused is None:
        dump_report()
        return 2
    print('\n[3] CONVENTIONS: %d declared; all %s by this reader%s' %
          (len(man['conventions']), 'supported' if not refused else 'NOT supported',
           '' if not refused else ' -> refusing ' + ', '.join(sorted(refused))))
    rot = man.get('parts', [{}])[0].get('transform', {}).get('rotation')
    if rot is not None:
        print('    parts[0].transform.rotation (wxyz) = %s' % rot)

    # 4. signature
    state, lines = verify_signature(entries, mbytes)
    print('\n[4] SIGNATURE: %s' % state)
    for ln in lines:
        print('    ' + ln)

    # 5. nodes, files, hashes
    nodes = man['nodes']
    by_id = {}
    for n in nodes:
        if n['node_id'] in by_id:
            report('duplicate-node-id', 'error', n['node_id'])
        by_id[n['node_id']] = n
    owner = {}
    file_meta = {}
    dead = {}
    hash_results = []
    for n in nodes:
        nid = n['node_id']
        vs = n.get('versions', [])
        if not vs:
            report('node-no-versions', 'error', nid)
            dead[nid] = 'no versions'
            continue
        if sum(1 for v in vs if v['v'] == n.get('active')) != 1:
            report('active-invalid', 'warn', nid, 'active=%r' % n.get('active'))
        for v in vs:
            if v['epistemic'] in ('measured', 'inferred') and ('input_hash' not in v or 'input_files' not in v):
                report('missing-input-hash', 'warn', nid, 'v%d is %s without input_hash/input_files' % (v['v'], v['epistemic']))
            if not v.get('note'):
                report('missing-work-note', 'warn', nid, 'v%d' % v['v'])
            for f in v['files']:
                p = f['path']
                if p in owner and owner[p] != nid:
                    report('path-claimed-twice', 'error', p, 'by %s and %s' % (owner[p], nid))
                owner[p] = nid
                file_meta[p] = f
                e = entries.get(p)
                if e is None:
                    report('file-missing', 'error', nid, p)
                    dead[nid] = 'file missing: ' + p
                    hash_results.append((p, f['sha256'], None, 'MISSING'))
                    continue
                if e['data'] is None:
                    dead[nid] = 'unreadable: ' + p
                    hash_results.append((p, f['sha256'], None, 'UNREADABLE'))
                    continue
                data = bytes(e['data'])
                h = hashlib.sha256(data).hexdigest()
                ok_size = len(data) == f['size']
                ok_hash = h == f['sha256']
                if not ok_size:
                    report('size-mismatch', 'error', nid, '%s: %d bytes, declared %d' % (p, len(data), f['size']))
                if not ok_hash:
                    report('hash-mismatch', 'error', nid, p)
                if not (ok_size and ok_hash):
                    dead[nid] = 'hash/size mismatch: ' + p
                hash_results.append((p, f['sha256'], h, 'OK' if ok_size and ok_hash else 'MISMATCH'))
    # nothing floats (SPEC §2)
    for name in order:
        if name in ('MANIFEST.json', 'SIGNATURE.json'):
            continue
        if name not in owner:
            report('file-floats', 'warn', name, 'container entry not listed by any node; not read')
    # license.sha256
    lic = man.get('license', {})
    if lic.get('file') in entries:
        lh = hashlib.sha256(bytes(entries[lic['file']]['data'])).hexdigest()
        hash_results.append(('license.sha256 -> ' + lic['file'], lic.get('sha256'), lh, 'OK' if lh == lic.get('sha256') else 'MISMATCH'))
        if lh != lic.get('sha256'):
            report('license-hash-mismatch', 'error', lic['file'])
    # spec_sha256 (SPEC §2, S-29)
    spec_paths = sorted((p for p in owner if p.startswith('spec/')), key=lambda s: s.encode('utf-8'))
    acc = b''
    for p in spec_paths:
        acc += p.encode('utf-8') + b'\n' + bytes.fromhex(hashlib.sha256(bytes(entries[p]['data'])).hexdigest()) + b'\n'
    sh = hashlib.sha256(acc).hexdigest()
    hash_results.append(('spec_sha256 (%d spec files)' % len(spec_paths), man.get('spec_sha256'), sh,
                         'OK' if sh == man.get('spec_sha256') else 'MISMATCH'))
    if sh != man.get('spec_sha256'):
        report('spec-sha256-mismatch', 'error', 'MANIFEST.json')
    # input_hash (MINI-SPECS §11 'What gets hashed')
    for n in nodes:
        for v in n['versions']:
            if 'input_hash' not in v:
                continue
            ins = v.get('input_files', [])
            missing = [p for p in ins if p not in entries or entries[p]['data'] is None]
            label = 'input_hash %s v%d' % (n['node_id'], v['v'])
            if missing:
                report('input-hash-unverifiable', 'info', n['node_id'],
                       'inputs not in this package: %s' % ', '.join(missing))
                hash_results.append((label, v['input_hash'], None, 'UNVERIFIABLE (inputs absent)'))
                continue
            h = hashlib.sha256()
            for p in ins:
                h.update(hashlib.sha256(bytes(entries[p]['data'])).digest())
            h.update(canonical_json(v.get('input_params') or {}).encode('utf-8'))
            got = h.hexdigest()
            st = 'OK' if got == v['input_hash'] else 'MISMATCH'
            if st != 'OK':
                report('input-hash-mismatch', 'warn', n['node_id'], 'derived data may be stale')
            hash_results.append((label, v['input_hash'], got, st))
    print('\n[5] HASHES')
    for p, decl, got, st in hash_results:
        print('    %-12s %s' % (st, p))
        print('                 declared %s' % decl)
        if got and got != decl:
            print('                 computed %s' % got)

    # edges (SPEC §5)
    for n in nodes:
        for e in n.get('edges', []):
            if e['to'] not in by_id:
                sev = 'warn'
                report('edge-target-missing', sev, n['node_id'],
                       '%s edge (role %s) -> %r, which is not in this package' % (e['kind'], e.get('role'), e['to']))
    changed = True
    while changed:
        changed = False
        for n in nodes:
            if n['node_id'] in dead:
                continue
            for e in n.get('edges', []):
                if e['kind'] == 'requires' and e['to'] in dead:
                    dead[n['node_id']] = 'requires dead node %s' % e['to']
                    report('node-dead-requires', 'error', n['node_id'], dead[n['node_id']])
                    changed = True

    # 6. dispatch by type
    print('\n[6] PAYLOADS')
    details = {}
    for n in nodes:
        nid, t = n['node_id'], n['type']
        if nid in dead:
            continue
        if any(_type_matches(t, r) for r in refused):
            report('unsupported-convention', 'error', nid, 'refused by convention')
            continue
        v, _ = active_version(n)
        try:
            if t in ('core.geom.game', 'core.geom.source', 'core.geom.lod'):
                g = read_glb(entries[v['files'][0]['path']]['data'])
                details[nid] = g
                for pr in g['primitives']:
                    print('    %-32s GLB: %d vertices, %s triangles, attrs %s' % (nid, pr['vertices'], pr.get('triangles'), ','.join(pr['attributes'])))
                    print('    %-32s      POSITION min %s max %s (computed from BIN)' % ('', _r(pr['pos_min_computed']), _r(pr['pos_max_computed'])))
                    for req in ('NORMAL', 'COLOR_0'):
                        if req not in pr['attributes']:
                            report('glb-attribute-missing', 'warn', nid, req)
            elif t in ('core.audio.effect', 'core.audio.ambience'):
                for f in v['files']:
                    if f['path'].endswith('.wav'):
                        w = read_wav(entries[f['path']]['data'])
                        details[f['path']] = w
                        print('    %-32s WAV %-6s %d Hz, %d ch, %d-bit fmt=%d, %.3f s  (%s)' %
                              (nid, f.get('role'), w['sample_rate'], w['channels'], w['bits'], w['audio_format'], w['seconds'], f['path']))
                    elif f['path'].endswith('.json'):
                        desc = parse_json(bytes(entries[f['path']]['data']))
                        details[nid] = desc
                        af = desc.get('audio_format', {})
                        print('    %-32s descriptor: "%s", %s, CLAP %.4f, declared %s Hz/%s ch/%s-bit %s' %
                              (nid, desc.get('interaction'), desc.get('category'), desc.get('clap_score', 0),
                               af.get('sample_rate_hz'), af.get('channels'), af.get('bit_depth'), af.get('sample_format')))
                af = details.get(nid, {}).get('audio_format', {})
                for f in v['files']:
                    w = details.get(f['path'])
                    if w and af and (w['sample_rate'] != af.get('sample_rate_hz') or w['channels'] != af.get('channels') or w['bits'] != af.get('bit_depth')):
                        report('audio-format-disagrees', 'warn', nid, '%s differs from descriptor audio_format' % f['path'])
            elif t == 'core.pose.rest':
                b = entries[v['files'][0]['path']]['data']
                magic, ver, hdr, secs = read_envelope(b)
                poses, contacts = decode_wkrp(b, hdr, secs)
                details[nid] = (hdr, poses, contacts)
                print('    %-32s WKRP v%d: %d poses, %d contacts, trials %s, producer %s' %
                      (nid, ver, len(poses), len(contacts), hdr.get('trials'), hdr.get('producer')))
                for i, p in enumerate(poses):
                    print('    %-32s   pose %d q(wxyz)=%s p=%.4f contacts=%d area=%.4f m2' %
                          ('', i, _r(p['quat_wxyz']), p['probability'], p['contact_count'], p['support_area_m2']))
                if 'input_hash' in hdr and hdr['input_hash'] != v.get('input_hash'):
                    report('envelope-input-hash-disagrees', 'warn', nid, 'header vs manifest')
                if hdr.get('epistemic') and hdr['epistemic'] != v.get('epistemic'):
                    report('envelope-epistemic-disagrees', 'info', nid, 'header %r vs manifest %r' % (hdr['epistemic'], v.get('epistemic')))
                hp = hdr.get('producer', {})
                if hp and hp.get('tool') != v.get('producer', {}).get('tool'):
                    report('envelope-producer-disagrees', 'warn', nid,
                           'envelope header producer %r, manifest version producer %r' % (hp, v.get('producer')))
            elif t in ('core.material', 'core.phys.bounds', 'core.semantics', 'core.provenance'):
                d = parse_json(bytes(entries[v['files'][0]['path']]['data']))
                details[nid] = d
                print('    %-32s JSON ok (%d top-level keys; schema validation NOT performed)' % (nid, len(d)))
            elif t.startswith('x.'):
                for f in v['files']:
                    if f['path'].endswith('.png'):
                        ih = read_png(entries[f['path']]['data'])
                        print('    %-32s PNG %dx%d bit_depth %d colour_type %d, chunk CRCs ok (%s)' %
                              (nid, ih['width'], ih['height'], ih['bit_depth'], ih['colour_type'], f['path']))
                        for im in n.get('meta', {}).get('images', []):
                            if im.get('file') == f['path'] and (im['width'], im['height']) != (ih['width'], ih['height']):
                                report('png-meta-disagrees', 'warn', nid, f['path'])
                meta_files = [im['file'] for im in n.get('meta', {}).get('images', [])]
                listed = [f['path'] for f in v['files']]
                absent = [m for m in meta_files if m not in listed]
                if absent:
                    report('meta-names-absent-files', 'info', nid,
                           'meta.images/count describe %d images, files[] carries %d' % (len(meta_files), len(listed)))
                report('node-skipped-unknown-type', 'info', nid, 'extension type %s: hashed and listed, not interpreted' % t)
            elif t in ('core.spec', 'core.loader', 'core.license', 'core.readme'):
                pass  # text; hashed above. Loaders are inert data: never opened, never run.
            else:
                report('node-skipped-unknown-type', 'info', nid, t)
        except (EnvelopeError, ValueError, KeyError, struct.error) as ex:
            dead[nid] = 'payload invalid: %s' % ex
            report('envelope-invalid' if t == 'core.pose.rest' else 'payload-invalid', 'error', nid, str(ex))

    # cross-checks between nodes (informative)
    bnd = details.get('bounds')
    geo = details.get('geom-game')
    if bnd and geo:
        lo, hi = geo['primitives'][0]['pos_min_computed'], geo['primitives'][0]['pos_max_computed']
        e = bnd['entity']
        if any(abs(a - b) > 1e-4 for a, b in zip(lo + hi, e['aabb_min'] + e['aabb_max'])):
            report('bounds-disagree-with-mesh', 'warn', 'bounds', 'aabb %s..%s vs mesh %s..%s' % (e['aabb_min'], e['aabb_max'], _r(lo), _r(hi)))
        else:
            print('    cross-check: bounds.json AABB matches the mesh vertices')
    rp = details.get('rest-poses')
    if rp and bnd:
        hdr, poses, contacts = rp
        e = bnd['entity']
        ymin = e['aabb_min'][1]
        q = poses[0]['quat_wxyz']
        if q == (1.0, 0.0, 0.0, 0.0):
            ys = [contacts[i][1] for i in range(poses[0]['contact_first'], poses[0]['contact_first'] + poses[0]['contact_count'])]
            if any(abs(y - ymin) > 1e-3 for y in ys):
                report('rest-pose-implausible', 'warn', 'rest-poses',
                       'pose 0 is identity but its contacts sit at y=%s, not on the mesh bottom y=%s; '
                       'payload is byte-identical to spec/examples/restposes.example.wkrp' % (_r(ys), ymin))
    for p, f in file_meta.items():
        pass
    rp_sha = file_meta.get('poses/rest.wkrp', {}).get('sha256')
    if rp_sha and rp_sha == file_meta.get('spec/examples/restposes.example.wkrp', {}).get('sha256'):
        report('payload-is-spec-example', 'warn', 'rest-poses', 'poses/rest.wkrp has the same sha256 as the spec example binary')

    # 7. listing
    print('\n[7] NODE GRAPH (%d nodes)' % len(nodes))
    for n in nodes:
        v, _ = active_version(n)
        status = 'DEAD: ' + dead[n['node_id']] if n['node_id'] in dead else 'live'
        print('  * %s  [%s]  active v%s  %s' % (n['node_id'], n['type'], n.get('active'), status))
        print('      meaning : %s' % meaning(n['type']))
        if v:
            print('      note    : %s' % v.get('note'))
            print('      made by : %s; epistemic %s%s' % (
                ' '.join('%s=%s' % kv for kv in v.get('producer', {}).items()), v.get('epistemic'),
                (', confidence %s' % v['confidence']) if 'confidence' in v else ''))
            for f in v['files']:
                print('      file    : %-48s %7d B%s' % (f['path'], f['size'], (' role=' + f['role']) if f.get('role') else ''))
        for e in n.get('edges', []):
            print('      edge    : %s --%s/%s--> %s%s' % (n['node_id'], e['kind'], e.get('role'), e['to'],
                                                      '' if e['to'] in by_id else '   (target not in package)'))
        if n['type'] == 'core.loader':
            print('      (bundled reader: treated as inert data; not opened, not run)')

    # 8. extraction
    print('\n[8] EXTRACTION -> %s' % outdir)
    os.makedirs(outdir, exist_ok=True)
    prim = man.get('primary') or {}
    extracted = []
    for slot, fallback_type in (('mesh', 'core.geom.game'), ('sound', 'core.audio.effect')):
        nid = prim.get(slot)
        if nid is None:
            cand = [n for n in nodes if n['type'] == fallback_type]
            if not cand:
                report('primary-unresolved', 'warn', slot)
                continue
            nid = cand[0]['node_id']
            report('primary-fallback', 'info', slot, 'primary.%s absent; fell back to %s' % (slot, nid))
        node = by_id.get(nid)
        if node is None:
            report('primary-unresolved', 'error', slot, 'primary.%s names %r which is not a node' % (slot, nid))
            continue
        if nid in dead:
            report('primary-dead', 'error', slot, '%s is dead: %s' % (nid, dead[nid]))
            continue
        v, _ = active_version(node)
        path, rule = resolve_payload(node, v)
        if path is None:
            continue
        decl = next(f for f in v['files'] if f['path'] == path)
        data = bytes(entries[path]['data'])
        dst = os.path.join(outdir, path.replace('/', '__'))
        with open(dst, 'wb') as fh:
            fh.write(data)
        got = hashlib.sha256(open(dst, 'rb').read()).hexdigest()
        ok = got == decl['sha256'] and os.path.getsize(dst) == decl['size']
        extracted.append((slot, nid, path, rule, dst, decl['sha256'], got, ok))
        if not ok:
            report('extract-hash-mismatch', 'error', path)
        print('    primary.%s -> node %s -> v%d -> %s [%s]' % (slot, nid, v['v'], path, rule))
        print('       wrote    %s (%d bytes)' % (dst, os.path.getsize(dst)))
        print('       declared %s' % decl['sha256'])
        print('       computed %s  %s' % (got, 'MATCH' if ok else 'MISMATCH'))

    rc = dump_report()
    return rc


def _r(v):
    if v is None:
        return None
    return '[' + ', '.join('%.4g' % x for x in v) + ']'


def dump_report():
    print('\n[R] REPORT ENTRIES')
    order = {'error': 0, 'warn': 1, 'info': 2}
    for sev, code, subj, msg in sorted(REPORT, key=lambda r: order[r[0]]):
        print('    %-5s %-30s %-34s %s' % (sev, code, subj, msg))
    if any(r[0] == 'error' for r in REPORT):
        if any(r[1] in ('zip64-unsupported', 'no-eocd', 'not-a-zip', 'manifest-missing', 'manifest-unparseable') for r in REPORT):
            print('\nexit 2'); return 2
        print('\nexit 1'); return 1
    print('\nexit 0')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
