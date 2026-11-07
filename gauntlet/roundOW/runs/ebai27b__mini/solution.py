#!/usr/bin/env python3
"""
solution.py - Open mini-v1.werk, list contents with meanings, verify integrity,
extract primary mesh and one sound, and write REPORT.md.
"""

import zipfile
import json
import hashlib
import os
import sys
from datetime import datetime, timezone


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def main():
    start_time = datetime.now(timezone.utc)
    werk_path = "mini-v1.werk"
    report_lines = []

    def rpt(line=""):
        report_lines.append(str(line))

    rpt("# REPORT.md - mini-v1.werk analysis")
    rpt()

    # Phase 1: Open container and read MANIFEST.json
    phase_open_start = datetime.now(timezone.utc)
    print("[phase] Opening " + werk_path)

    if not os.path.isfile(werk_path):
        print("ERROR: " + werk_path + " not found.")
        sys.exit(1)

    with zipfile.ZipFile(werk_path, "r") as zf:
        bad = zf.testzip()
        if bad is not None:
            print("  ZIP CRC mismatch on entry: " + bad)
        manifest_bytes = zf.read("MANIFEST.json")
        manifest = json.loads(manifest_bytes)

    phase_open_end = datetime.now(timezone.utc)
    open_duration = (phase_open_end - phase_open_start).total_seconds()
    print("  Manifest loaded. Duration: {:.3f}s".format(open_duration))

    # Phase 2: Build path-to-node mapping and list contents
    phase_list_start = datetime.now(timezone.utc)
    print("[phase] Listing contents with meanings ...")

    path_to_node = {}
    for node in manifest.get("nodes", []):
        nid = node["node_id"]
        ntype = node.get("type", "unknown")
        edges_info = ""
        if "edges" in node:
            parts = []
            for e in node["edges"]:
                s = "{}({}) -> {}".format(e["kind"], e["role"], e["to"])
                parts.append(s)
            edges_info = "; ".join(parts)

        for ver in node.get("versions", []):
            note_text = ver.get("note", "")
            for finfo in ver.get("files", []):
                fpath = finfo["path"]
                path_to_node[fpath] = {
                    "node_id": nid,
                    "type": ntype,
                    "note": note_text,
                    "edges": edges_info,
                    "declared_sha256": finfo.get("sha256"),
                    "declared_size": finfo.get("size"),
                    "role": finfo.get("role", "payload"),
                }

    special_files = {
        "MANIFEST.json": {"node_id": "manifest", "type": "core.manifest", "note": "Package manifest"},
        "SIGNATURE.json": {"node_id": "signature", "type": "core.signature", "note": "Ed25519 signature chain"},
        "LICENSE": {"node_id": "license-node", "type": "core.license", "note": "CC-BY-4.0 licence text"},
        "README.txt": {"node_id": "readme-node", "type": "core.readme", "note": "Human-readable overview"},
    }

    rpt("## Container Contents")
    rpt()

    all_entries = sorted(zf.namelist())
    rpt("Total ZIP entries: {}".format(len(all_entries)))
    rpt()
    rpt("| Entry Path | Node ID | Type | Role/Meaning | Declared SHA-256 | Size |")
    rpt("|---|---|---|---|---|---|")

    for entry_name in all_entries:
        info = path_to_node.get(entry_name, special_files.get(entry_name, {}))
        if info:
            nid = info.get("node_id", "-")
            ntype = info.get("type", "-")
            role_meaning = info.get("note", "-")
            declared_sha = info.get("declared_sha256", "") or ""
            declared_size = str(info.get("declared_size", "-"))
        else:
            nid = "-"
            ntype = "-"
            role_meaning = "-"
            declared_sha = ""
            declared_size = "-"

        if len(role_meaning) > 100:
            role_meaning = role_meaning[:97] + "..."

        row = "| {} | {} | {} | {} | {} | {} |".format(
            entry_name, nid, ntype, role_meaning, declared_sha, declared_size)
        rpt(row)

    phase_list_end = datetime.now(timezone.utc)
    list_duration = (phase_list_end - phase_list_start).total_seconds()
    print("  Listed {} entries. Duration: {:.3f}s".format(len(all_entries), list_duration))

    # Phase 3: Verify integrity
    phase_verify_start = datetime.now(timezone.utc)
    print("[phase] Verifying integrity (SHA-256 hashes) ...")

    verification_results = []
    all_declared_files = set()

    for node in manifest.get("nodes", []):
        for ver in node.get("versions", []):
            for finfo in ver.get("files", []):
                fpath = finfo["path"]
                declared_hash = finfo.get("sha256")
                if declared_hash and fpath not in all_declared_files:
                    all_declared_files.add(fpath)

    license_info = manifest.get("license", {})
    if "file" in license_info and "sha256" in license_info:
        lic_path = license_info["file"]
        if lic_path not in all_declared_files:
            all_declared_files.add(lic_path)

    zip_data_cache = {}
    with zipfile.ZipFile(werk_path, "r") as zf:
        for fpath in sorted(all_declared_files):
            try:
                zip_data_cache[fpath] = zf.read(fpath)
            except KeyError:
                verification_results.append({
                    "path": fpath,
                    "status": "MISSING_IN_ZIP",
                    "declared_sha256": "",
                    "computed_sha256": "",
                })

    for node in manifest.get("nodes", []):
        nid = node["node_id"]
        for ver in node.get("versions", []):
            for finfo in ver.get("files", []):
                fpath = finfo["path"]
                declared_hash = finfo.get("sha256")
                if not declared_hash:
                    continue

                data = zip_data_cache.get(fpath)
                if data is None:
                    verification_results.append({
                        "path": fpath,
                        "status": "MISSING_IN_ZIP",
                        "declared_sha256": declared_hash,
                        "computed_sha256": "",
                    })
                    continue

                computed = sha256_hex(data)
                status = "OK" if computed == declared_hash else "MISMATCH"
                verification_results.append({
                    "path": fpath,
                    "status": status,
                    "declared_sha256": declared_hash,
                    "computed_sha256": computed,
                    "node_id": nid,
                })

    if license_info.get("sha256"):
        lic_path = license_info["file"]
        data = zip_data_cache.get(lic_path)
        if data:
            computed = sha256_hex(data)
            declared = license_info["sha256"]
            status = "OK" if computed == declared else "MISMATCH"
            verification_results.append({
                "path": lic_path,
                "status": status,
                "declared_sha256": declared,
                "computed_sha256": computed,
                "node_id": "license",
            })

    try:
        with zipfile.ZipFile(werk_path, "r") as zf:
            sig_bytes = zf.read("SIGNATURE.json")
        sig_data = json.loads(sig_bytes)
        manifest_declared_hash = sig_data.get("manifest_sha256", "")
        if manifest_declared_hash:
            computed_manifest_hash = sha256_hex(manifest_bytes)
            status = "OK" if computed_manifest_hash == manifest_declared_hash else "MISMATCH"
            verification_results.append({
                "path": "MANIFEST.json (via SIGNATURE.json)",
                "status": status,
                "declared_sha256": manifest_declared_hash,
                "computed_sha256": computed_manifest_hash,
                "node_id": "signature-chain",
            })
    except Exception as e:
        verification_results.append({
            "path": "MANIFEST.json (via SIGNATURE.json)",
            "status": "ERROR: " + str(e),
            "declared_sha256": "",
            "computed_sha256": "",
            "node_id": "signature-chain",
        })

    phase_verify_end = datetime.now(timezone.utc)
    verify_duration = (phase_verify_end - phase_verify_start).total_seconds()

    ok_count = sum(1 for r in verification_results if r["status"] == "OK")
    mismatch_count = sum(1 for r in verification_results if r["status"] == "MISMATCH")
    missing_count = sum(1 for r in verification_results if r["status"] == "MISSING_IN_ZIP")

    print("  Verified {} hashes: {} OK, {} mismatch, {} missing.".format(
        len(verification_results), ok_count, mismatch_count, missing_count))
    print("  Duration: {:.3f}s".format(verify_duration))

    rpt()
    rpt("## Integrity Verification")
    rpt()
    rpt("- Files verified: {}".format(len(verification_results)))
    rpt("- Passed (OK): {}".format(ok_count))
    rpt("- Mismatched: {}".format(mismatch_count))
    rpt("- Missing from ZIP: {}".format(missing_count))
    rpt()

    if mismatch_count > 0 or missing_count > 0:
        rpt("### Issues")
        rpt()
        for r in verification_results:
            if r["status"] != "OK":
                row = "| {} | {} | declared: {} | computed: {} |".format(
                    r["path"], r["status"], r["declared_sha256"], r["computed_sha256"])
                rpt(row)

    # Phase 4: Extract primary mesh and one sound
    phase_extract_start = datetime.now(timezone.utc)
    print("[phase] Extracting primary mesh and sound ...")

    primary_info = manifest.get("primary", {})
    primary_mesh_node_id = primary_info.get("mesh", "")
    primary_sound_node_id = primary_info.get("sound", "")

    def find_primary_file(node_id, preferred_role=None):
        for node in manifest.get("nodes", []):
            if node["node_id"] != node_id:
                continue
            active_ver = None
            for ver in node.get("versions", []):
                if ver.get("v") == node.get("active"):
                    active_ver = ver
                    break
            if not active_ver and node.get("versions"):
                active_ver = node["versions"][0]
            if not active_ver:
                return None, {}

            files = active_ver.get("files", [])
            if preferred_role:
                for f in files:
                    if f.get("role") == preferred_role:
                        return f["path"], f
                if files:
                    return files[0]["path"], files[0]
            elif files:
                return files[0]["path"], files[0]
        return None, {}

    mesh_path, mesh_info = find_primary_file(primary_mesh_node_id)
    sound_path, sound_info = find_primary_file(primary_sound_node_id, preferred_role="best")

    extracted_files = []

    if mesh_path:
        with zipfile.ZipFile(werk_path, "r") as zf:
            mesh_data = zf.read(mesh_path)
        out_mesh = os.path.basename(mesh_path)
        with open(out_mesh, "wb") as f:
            f.write(mesh_data)
        computed_mesh_hash = sha256_hex(mesh_data)
        declared_mesh_hash = mesh_info.get("sha256", "")
        mesh_ok = computed_mesh_hash == declared_mesh_hash
        extracted_files.append({
            "path": out_mesh,
            "zip_path": mesh_path,
            "declared_sha256": declared_mesh_hash,
            "computed_sha256": computed_mesh_hash,
            "match": mesh_ok,
            "size": len(mesh_data),
        })
        print("  Extracted {} -> {} ({} bytes)".format(mesh_path, out_mesh, len(mesh_data)))
        print("    Declared SHA-256: {}".format(declared_mesh_hash))
        print("    Computed SHA-256: {}".format(computed_mesh_hash))
        mstr = "YES" if mesh_ok else "NO"
        print("    Match: {}".format(mstr))

    if sound_path:
        with zipfile.ZipFile(werk_path, "r") as zf:
            sound_data = zf.read(sound_path)
        out_sound = os.path.basename(sound_path)
        with open(out_sound, "wb") as f:
            f.write(sound_data)
        computed_sound_hash = sha256_hex(sound_data)
        declared_sound_hash = sound_info.get("sha256", "")
        sound_ok = computed_sound_hash == declared_sound_hash
        extracted_files.append({
            "path": out_sound,
            "zip_path": sound_path,
            "declared_sha256": declared_sound_hash,
            "computed_sha256": computed_sound_hash,
            "match": sound_ok,
            "size": len(sound_data),
        })
        print("  Extracted {} -> {} ({} bytes)".format(sound_path, out_sound, len(sound_data)))
        print("    Declared SHA-256: {}".format(declared_sound_hash))
        print("    Computed SHA-256: {}".format(computed_sound_hash))
        mstr = "YES" if sound_ok else "NO"
        print("    Match: {}".format(mstr))

    phase_extract_end = datetime.now(timezone.utc)
    extract_duration = (phase_extract_end - phase_extract_start).total_seconds()
    print("  Extraction complete. Duration: {:.3f}s".format(extract_duration))

    # Phase 5: Node graph listing with meanings
    rpt()
    rpt("## Node Graph Listing")
    rpt()
    rpt("The manifest declares a node graph where each node represents content,")
    rpt("with edges describing relationships between them.")
    rpt()

    for node in manifest.get("nodes", []):
        nid = node["node_id"]
        ntype = node.get("type", "unknown")
        active_ver_num = node.get("active")
        part_id = node.get("part_id", "-")
        mat_id = node.get("material_id", "-")

        rpt("### Node: {}".format(nid))
        rpt("- **Type:** {}".format(ntype))
        rpt("- **Active version:** v{}".format(active_ver_num))
        if part_id != "-":
            rpt("- **Part ID:** {}".format(part_id))
        if mat_id != "-":
            rpt("- **Material ID:** {}".format(mat_id))

        for ver in node.get("versions", []):
            if ver.get("v") == active_ver_num:
                note_text = ver.get("note", "")
                epistemic = ver.get("epistemic", "-")
                producer_tool = ver.get("producer", {}).get("tool", "-")
                rpt("- **Epistemic status:** {}".format(epistemic))
                rpt("- **Producer tool:** {}".format(producer_tool))
                if note_text:
                    rpt("- **Note:** {}".format(note_text))

                files_list = ver.get("files", [])
                if files_list:
                    rpt("- **Files ({}):**".format(len(files_list)))
                    for finfo in files_list:
                        role = finfo.get("role", "payload")
                        fpath = finfo["path"]
                        fsize = finfo.get("size", "?")
                        fhash = finfo.get("sha256", "")
                        if len(fhash) > 16:
                            short_hash = fhash[:16] + "..."
                        else:
                            short_hash = fhash
                        line = "  - {} (role: {}, size: {} bytes, sha256: {})".format(
                            fpath, role, fsize, short_hash)
                        rpt(line)

                edges = node.get("edges", [])
                if edges:
                    rpt("- **Edges ({}):**".format(len(edges)))
                    for e in edges:
                        to_node = e["to"]
                        kind = e["kind"]
                        role = e["role"]
                        line = "  - {}({}) -> {}".format(kind, role, to_node)
                        rpt(line)
                break

        rpt()

    # Phase 6: Extracted files summary in report
    rpt()
    rpt("## Extracted Files")
    rpt()
    for ef in extracted_files:
        status = "MATCH" if ef["match"] else "MISMATCH"
        rpt("| File | ZIP Path | Declared SHA-256 | Computed SHA-256 | Status | Size |")
        rpt("|---|---|---|---|---|---|")
        line = "| {} | {} | {} | {} | {} | {} bytes |".format(
            ef["path"], ef["zip_path"], ef["declared_sha256"],
            ef["computed_sha256"], status, ef["size"])
        rpt(line)

    # Phase 7: Bundled reader programs analysis
    rpt()
    rpt("## Bundled Reader Programs")
    rpt()
    rpt("The package contains three bundled readers under loaders/:")
    rpt("- loaders/werk_read.py (Python, 42226 bytes)")
    rpt("- loaders/werk_read.rs (Rust, 98761 bytes)")
    rpt("- loaders/werk_read.c (C, 111051 bytes)")
    rpt()

    loader_python_path = "loaders/werk_read.py"
    try:
        with zipfile.ZipFile(werk_path, "r") as zf:
            loader_data = zf.read(loader_python_path)
        loader_text = loader_data.decode("utf-8", errors="replace")[:500]
        line1 = "**Did we open/run a bundled reader?** Yes - extracted {} to inspect.".format(loader_python_path)
        rpt(line1)
        line2 = "Our solution is self-contained and does not execute it."
        rpt(line2)
        rpt()
        rpt("First lines of loaders/werk_read.py:")
        rpt("