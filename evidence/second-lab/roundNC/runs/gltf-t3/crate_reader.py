"""Open crate-nc-v1.gltf, list contents, verify integrity, extract primary mesh + texture.

Every binary rule used here is either read from the JSON (byteOffset/byteLength/
count/type/min/max) or *derived empirically* from the data by derive_codes();
nothing is taken from an external spec. See REPORT.md.

Usage: python -I crate_reader.py <dir-containing-gltf> <out-dir>
"""
import hashlib, json, os, struct, sys

GLTF = "crate-nc-v1.gltf"
# Number of scalar components per element, from the "type" strings. The names
# VEC2/VEC3/SCALAR self-describe; verified below against byteLength/count.
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def load(base):
    raw = open(os.path.join(base, GLTF), "rb").read()
    doc = json.loads(raw)
    bufs = [open(os.path.join(base, b["uri"]), "rb").read() for b in doc["buffers"]]
    return raw, doc, bufs


def view_bytes(doc, bufs, vi):
    v = doc["bufferViews"][vi]
    off = v.get("byteOffset", 0)
    return bufs[v["buffer"]][off:off + v["byteLength"]]


def derive_codes(doc, bufs):
    """Infer the meaning of each componentType code from the data.

    size  = byteLength / (count * ncomp), must be integral and consistent.
    kind  = for 4-byte codes: try little/big-endian float32 and pick the one
            whose per-component min/max equal the declared min/max exactly.
            for 2-byte codes used as 'indices': try LE/BE unsigned and pick
            the one whose max < vertex count of the same primitive.
    """
    sizes, findings = {}, []
    for i, a in enumerate(doc["accessors"]):
        v = doc["bufferViews"][a["bufferView"]]
        n = a["count"] * NCOMP[a["type"]]
        size, rem = divmod(v["byteLength"], n)
        if rem:
            raise ValueError(f"accessor {i}: byteLength not a multiple of count*ncomp")
        prev = sizes.setdefault(a["componentType"], size)
        if prev != size:
            raise ValueError(f"componentType {a['componentType']} has inconsistent size")
    fmt = {}
    for code, size in sizes.items():
        users = [(i, a) for i, a in enumerate(doc["accessors"]) if a["componentType"] == code]
        if size == 4:
            for endian in "<>":
                ok = True
                for i, a in users:
                    if "min" not in a:
                        continue
                    nc = NCOMP[a["type"]]
                    vals = struct.unpack(f"{endian}{a['count']*nc}f", view_bytes(doc, bufs, a["bufferView"]))
                    cols = [vals[k::nc] for k in range(nc)]
                    if [min(c) for c in cols] != [struct.unpack("f", struct.pack("f", m))[0] for m in a["min"]] \
                       or [max(c) for c in cols] != [struct.unpack("f", struct.pack("f", m))[0] for m in a["max"]]:
                        ok = False
                if ok:
                    fmt[code] = endian + "f"
                    findings.append(f"code {code}: 4-byte, {'little' if endian=='<' else 'big'}-endian float32 "
                                    f"(declared min/max reproduced exactly)")
                    break
        elif size == 2:
            idx_users = {p["indices"]: p["attributes"]["POSITION"]
                         for m in doc["meshes"] for p in m["primitives"]}
            for endian in "<>":
                ok = True
                for i, a in users:
                    vals = struct.unpack(f"{endian}{a['count']}H", view_bytes(doc, bufs, a["bufferView"]))
                    vcount = doc["accessors"][idx_users[i]]["count"]
                    if max(vals) >= vcount:
                        ok = False
                if ok:
                    fmt[code] = endian + "H"
                    findings.append(f"code {code}: 2-byte, {'little' if endian=='<' else 'big'}-endian unsigned int "
                                    f"(all index values < vertex count; signed/unsigned indistinguishable here)")
                    break
        if code not in fmt:
            raise ValueError(f"could not derive meaning of componentType {code}")
    return fmt, findings


def read_accessor(doc, bufs, fmt, ai):
    a = doc["accessors"][ai]
    nc = NCOMP[a["type"]]
    f = fmt[a["componentType"]]
    vals = struct.unpack(f"{f[0]}{a['count']*nc}{f[1]}", view_bytes(doc, bufs, a["bufferView"]))
    return [vals[k:k + nc] for k in range(0, len(vals), nc)]


def list_contents(doc):
    print("== asset:", doc["asset"])
    s = doc["scenes"][doc.get("scene", 0)]
    print(f"== default scene {doc.get('scene',0)} '{s['name']}' (root of the node graph)")
    for ni in s["nodes"]:
        n = doc["nodes"][ni]
        m = doc["meshes"][n["mesh"]]
        print(f"  node {ni} '{n['name']}': places mesh {n['mesh']} '{m['name']}'"
              f" (no transform keys -> identity placement assumed; no children)")
        for pi, p in enumerate(m["primitives"]):
            print(f"    primitive {pi}: material {p['material']} '{doc['materials'][p['material']]['name']}'")
            for sem, ai in p["attributes"].items():
                a = doc["accessors"][ai]
                print(f"      {sem:<11} -> accessor {ai}: {a['count']} x {a['type']} code {a['componentType']}")
            a = doc["accessors"][p["indices"]]
            print(f"      indices     -> accessor {p['indices']}: {a['count']} x SCALAR"
                  f" = {a['count']//3} triangles if read as triples")
    for i, mat in enumerate(doc["materials"]):
        print(f"== material {i} '{mat['name']}': {json.dumps(mat)}")
    for i, t in enumerate(doc["textures"]):
        print(f"== texture {i}: image {t['source']} '{doc['images'][t['source']]['uri']}', "
              f"sampler {t['sampler']} {doc['samplers'][t['sampler']]} (filter codes: meaning not derivable)")
    for i, v in enumerate(doc["bufferViews"]):
        print(f"== bufferView {i}: buffer {v['buffer']} [{v['byteOffset']}..{v['byteOffset']+v['byteLength']}) "
              f"target {v.get('target')}")


def verify(raw, doc, bufs, fmt):
    """Structural integrity checks. There are NO declared hashes in the file."""
    problems = []
    declared = [k for k in ("sha256", "hash", "digest", "checksum") if k in raw.decode("utf-8").lower()]
    print("== declared hashes in manifest:", declared or "NONE")
    for i, b in enumerate(doc["buffers"]):
        if len(bufs[i]) != b["byteLength"]:
            problems.append(f"buffer {i} length {len(bufs[i])} != declared {b['byteLength']}")
    spans = sorted((v.get("byteOffset", 0), v["byteLength"], i) for i, v in enumerate(doc["bufferViews"]))
    pos = 0
    for off, ln, i in spans:
        if off != pos:
            problems.append(f"bufferView {i} gap/overlap at {off} (expected {pos})")
        pos = off + ln
    if pos != doc["buffers"][0]["byteLength"]:
        problems.append(f"bufferViews end at {pos}, buffer is {doc['buffers'][0]['byteLength']}")
    # target codes: check they partition exactly into index views vs attribute views
    idx_views = {doc["accessors"][p["indices"]]["bufferView"] for m in doc["meshes"] for p in m["primitives"]}
    tmap = {}
    for i, v in enumerate(doc["bufferViews"]):
        tmap.setdefault(v.get("target"), set()).add(i in idx_views)
    for t, kinds in tmap.items():
        if len(kinds) != 1:
            problems.append(f"target {t} used for both index and attribute views")
    print("== target codes:", {t: ("index data" if True in k else "vertex attribute data") for t, k in tmap.items()})
    for m in doc["meshes"]:
        for p in m["primitives"]:
            vc = doc["accessors"][p["attributes"]["POSITION"]]["count"]
            for ai in p["attributes"].values():
                if doc["accessors"][ai]["count"] != vc:
                    problems.append(f"mesh {m['name']}: attribute count mismatch")
            if doc["accessors"][p["indices"]]["count"] % 3:
                problems.append(f"mesh {m['name']}: index count not divisible by 3")
            nrm = read_accessor(doc, bufs, fmt, p["attributes"]["NORMAL"])
            bad = sum(1 for n in nrm if abs(sum(c * c for c in n) - 1) > 1e-3)
            if bad:
                problems.append(f"mesh {m['name']}: {bad} normals not unit length")
    for img in doc["images"]:
        data = open(os.path.join(BASE, img["uri"]), "rb").read()
        sig = data[1:4]
        if sig.decode("latin-1") != img["mimeType"].split("/")[1].upper():
            problems.append(f"image {img['uri']}: leading bytes do not name its mimeType")
    print("== structural problems:", problems or "none")
    return problems


def pick_primary(doc):
    """No 'primary' marker exists; choose the node whose name is the common
    prefix of all node names (the base object), falling back to most vertices."""
    names = [doc["nodes"][i]["name"] for i in doc["scenes"][doc.get("scene", 0)]["nodes"]]
    for ni in doc["scenes"][doc.get("scene", 0)]["nodes"]:
        n = doc["nodes"][ni]
        if all(x.startswith(n["name"]) for x in names):
            return ni
    return max(doc["scenes"][0]["nodes"],
               key=lambda ni: doc["accessors"][doc["meshes"][doc["nodes"][ni]["mesh"]]["primitives"][0]
                              ["attributes"]["POSITION"]]["count"])


def extract(doc, bufs, fmt, out):
    os.makedirs(out, exist_ok=True)
    ni = pick_primary(doc)
    node = doc["nodes"][ni]
    prim = doc["meshes"][node["mesh"]]["primitives"][0]
    results = {}
    # 1. raw byte slices, exactly as stored (these are what any hash would cover)
    for sem, ai in list(prim["attributes"].items()) + [("INDICES", prim["indices"])]:
        b = view_bytes(doc, bufs, doc["accessors"][ai]["bufferView"])
        p = os.path.join(out, f"{node['name']}.{sem}.raw")
        open(p, "wb").write(b)
        results[p] = sha(b)
    # 2. a human-usable Wavefront OBJ (output format is my choice, not from the file)
    P = read_accessor(doc, bufs, fmt, prim["attributes"]["POSITION"])
    N = read_accessor(doc, bufs, fmt, prim["attributes"]["NORMAL"])
    T = read_accessor(doc, bufs, fmt, prim["attributes"]["TEXCOORD_0"])
    I = [i[0] for i in read_accessor(doc, bufs, fmt, prim["indices"])]
    lines = [f"# {node['name']} / {doc['meshes'][node['mesh']]['name']} from {GLTF}", "mtllib none"]
    lines += [f"v {x:.9g} {y:.9g} {z:.9g}" for x, y, z in P]
    lines += [f"vn {x:.9g} {y:.9g} {z:.9g}" for x, y, z in N]
    # V flipped: assumption -- the file does not say where the UV origin is
    lines += [f"vt {u:.9g} {1 - v:.9g}" for u, v in T]
    for k in range(0, len(I), 3):
        a, b, c = (i + 1 for i in I[k:k + 3])
        lines.append(f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}")
    p = os.path.join(out, f"{node['name']}.obj")
    data = ("\n".join(lines) + "\n").encode()
    open(p, "wb").write(data)
    results[p] = sha(data)
    # 3. texture: byte-for-byte copy of the base colour image
    tex = doc["textures"][doc["materials"][prim["material"]]["pbrMetallicRoughness"]["baseColorTexture"]["index"]]
    img = doc["images"][tex["source"]]
    data = open(os.path.join(BASE, img["uri"]), "rb").read()
    p = os.path.join(out, img["uri"])
    open(p, "wb").write(data)
    results[p] = sha(data)
    print(f"== primary mesh: node {ni} '{node['name']}' ({len(P)} vertices, {len(I)//3} triangles)")
    return results


if __name__ == "__main__":
    BASE, OUT = sys.argv[1], sys.argv[2]
    raw, doc, bufs = load(BASE)
    print("== input sha256:", GLTF, sha(raw))
    for b in doc["buffers"]:
        print("== input sha256:", b["uri"], sha(bufs[doc["buffers"].index(b)]))
    fmt, findings = derive_codes(doc, bufs)
    for f in findings:
        print("== derived:", f)
    list_contents(doc)
    verify(raw, doc, bufs, fmt)
    for p, h in extract(doc, bufs, fmt, OUT).items():
        print(f"== wrote {p}  sha256 {h}  (declared: none)")
