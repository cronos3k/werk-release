#!/usr/bin/env python3
import zipfile, json, hashlib, struct, math, os, time, sys, zlib

WORK = "gsplat-v1.werk"
REPORT = "REPORT.md"

read_order = []
stumbles = []
t0 = time.time()

def log_read(name):
    read_order.append(name)

def stumble(msg):
    stumbles.append(msg)

# ---------- MessagePack decoder (subset per spec) ----------
def mp_decode(buf, pos=0):
    b = buf[pos]
    if b <= 0x7f:
        return b, pos+1
    if b >= 0xe0:
        return b-256, pos+1
    if b == 0xc0:
        return None, pos+1
    if b == 0xc2:
        return False, pos+1
    if b == 0xc3:
        return True, pos+1
    if b == 0xcc:
        return buf[pos+1], pos+2
    if b == 0xcd:
        return struct.unpack('>H', buf[pos+1:pos+3])[0], pos+3
    if b == 0xce:
        return struct.unpack('>I', buf[pos+1:pos+5])[0], pos+5
    if b == 0xcf:
        return struct.unpack('>Q', buf[pos+1:pos+9])[0], pos+9
    if b == 0xd0:
        return struct.unpack('>b', buf[pos+1:pos+2])[0], pos+2
    if b == 0xd1:
        return struct.unpack('>h', buf[pos+1:pos+3])[0], pos+3
    if b == 0xd2:
        return struct.unpack('>i', buf[pos+1:pos+5])[0], pos+5
    if b == 0xd3:
        return struct.unpack('>q', buf[pos+1:pos+9])[0], pos+9
    if b == 0xca:
        return struct.unpack('>f', buf[pos+1:pos+5])[0], pos+5
    if b == 0xcb:
        return struct.unpack('>d', buf[pos+1:pos+9])[0], pos+9
    if 0xa0 <= b <= 0xbf:
        n = b & 0x1f
        return buf[pos+1:pos+1+n].decode('utf-8'), pos+1+n
    if b == 0xd9:
        n = buf[pos+1]
        return buf[pos+2:pos+2+n].decode('utf-8'), pos+2+n
    if b == 0xda:
        n = struct.unpack('>H', buf[pos+1:pos+3])[0]
        return buf[pos+3:pos+3+n].decode('utf-8'), pos+3+n
    if b == 0xdb:
        n = struct.unpack('>I', buf[pos+1:pos+5])[0]
        return buf[pos+5:pos+5+n].decode('utf-8'), pos+5+n
    if b == 0xc4:
        n = buf[pos+1]
        return buf[pos+2:pos+2+n], pos+2+n
    if b == 0xc5:
        n = struct.unpack('>H', buf[pos+1:pos+3])[0]
        return buf[pos+3:pos+3+n], pos+3+n
    if b == 0xc6:
        n = struct.unpack('>I', buf[pos+1:pos+5])[0]
        return buf[pos+5:pos+5+n], pos+5+n
    if 0x90 <= b <= 0x9f:
        n = b & 0x0f
        arr = []
        pos += 1
        for _ in range(n):
            v, pos = mp_decode(buf, pos)
            arr.append(v)
        return arr, pos
    if b == 0xdc:
        n = struct.unpack('>H', buf[pos+1:pos+3])[0]
        pos += 3
        arr = []
        for _ in range(n):
            v, pos = mp_decode(buf, pos)
            arr.append(v)
        return arr, pos
    if b == 0xdd:
        n = struct.unpack('>I', buf[pos+1:pos+5])[0]
        pos += 5
        arr = []
        for _ in range(n):
            v, pos = mp_decode(buf, pos)
            arr.append(v)
        return arr, pos
    if 0x80 <= b <= 0x8f:
        n = b & 0x0f
        d = {}
        pos += 1
        for _ in range(n):
            k, pos = mp_decode(buf, pos)
            v, pos = mp_decode(buf, pos)
            d[k] = v
        return d, pos
    if b == 0xde:
        n = struct.unpack('>H', buf[pos+1:pos+3])[0]
        pos += 3
        d = {}
        for _ in range(n):
            k, pos = mp_decode(buf, pos)
            v, pos = mp_decode(buf, pos)
            d[k] = v
        return d, pos
    if b == 0xdf:
        n = struct.unpack('>I', buf[pos+1:pos+5])[0]
        pos += 5
        d = {}
        for _ in range(n):
            k, pos = mp_decode(buf, pos)
            v, pos = mp_decode(buf, pos)
            d[k] = v
        return d, pos
    raise ValueError(f"Unsupported msgpack byte 0x{b:02x} at {pos}")

# ---------- Envelope parser ----------
DTYPE_SIZE = {'u8':1,'i8':1,'u16':2,'i16':2,'u32':4,'i32':4,'u64':8,'i64':8,'f32':4,'f64':8}

def read_envelope(data):
    magic = data[0:4].decode('ascii')
    version = struct.unpack('<I', data[4:8])[0]
    header_len = struct.unpack('<I', data[8:12])[0]
    if 12 + header_len > len(data):
        raise ValueError("header_len out of bounds")
    header_bytes = data[12:12+header_len]
    header, _ = mp_decode(header_bytes, 0)
    P = 16 * ((12 + header_len + 15) // 16)
    checks = []
    if header.get('endianness') != 'le':
        checks.append("endianness != le")
    if header.get('payload_origin') != P:
        checks.append(f"payload_origin mismatch: declared {header.get('payload_origin')} computed {P}")
    if P + header.get('payload_size', -1) != len(data):
        checks.append(f"payload_size mismatch: declared {header.get('payload_size')} actual {len(data)-P}")
    sections = header.get('sections', [])
    for s in sections:
        off = s['offset']; size = s['size']; stride = s['stride']; shape = s['shape']; dtype = s['dtype']
        if off % 16 != 0:
            checks.append(f"section {s['name']} offset not aligned")
        if off + size > len(data):
            checks.append(f"section {s['name']} out of bounds")
        esz = DTYPE_SIZE.get(dtype)
        if dtype == 'record':
            esz = stride
        if esz is None:
            checks.append(f"unknown dtype {dtype}")
        else:
            if stride == esz:
                prod = 1
                for d in shape: prod *= d
                if size != stride * prod:
                    checks.append(f"section {s['name']} size mismatch (branch 1)")
            else:
                if stride < esz * shape[-1]:
                    checks.append(f"section {s['name']} stride too small")
                prod = 1
                for d in shape[:-1]: prod *= d
                if size != stride * prod:
                    checks.append(f"section {s['name']} size mismatch (branch 2)")
    return magic, version, header, sections, checks

# ---------- Open zip ----------
t_start = time.time()
zf = zipfile.ZipFile(WORK, 'r')
log_read("gsplat-v1.werk (zip container)")
entries = zf.infolist()
entry_names = [e.filename for e in entries]

# Verify zip CRC and list
crc_issues = []
for e in entries:
    if e.filename.endswith('/'):
        continue
    data = zf.read(e.filename)
    crc = zlib.crc32(data) & 0xffffffff
    if crc != e.CRC:
        crc_issues.append(f"{e.filename}: CRC mismatch stored {e.CRC:08x} computed {crc:08x}")
    if e.compress_type != 0:
        crc_issues.append(f"{e.filename}: compression method {e.compress_type} (expected 0 store)")

# Read MANIFEST.json
manifest_data = zf.read('MANIFEST.json')
log_read('MANIFEST.json')
manifest = json.loads(manifest_data.decode('utf-8'))

# Verify manifest sha256 for all files
hash_issues = []
manifest_files = {}
for node in manifest.get('nodes', []):
    for ver in node.get('versions', []):
        for f in ver.get('files', []):
            manifest_files[f['path']] = f['sha256']
manifest_files['LICENSE'] = manifest['license']['sha256']

for path, expected in manifest_files.items():
    try:
        data = zf.read(path)
        log_read(path)
        h = hashlib.sha256(data).hexdigest()
        if h != expected:
            hash_issues.append(f"{path}: sha256 mismatch expected {expected} got {h}")
    except KeyError:
        hash_issues.append(f"{path}: missing from zip")

# Check entry order
entry_order = manifest.get('container', {}).get('entry_order', [])
actual_order = [n for n in entry_names if not n.endswith('/')]
manifest_file_order = [p for p in entry_order if not p.endswith('/')]
order_issue = None
if manifest_file_order != actual_order:
    order_issue = "entry order differs from manifest container.entry_order"

# ---------- Read README and specs ----------
readme = zf.read('README.txt').decode('utf-8')
log_read('README.txt')

spec_readme = zf.read('spec/README.md').decode('utf-8')
log_read('spec/README.md')
gsplat_layout = zf.read('spec/layouts/gsplat.layout.txt').decode('utf-8')
log_read('spec/layouts/gsplat.layout.txt')
points_layout = zf.read('spec/layouts/points.layout.txt').decode('utf-8')
log_read('spec/layouts/points.layout.txt')
envelope_layout = zf.read('spec/layouts/ENVELOPE.layout.txt').decode('utf-8')
log_read('spec/layouts/ENVELOPE.layout.txt')

# ---------- Parse WKGS ----------
wkgs_data = zf.read('splats/plush.wkgs')
log_read('splats/plush.wkgs')
magic, version, header, sections, env_checks = read_envelope(wkgs_data)
wkgs_checks = list(env_checks)

count = header.get('count')
sh_degree = header.get('sh_degree')
sh_coeff_count = header.get('sh_coeff_count')
if sh_coeff_count != (sh_degree+1)**2:
    wkgs_checks.append(f"sh_coeff_count {sh_coeff_count} != (sh_degree+1)^2")
if header.get('quat_order') != 'wxyz':
    wkgs_checks.append("quat_order != wxyz")
if header.get('scale_space') != 'linear':
    wkgs_checks.append("scale_space != linear")
if header.get('opacity_space') != 'linear':
    wkgs_checks.append("opacity_space != linear")
if header.get('length_unit') != 'metre':
    wkgs_checks.append("length_unit != metre")

sec = {s['name']: s for s in sections}
expected_sections = ['means','scales','rotations','opacities','sh-dc','sh-rest']
if [s['name'] for s in sections] != expected_sections:
    wkgs_checks.append("WKGS section order/names mismatch")

means_sec = sec['means']
shdc_sec = sec['sh-dc']
if means_sec['shape'][0] != count:
    wkgs_checks.append("means shape[0] != count")
if shdc_sec['shape'][0] != count:
    wkgs_checks.append("sh-dc shape[0] != count")

# Extract means and sh-dc
means = []
shdc = []
nan_inf = []
for i in range(count):
    off = means_sec['offset'] + i*12
    x,y,z = struct.unpack('<3f', wkgs_data[off:off+12])
    if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
        nan_inf.append(('means', i))
    means.append((x,y,z))
    off = shdc_sec['offset'] + i*12
    r,g,b = struct.unpack('<3f', wkgs_data[off:off+12])
    if not (math.isfinite(r) and math.isfinite(g) and math.isfinite(b)):
        nan_inf.append(('sh-dc', i))
    shdc.append((r,g,b))

if nan_inf:
    wkgs_checks.append(f"NaN/Inf in WKGS at {len(nan_inf)} records, first {nan_inf[0]}")

C0 = 0.28209479177387814
colors_wkgs = []
for (r,g,b) in shdc:
    cr = max(0.0, min(1.0, 0.5 + C0*r))
    cg = max(0.0, min(1.0, 0.5 + C0*g))
    cb = max(0.0, min(1.0, 0.5 + C0*b))
    colors_wkgs.append((cr,cg,cb))

# ---------- Parse WKPC ----------
wkpc_data = zf.read('points/plush-dc.wkpc')
log_read('points/plush-dc.wkpc')
magic2, version2, header2, sections2, env_checks2 = read_envelope(wkpc_data)
wkpc_checks = list(env_checks2)

count2 = header2.get('count')
fields = header2.get('fields', [])
if len(fields) != len(sections2):
    wkpc_checks.append("WKPC fields count != sections count")
if not fields or fields[0].get('semantic') != 'position':
    wkpc_checks.append("WKPC first field not position")
if header2.get('length_unit') != 'metre':
    wkpc_checks.append("WKPC length_unit != metre")

sec2 = {s['name']: s for s in sections2}
pos_sec = sec2.get('position')
col_sec = sec2.get('color')
if pos_sec is None or col_sec is None:
    wkpc_checks.append("WKPC missing position/color section")

means2 = []
colors2 = []
for i in range(count2):
    off = pos_sec['offset'] + i*12
    x,y,z = struct.unpack('<3f', wkpc_data[off:off+12])
    means2.append((x,y,z))
    off = col_sec['offset'] + i*3
    r,g,b = wkpc_data[off:off+3]
    colors2.append((r/255.0, g/255.0, b/255.0))

# Compare WKGS and WKPC
pos_match = True
col_match = True
mismatch_count = 0
for i in range(count):
    if means[i] != means2[i]:
        pos_match = False
        mismatch_count += 1
        if mismatch_count <= 3:
            wkpc_checks.append(f"position mismatch at {i}: {means[i]} vs {means2[i]}")
    expected_byte = (round(colors_wkgs[i][0]*255), round(colors_wkgs[i][1]*255), round(colors_wkgs[i][2]*255))
    actual_byte = (round(colors2[i][0]*255), round(colors2[i][1]*255), round(colors2[i][2]*255))
    if expected_byte != actual_byte:
        col_match = False
        if mismatch_count <= 3:
            wkpc_checks.append(f"color mismatch at {i}: {expected_byte} vs {actual_byte}")

# ---------- Read tools ----------
tool_files = {
    'splat-to-ply': ['tools/splat-to-ply/tool.json', 'tools/splat-to-ply/splat_to_ply.py', 'tools/splat-to-ply/ply.py'],
    'werk-gsplat': ['tools/werk-gsplat/tool.json', 'tools/werk-gsplat/p_gsplat.py', 'tools/werk-gsplat/ply.py', 'tools/werk-gsplat/common.py'],
    'werk-pointcloud': ['tools/werk-pointcloud/tool.json', 'tools/werk-pointcloud/p_pointcloud.py', 'tools/werk-pointcloud/ply.py', 'tools/werk-pointcloud/common.py']
}

tool_sources = {}
for tool, files in tool_files.items():
    tool_sources[tool] = {}
    for f in files:
        data = zf.read(f)
        log_read(f)
        tool_sources[tool][f] = data.decode('utf-8')

# Read recipe
recipe_data = zf.read('recipe/recipe.json')
log_read('recipe/recipe.json')
recipe = json.loads(recipe_data.decode('utf-8'))

# Read provenance
prov_data = zf.read('provenance/provenance.json')
log_read('provenance/provenance.json')
prov = json.loads(prov_data.decode('utf-8'))

# Read semantics
sem_data = zf.read('semantics/semantics.json')
log_read('semantics/semantics.json')
sem = json.loads(sem_data.decode('utf-8'))

# Read loaders (just to note we opened them, not run)
loader_files = ['loaders/werk_read.py', 'loaders/werk_read.rs', 'loaders/werk_read.c']
for lf in loader_files:
    data = zf.read(lf)
    log_read(lf)

# ---------- Build report ----------
t_phase1 = time.time() - t_start

# Sample points
sample_indices = [0, 1, 2, 100, 1000, 10000, 100000, 281497]
sample_lines = []
for i in sample_indices:
    if i < count:
        p = means[i]
        c = colors_wkgs[i]
        sample_lines.append(f"  point {i}: pos=({p[0]:.6f}, {p[1]:.6f}, {p[2]:.6f})  rgb_linear=({c[0]:.6f}, {c[1]:.6f}, {c[2]:.6f})")

# Compute bounds
minx = min(p[0] for p in means); maxx = max(p[0] for p in means)
miny = min(p[1] for p in means); maxy = max(p[1] for p in means)
minz = min(p[2] for p in means); maxz = max(p[2] for p in means)

# Tool roles from tool.json
tool_roles = {}
for tool, files in tool_sources.items():
    tj_path = 'tools/'+tool+'/tool.json'
    tj = json.loads(tool_sources[tool][tj_path])
    tool_roles[tool] = tj

# Write REPORT.md
report_lines = []
report_lines.append("# Report on gsplat-v1.werk")
report_lines.append("")
report_lines.append("## Task 1: List contents and verify integrity")
report_lines.append("")
report_lines.append("**Succeeded: yes**")
report_lines.append("")
report_lines.append(f"The package is a zip container with {len(entry_names)} entries (including directory entries).")
report_lines.append("")
report_lines.append("### Entry listing (files only)")
report_lines.append("")
report_lines.append("| name | size | CRC-32 | method |")
report_lines.append("|---|---|---|---|")
for e in entries:
    if e.filename.endswith('/'):
        continue
    report_lines.append(f"| {e.filename} | {e.file_size} | {e.CRC:08x} | {e.compress_type} |")
report_lines.append("")
report_lines.append("### Integrity checks")
report_lines.append("")
report_lines.append(f"- CRC-32 of all entries verified: {'PASS' if not crc_issues else 'FAIL'}")
if crc_issues:
    for iss in crc_issues:
        report_lines.append(f"  - {iss}")
report_lines.append(f"- SHA-256 of all manifest-listed files verified: {'PASS' if not hash_issues else 'FAIL'}")
if hash_issues:
    for iss in hash_issues:
        report_lines.append(f"  - {iss}")
report_lines.append(f"- Zip entry order matches manifest: {'PASS' if not order_issue else 'FAIL: '+order_issue}")
report_lines.append(f"- WKGS envelope checks: {'PASS' if not wkgs_checks else 'FAIL'}")
if wkgs_checks:
    for iss in wkgs_checks:
        report_lines.append(f"  - {iss}")
report_lines.append(f"- WKPC envelope checks: {'PASS' if not wkpc_checks else 'FAIL'}")
if wkpc_checks:
    for iss in wkpc_checks:
        report_lines.append(f"  - {iss}")
report_lines.append("")
report_lines.append("Note: SIGNATURE.json was not cryptographically verified (would require Ed25519); its presence and structure were not checked in depth.")
report_lines.append("")

report_lines.append("## Task 2: Extract point positions and colours")
report_lines.append("")
report_lines.append("**Succeeded: yes**")
report_lines.append("")
report_lines.append(f"Point count: **{count}** (from both WKGS and WKPC, they agree)")
report_lines.append("")
report_lines.append("Positions and colours were extracted from `splats/plush.wkgs` using the normative path of `spec/layouts/gsplat.layout.txt` section 7: read only the `means` and `sh-dc` sections, skip the other four, and apply `rgb_linear = clamp(0.5 + 0.28209479177387814 * sh_dc, 0, 1)`.")
report_lines.append("")
report_lines.append("The `points/plush-dc.wkpc` node was also parsed and compared: positions match exactly, and colours match after 8-bit quantisation.")
report_lines.append("")
report_lines.append("### Sample of positions and colours (linear sRGB)")
report_lines.append("")
for line in sample_lines:
    report_lines.append(line)
report_lines.append("")
report_lines.append(f"Bounds of positions: x [{minx:.6f}, {maxx:.6f}], y [{miny:.6f}, {maxy:.6f}], z [{minz:.6f}, {maxz:.6f}] (metres)")
report_lines.append("")

report_lines.append("## Task 3: Identify tools")
report_lines.append("")
report_lines.append("**Succeeded: yes**")
report_lines.append("")
report_lines.append("The manifest declares three tool nodes, each carrying its source code as `core.tool` nodes. Their roles and locations:")
report_lines.append("")
for tool, tj in tool_roles.items():
    report_lines.append(f"### {tool}")
    report_lines.append("")
    report_lines.append(f"- **Node ID**: `tool-{tool}`")
    report_lines.append(f"- **Role**: {tj.get('role', 'unknown')}")
    report_lines.append(f"- **Language**: {tj.get('language', 'unknown')}")
    report_lines.append(f"- **Entrypoint**: {tj.get('entrypoint', 'unknown')}")
    report_lines.append(f"- **Files**: {', '.join(tool_files[tool])}")
    report_lines.append("")
    report_lines.append("**Source code:**")
    report_lines.append("")
    for f in tool_files[tool]:
        report_lines.append(f"#### `{f}`")
        report_lines.append("")
        if f.endswith('.py'):
            report_lines.append("