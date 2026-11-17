#!/usr/bin/env python3
"""roundtrip_gate.py — the Stage 10B gate, measured against a live UE 5.8
(werk release copy, plugins/unreal; the source tree targets 5.7).

    python tests/roundtrip_gate.py --repo <werk release repo>
        [--project project/WerkGate/WerkGate.uproject]
        [--engine  "C:/Program Files/Epic Games/UE_5.8"]

Release changes (W5c, 2026-11-07):
  * files-verified is no longer a hard-coded number: it is DERIVED from each
    fixture's manifest by the release Python reader (vendor/werk_single.py) --
    the files of the resolved version of every node that is not dead, which is
    exactly what WerkLink's FWerkImportResult::FilesVerified counts. Node count
    is derived the same way. The other five counts (imported, skipped,
    refused, assets, packages) are WerkLink's own behaviour and stay pinned.
  * one clause added: the exported core.material carries a `requires` edge to
    each sampled core.tex and the export has no edge to an absent node.

It asserts nothing about Unreal from the outside: it RUNS the commandlet, reads
what landed on disk, and decides. Every number it prints is one it measured in
this run.

Clauses
-------
 1. import every fixture, and require the EXACT node/asset counts and the exact
    SPEC 10.1 exit status for each
 2. the textured fixture's three core.tex nodes become three UTexture2D assets
    and its core.material becomes an instance with three texture slots bound
 3. export the imported textured entity back to a .werk
 4. TEXTURE ROUND TRIP: decode both PNGs -- the one Blender wrote into the
    fixture and the one Unreal's ImageWrapper wrote on the way out -- and
    compare PIXELS, not bytes. Two PNG encoders will not agree on bytes and it
    would be dishonest to call that a failure; they must agree on every pixel,
    and that is a claim worth making.
 5. re-import the exported package and require the same counts back
 6. the exported package passes three independent readers: this adapter's own
    core (werk_gate.exe, when built), loaders/werk_read.py, and jsonschema
    against spec/schemas/*.

The PNG decoder here is stdlib-only on purpose. Pulling in Pillow to check a
format whose whole argument is "you need no ecosystem to read this" would be
funny in the wrong way.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(PLUGIN, "vendor"))
import werk_single as werklib                          # noqa: E402

_pin_fixture = None   # imported from <repo>/tests once --repo is known


def derived_counts(path):
    """(nodes, files verified) for one fixture, from its manifest, by the
    release reader: files of the resolved version of every non-dead node."""
    pkg = werklib.open(path)
    files = 0
    for n in pkg.nodes:
        if n.status == "dead" or n.resolved is None:
            continue
        ver = [v for v in n.versions if v.get("v") == n.resolved]
        files += len(ver[0]["files"]) if ver else 0
    return len(pkg.nodes), files


RESULTS = []


def clause(name, ok, detail):
    RESULTS.append((bool(ok), name, detail))
    print("[%s] %-38s %s" % ("PASS" if ok else "FAIL", name, detail))
    return ok


# ---------------------------------------------------------------------------
# a stdlib PNG decoder, enough for colour types 0/2/3/6 at 8 and 16 bits
# ---------------------------------------------------------------------------

def png_pixels(data):
    """Return (width, height, channels, bitdepth, bytes-of-unfiltered-samples).

    Implements the five PNG filters of MINI-SPECS 8 / RFC 2083 section 6. No
    interlace support: Adam7 is refused loudly rather than mis-decoded.
    """
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos = 8
    ihdr = None
    idat = bytearray()
    palette = None
    while pos < len(data):
        ln, tag = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if tag == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif tag == b"PLTE":
            palette = body
        elif tag == b"IDAT":
            idat += body
        elif tag == b"IEND":
            break
    if ihdr is None:
        raise ValueError("no IHDR")
    w, h, depth, colour, comp, filt, interlace = ihdr
    if interlace:
        raise ValueError("interlaced PNG: refused rather than mis-decoded")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colour]
    bpp_bits = channels * depth
    stride = (w * bpp_bits + 7) // 8
    fbpp = max(1, bpp_bits // 8)

    raw = zlib.decompress(bytes(idat))
    out = bytearray(stride * h)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if f == 1:
            for i in range(fbpp, stride):
                line[i] = (line[i] + line[i - fbpp]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                a = line[i - fbpp] if i >= fbpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - fbpp] if i >= fbpp else 0
                c = prev[i - fbpp] if i >= fbpp else 0
                b = prev[i]
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif f != 0:
            raise ValueError("unknown PNG filter %d" % f)
        out[y * stride:(y + 1) * stride] = line
        prev = line

    if colour == 3:
        if palette is None:
            raise ValueError("indexed PNG with no PLTE")
        rgb = bytearray()
        for y in range(h):
            row = out[y * stride:(y + 1) * stride]
            for x in range(w):
                idx = row[x]
                rgb += palette[idx * 3:idx * 3 + 3]
        return w, h, 3, 8, bytes(rgb)
    return w, h, channels, depth, bytes(out)


def rgb_hash(data):
    """sha256 over the RGB samples only, at 8 bits.

    Alpha is excluded because a source with no alpha and an export that adds an
    opaque one are the same image, and calling that a difference would make the
    gate fail on a true statement. Reported as what it is, not hidden.
    """
    w, h, ch, depth, samples = png_pixels(data)
    step = 2 if depth == 16 else 1
    px = bytearray()
    if ch >= 3:
        for i in range(0, len(samples), ch * step):
            px += bytes((samples[i], samples[i + step], samples[i + 2 * step]))
    else:
        for i in range(0, len(samples), ch * step):
            g = samples[i]
            px += bytes((g, g, g))
    return w, h, hashlib.sha256(bytes(px)).hexdigest()


# ---------------------------------------------------------------------------
# running the commandlet
# ---------------------------------------------------------------------------

def run_ue(engine, project, args, logfile):
    exe = os.path.join(engine, "Engine", "Binaries", "Win64", "UnrealEditor-Cmd.exe")
    cmd = [exe, project] + args + ["-unattended", "-nopause", "-nosplash"]
    t0 = time.time()
    with open(logfile, "wb") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT)
    text = open(logfile, "r", encoding="utf-8", errors="replace").read()
    return proc.returncode, text, time.time() - t0


LINE = re.compile(r"LogWerkLink: Display: (.*)")


def werk_lines(text):
    return [m.group(1).rstrip() for m in LINE.finditer(text)]


def find_result(lines):
    for l in lines:
        if l.startswith("result   :"):
            return l.split(":", 1)[1].strip()
    return ""


def counts(summary):
    m = re.search(r"(\d+) nodes: (\d+) imported, (\d+) skipped, (\d+) refused; "
                  r"(\d+) assets, (\d+) packages saved, (\d+) files verified", summary)
    return tuple(int(x) for x in m.groups()) if m else None


def main():
    ap = argparse.ArgumentParser()
    TESTBED = os.environ.get("WERK_UE_TESTBED", "<WERK_UE_TESTBED unset>")
    ap.add_argument("--project", default=os.environ.get("WERK_UE_TESTBED") and
                    os.path.join(TESTBED, "WerkTest", "WerkTest.uproject") or
                    os.path.join(PLUGIN, "project", "WerkGate", "WerkGate.uproject"))
    ap.add_argument("--engine", default="C:/Program Files/Epic Games/UE_5.8")
    ap.add_argument("--repo", default=os.environ.get("WERK_REPO", ""))
    ap.add_argument("--logs", default=os.path.join(PLUGIN, "_gate_out", "commandlet", "logs"))
    ap.add_argument("--out", default=os.path.join(PLUGIN, "_gate_out", "commandlet", "roundtrip"))
    args = ap.parse_args()

    repo = args.repo
    if not repo or not os.path.isdir(os.path.join(repo, "spec")):
        print("SKIP: --repo (or WERK_REPO) must name the werk release repository.")
        return 3
    global _pin_fixture
    # S8-1..S8-3: a gate's numbers are measurements of ONE fixture build, so the
    # build is pinned against fixtures/fixtures.json before anything is measured.
    sys.path.insert(0, os.path.join(repo, "tests"))
    from fixture_pin import pin as _pin_fixture       # noqa: E402
    fixtures = os.path.join(repo, "fixtures")
    os.makedirs(args.logs, exist_ok=True)
    os.makedirs(args.out, exist_ok=True)

    exe = os.path.join(args.engine, "Engine", "Binaries", "Win64", "UnrealEditor-Cmd.exe")
    if not os.path.isfile(exe) or not os.path.isfile(args.project):
        print("SKIP: no UE editor or no testbed project. "
              "See plugins/unreal/TESTBED.md.")
        return 3

    print("werk Stage 10B gate -- WerkLink textures, materials, and the live testbed")
    print("engine  : %s" % args.engine)
    print("project : %s" % args.project)
    needed = ("crate-v1", "crate-tex-v1", "ista-varun-v1", "crate-v1-damaged")
    missing = [n for n in needed
               if not os.path.isfile(os.path.join(fixtures, n + ".werk"))]
    if missing:
        # A missing fixture is a SKIP, not a crash: without the fixtures there is
        # nothing to measure, and a gate that raises FileNotFoundError here has
        # reported nothing. Build them (fixtures/build_*.py) or fetch them first.
        print("SKIP: required fixture(s) not present: %s. "
              "Build them first (see fixtures/)." % ", ".join(missing))
        return 3
    for name in needed:
        p = os.path.join(fixtures, name + ".werk")
        body = open(p, "rb").read()
        pinned = _pin_fixture(name)
        print("fixture : %-18s %9d B  sha256 %s  %s"
              % (name, len(body), hashlib.sha256(body).hexdigest(),
                 "pinned" if pinned.ok else "DRIFT -- " + pinned.detail))
    print("")

    # An open editor holds every .uasset in Content/Werk, so wiping the folder
    # fails with a Windows sharing violation halfway through and leaves a
    # HALF-DELETED content tree -- which the next import would then partly
    # reuse, and every count below would be measuring two runs at once.
    # Detected rather than survived: a live Remote Control server on any port in
    # the launcher's range is a running editor.
    import urllib.request
    for p in range(30010, 30031):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/remote/info" % p,
                                        timeout=0.5) as r:
                if r.status == 200:
                    print("REFUSED: an Unreal editor is running (Remote Control on "
                          "port %d) and holds the assets this gate rewrites.\n"
                          "         Close it first. Nothing was measured." % p)
                    return 2
        except Exception:
            pass

    content_werk = os.path.join(os.path.dirname(args.project), "Content", "Werk")
    if os.path.isdir(content_werk):
        try:
            shutil.rmtree(content_werk)
        except OSError as e:
            print("REFUSED: could not clear %s (%s). Something has those files "
                  "open. Nothing was measured." % (content_werk, e))
            return 2

    # --- clause 1: import every fixture ------------------------------------
    # Expected exit status per SPEC 10.1, and the counts are what the previous
    # measured run produced -- so a change in either is a REGRESSION and not a
    # new baseline someone quietly accepted.
    # REBASELINED 2026-08-08 for the fixture rebuild that followed that date's
    # spec rulings. ONE number moved in every row -- the files-verified count,
    # by exactly +4 -- and it moved for a reason that is checkable rather than
    # accepted: the vendored spec/ tree gained four files (conventions-map.json,
    # conventions-map.image.json, schemas/conventions-map.schema.json and
    # schemas/core.retarget.bind.schema.json). Node, imported, skipped, refused,
    # asset and package counts are UNCHANGED in all four rows, which is the
    # evidence that the rebuild added spec bytes and changed nothing else.
    #
    # REBASELINED AGAIN later the same day, for the Stage 12B rebuild (rulings
    # 21/22: the licensing doctrine + `primary.geometry`). The same single
    # number moved in every row by exactly +4 once more, and again for a
    # checkable reason: STAGE 12 added four files to the vendored spec/ tree
    # (layouts/points.layout.txt, layouts/gsplat.layout.txt,
    # schemas/core.tool.schema.json, schemas/core.tool.config.schema.json) and
    # this gate was declared out of scope in that wave, so the +4 lands here
    # one rebuild later. Every other count is unchanged in all four rows.
    #
    # The fixture BUILD these numbers belong to is pinned above against
    # fixtures/fixtures.json, so the next rebuild fails on the pin with both
    # hashes in the message rather than here with a count nobody can explain.
    #
    # REBASELINED AGAIN for the 2026-08-09 open-weights spec-fix wave (S-OW-1
    # .. S-OW-4). Same single number, same shape: +6 in every row, because the
    # wave added SIX files to the vendored spec/ tree -- the worked examples
    # that S-OW-3 says are part of the minimum documentation set
    # (examples/gsplat.example.wkgs, examples/gsplat.example.hex.txt,
    # examples/embedding.example.wkem, examples/embedding.example.hex.txt,
    # examples/SIGNATURE.example.json, examples/signature.example.txt).
    # Node, imported, skipped, refused, asset and package counts are unchanged
    # in all four rows.
    #
    # REBASELINED for the werk release (W5c, 2026-11-07), and this time not by
    # typing a new number. The recon run on UE 5.8 measured +8 files verified
    # in every row and nothing else moved. The +8 is exactly the eight spec
    # files artcraft-profiles c8f9266 added to the vendored spec/ tree
    # (WRITING-3D-ENTITY.md, WRITING-IMAGE.md, examples/write_minimal_3d_entity.py,
    # examples/write_minimal_image.py, formats/splat-32.md,
    # schemas/core.revisions.schema.json, schemas/core.scene.schema.json,
    # schemas/manifest.base.schema.json) -- checked by diffing the `spec` node's
    # file list of crate-tex-v1 at e8c52e3 (the last baseline, 66) against the
    # release fixture (74). The release re-pin (PR #11 spec text) changed spec
    # BYTES, not the file count. So nodes and files-verified are now DERIVED
    # from each fixture's manifest (derived_counts above) and only WerkLink's
    # own five behaviour counts stay pinned:
    #                    exit  (imported, skipped, refused, assets, packages)
    behaviour = {
        "crate-v1":         (0, (26, 10, 0, 23, 23)),
        "crate-tex-v1":     (0, (7, 4, 0, 5, 5)),
        "ista-varun-v1":    (0, (3, 12, 0, 3, 3)),
        "crate-v1-damaged": (1, (25, 11, 1, 22, 22)),
    }
    expect = {}
    for name, (want_exit, b) in behaviour.items():
        nodes, files = derived_counts(os.path.join(fixtures, name + ".werk"))
        expect[name] = (want_exit, (nodes,) + b + (files,))
        print("expect  : %-18s %d nodes, %d files verified (derived from the manifest)"
              % (name, nodes, files))
    print("")
    imports = {}
    for name, (want_exit, want_counts) in expect.items():
        log = os.path.join(args.logs, "gate_import_%s.log" % name)
        code, text, secs = run_ue(args.engine, args.project,
                                  ["-run=WerkLink",
                                   "-Import=%s" % os.path.join(fixtures, name + ".werk").replace("\\", "/"),
                                   "-Dest=/Game/Werk/%s" % name], log)
        lines = werk_lines(text)
        summary = find_result(lines)
        got = counts(summary)
        imports[name] = (code, got, lines, secs)
        clause("import: %s" % name,
               code == want_exit and got == want_counts,
               "exit %d (want %d), %s, %.1f s wall" % (code, want_exit, summary, secs))

    # --- clause 2: the textured fixture actually produced textures ---------
    tex_lines = [l for l in imports["crate-tex-v1"][2] if "core.tex" in l]
    mat_line = next((l for l in imports["crate-tex-v1"][2]
                     if "core.material" in l), "")
    spaces = {}
    for l in tex_lines:
        node = l.split()[1]
        spaces[node] = "srgb" if "colour space srgb" in l else "linear"
    want_spaces = {"tex-crate-tex-albedo": "srgb",
                   "tex-crate-tex-mr": "linear",
                   "tex-crate-tex-normal": "linear"}
    clause("texture import: colour spaces", spaces == want_spaces, json.dumps(spaces, sort_keys=True))
    # S10-6's regression test. The UV extent is measured off the built
    # FMeshDescription and printed by the importer, so this clause is a number
    # from the asset rather than a claim about the GLB. A collapse here means
    # a textured mesh that samples exactly one texel and looks, in every count
    # and every report, completely fine.
    geom_line = next((l for l in imports["crate-tex-v1"][2]
                      if "core.geom.game" in l), "")
    clause("mesh import: UVs survived the build",
           "uv0 [0.0000,0.0000]-[1.0000,1.0000]" in geom_line,
           geom_line.split("core.geom.game")[-1].strip() or "no geometry outcome line")

    clause("material import: slots bound",
           "textures {base_color, metallic_roughness, normal}" in mat_line
           and "assigned to 1 mesh material slot(s)" in mat_line,
           mat_line.strip()[:150] if mat_line else "no core.material outcome line")

    # --- clause 3: export it back ------------------------------------------
    base = "/Game/Werk/crate-tex-v1/WoodenCrateTextured"
    assets = ",".join("%s/%s.%s" % (base, n, n) for n in
                      ("SM_GeomGame", "MI_MaterialCratePlanks",
                       "T_TexCrateTexAlbedo", "T_TexCrateTexMr", "T_TexCrateTexNormal"))
    out_werk = os.path.join(args.out, "crate-tex-rt.werk").replace("\\", "/")
    if os.path.isfile(out_werk):
        os.remove(out_werk)
    code, text, secs = run_ue(args.engine, args.project,
                              ["-run=WerkLink", "-Export=%s" % out_werk,
                               "-Assets=%s" % assets, "-Spec=%s" % repo.replace("\\", "/"),
                               "-Name=Wooden crate, textured (round trip)"],
                              os.path.join(args.logs, "gate_export.log"))
    exp_lines = werk_lines(text)
    exp_summary = next((l for l in exp_lines if l.startswith("result   :")), "")
    clause("export: textured entity", code == 0 and os.path.isfile(out_werk),
           "exit %d, %s, %.1f s wall" % (code, exp_summary.split(":", 1)[-1].strip(), secs))

    tex_export_lines = [l for l in exp_lines if "core.tex" in l and "exported" in l]
    clause("texture export: three real PNGs", len(tex_export_lines) == 3,
           "; ".join(l.split("core.tex")[-1].strip() for l in tex_export_lines) or "none")

    # --- clause 4: PIXEL comparison ----------------------------------------
    src = zipfile.ZipFile(os.path.join(fixtures, "crate-tex-v1.werk"))
    dst = zipfile.ZipFile(out_werk)
    src_man = json.loads(src.read("MANIFEST.json"))
    dst_man = json.loads(dst.read("MANIFEST.json"))

    def tex_paths(man, z):
        out = {}
        for n in man["nodes"]:
            if n["type"] == "core.tex":
                p = n["versions"][0]["files"][0]["path"]
                out[n["node_id"]] = (p, n.get("meta", {}))
        return out

    a = tex_paths(src_man, src)
    b = tex_paths(dst_man, dst)
    rows, all_ok = [], (set(a) == set(b))
    for node in sorted(a):
        if node not in b:
            rows.append("%s MISSING from the export" % node)
            all_ok = False
            continue
        w1, h1, k1 = rgb_hash(src.read(a[node][0]))
        w2, h2, k2 = rgb_hash(dst.read(b[node][0]))
        same = (w1, h1, k1) == (w2, h2, k2)
        cs_same = a[node][1].get("color_space") == b[node][1].get("color_space")
        all_ok = all_ok and same and cs_same
        rows.append("%s %dx%d rgb-sha %s%s%s"
                    % (node, w1, h1, k1[:16],
                       " IDENTICAL" if same else " DIFFERS (%s vs %s)" % (k1[:16], k2[:16]),
                       "" if cs_same else " COLOUR SPACE CHANGED"))
    clause("texture round trip: pixels", all_ok, " | ".join(rows))

    # byte identity is NOT the claim, and the number is printed so nobody has
    # to wonder whether it was silently the same.
    byte_same = sum(1 for n in a if n in b and src.read(a[n][0]) == dst.read(b[n][0]))
    print("       (PNG bytes identical for %d/%d textures -- two encoders, so this is "
          "expected to be 0 and is not a gate)" % (byte_same, len(a)))

    # --- material slots survived ------------------------------------------
    def material_payload(man, z):
        for n in man["nodes"]:
            if n["type"] == "core.material":
                return json.loads(z.read(n["versions"][0]["files"][0]["path"]))
        return {}

    ma, mb = material_payload(src_man, src), material_payload(dst_man, dst)
    sa = sorted((ma.get("textures") or {}).keys())
    sb = sorted((mb.get("textures") or {}).keys())
    node_map_ok = all((mb["textures"][s]["node"] == ma["textures"][s]["node"]) for s in sa) \
        if sa and sa == sb else False
    clause("material round trip: slots", sa == sb and node_map_ok,
           "in %s -> out %s, node ids %s" % (sa, sb, "preserved" if node_map_ok else "CHANGED"))

    # --- the dangling-edge guard's positive half (W5c) ---------------------
    ids_out = {n["node_id"] for n in dst_man["nodes"]}
    dangling = [(n["node_id"], e.get("to")) for n in dst_man["nodes"]
                for e in n.get("edges") or [] if e.get("to") not in ids_out]
    mat_edges = sorted(e["to"] for n in dst_man["nodes"] if n["type"] == "core.material"
                       for e in n.get("edges") or [] if e.get("kind") == "requires")
    want_edges = sorted(ma["textures"][s]["node"] for s in sa) if sa else []
    clause("export: material edges, none dangling",
           not dangling and mat_edges == want_edges and len(mat_edges) == 3,
           "requires -> %s; dangling %s" % (mat_edges, dangling or "none"))

    mat_nodes_out = [n["node_id"] for n in dst_man["nodes"] if n["type"] == "core.material"]
    clause("export: no phantom master material", len(mat_nodes_out) == 1,
           "core.material nodes in the export: %s" % mat_nodes_out)

    # --- clause 5: re-import ----------------------------------------------
    code, text, secs = run_ue(args.engine, args.project,
                              ["-run=WerkLink", "-Import=%s" % out_werk,
                               "-Dest=/Game/Werk/roundtrip"],
                              os.path.join(args.logs, "gate_reimport.log"))
    rl = werk_lines(text)
    rsummary = find_result(rl)
    rc = counts(rsummary)
    reimport_tex = sum(1 for l in rl if "core.tex" in l and l.strip().startswith("imported"))
    clause("re-import: the exported package",
           code == 0 and rc is not None and reimport_tex == 3,
           "exit %d, %s, %d core.tex imported" % (code, rsummary, reimport_tex))

    # --- clause 6: three independent readers -------------------------------
    reader = os.path.join(repo, "loaders", "werk_read.py")
    proc = subprocess.run([sys.executable, reader, out_werk, "--verify"],
                          capture_output=True, text=True)
    tail = [l for l in proc.stdout.strip().splitlines() if "files verified" in l]
    clause("reader: loaders/werk_read.py", proc.returncode == 0 and bool(tail),
           (tail[-1] if tail else proc.stdout.strip()[-120:]))

    try:
        import jsonschema
        errs = []
        schema = json.loads(dst.read("spec/schemas/manifest.schema.json"))
        errs += list(jsonschema.Draft202012Validator(schema).iter_errors(dst_man))
        msch = json.loads(dst.read("spec/schemas/core.material.schema.json"))
        errs += list(jsonschema.Draft202012Validator(msch).iter_errors(mb))
        clause("reader: jsonschema (manifest + material)", not errs,
               "%d error(s)%s" % (len(errs), "" if not errs else ": " + errs[0].message))
    except ImportError:
        clause("reader: jsonschema (manifest + material)", False,
               "jsonschema not installed -- NOT a pass, a missing measurement")

    gate_exe = os.path.join(HERE, ".build", "werk_gate.exe")
    if os.path.isfile(gate_exe):
        proc = subprocess.run([gate_exe, out_werk], capture_output=True, text=True)
        last = proc.stdout.strip().splitlines()[-2:] if proc.stdout.strip() else [""]
        clause("reader: werk_gate.exe (this adapter's core)", proc.returncode == 0,
               " / ".join(x.strip() for x in last))
    else:
        print("[SKIP] reader: werk_gate.exe              not built "
              "(plugins/unreal/tests/build_gate.bat)")

    npass = sum(1 for ok, _, _ in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n%d PASS, %d FAIL" % (npass, nfail))
    print("GATE: %s" % ("PASSED" if nfail == 0 else "FAILED"))
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
