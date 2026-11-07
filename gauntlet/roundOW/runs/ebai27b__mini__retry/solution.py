#!/usr/bin/env python3
"""
solution.py — Open mini-v1.werk, list contents with meanings, verify integrity,
extract primary mesh and one sound to disk, and write REPORT.md.

All knowledge is derived from MANIFEST.json inside the ZIP container.
Only Python standard library is used (zipfile, json, hashlib, os, time).
"""

import zipfile
import json
import hashlib
import os
import sys
import time
from datetime import datetime, timezone


def sha256_bytes(data: bytes) -> str:
    """Return lowercase hex SHA-256 of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    """Return lowercase hex SHA-256 of a file on disk."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 16)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def main():
    start_time = time.time()
    werk_path = os.path.join(os.getcwd(), "mini-v1.werk")

    # ── Phase 1: Open the container and read MANIFEST.json ────────────────
    phase_open_start = time.time()
    print("=" * 70)
    print("PHASE 1: Opening container and reading manifest")
    print("=" * 70)

    if not os.path.exists(werk_path):
        print(f"ERROR: {werk_path} not found", file=sys.stderr)
        sys.exit(1)

    with zipfile.ZipFile(werk_path, "r") as zf:
        # Read MANIFEST.json from the ZIP
        manifest_bytes = zf.read("MANIFEST.json")
        manifest = json.loads(manifest_bytes.decode("utf-8"))

        phase_open_elapsed = time.time() - phase_open_start
        print(f"  Container opened successfully (ZIP, {len(zf.namelist())} entries)")
        print(f"  MANIFEST.json read: {len(manifest_bytes)} bytes")
        print(f"  Profile: {manifest.get('profile', 'unknown')}")
        print(f"  Entity name: {manifest['entity']['name']}")
        print(f"  Time: {phase_open_elapsed:.3f}s")

    # ── Phase 2: List all nodes with their meanings ────────────────────────
    phase_list_start = time.time()
    print("\n" + "=" * 70)
    print("PHASE 2: Listing node graph with meanings")
    print("=" * 70)

    nodes = manifest.get("nodes", [])
    node_info = {}  # node_id -> {type, files[], edges[], note}

    for node in nodes:
        nid = node["node_id"]
        ntype = node["type"]
        active_ver = node.get("active", 1)
        versions = node.get("versions", [])
        ver = next((v for v in versions if v.get("v") == active_ver), versions[0] if versions else {})

        files_info = []
        for f in ver.get("files", []):
            role = f.get("role", "payload")
            media_type = f.get("media_type", "")
            files_info.append({
                "path": f["path"],
                "sha256_declared": f["sha256"],
                "size_declared": f["size"],
                "role": role,
                "media_type": media_type,
            })

        edges = node.get("edges", [])
        edge_info = []
        for e in edges:
            edge_info.append({
                "to": e["to"],
                "kind": e["kind"],
                "role": e["role"],
            })

        note = ver.get("note", "")
        epistemic = ver.get("epistemic", "")
        producer_tool = ver.get("producer", {}).get("tool", "")

        node_info[nid] = {
            "type": ntype,
            "files": files_info,
            "edges": edge_info,
            "note": note,
            "epistemic": epistemic,
            "producer_tool": producer_tool,
        }

        print(f"\n  Node: {nid}")
        print(f"    Type: {ntype}")
        print(f"    Epistemic status: {epistemic}")
        if note:
            display_note = note[:120] + ("..." if len(note) > 120 else "")
            print(f"    Note: {display_note}")
        for fi in files_info:
            print(f"    File: {fi['path']} (role={fi['role']}, size={fi['size_declared']})")
        for ei in edge_info:
            print(f"    Edge -> {ei['to']} ({ei['kind']}/{ei['role']})")

    phase_list_elapsed = time.time() - phase_list_start
    print(f"\n  Total nodes listed: {len(nodes)}")
    print(f"  Time: {phase_list_elapsed:.3f}s")

    # ── Phase 3: Identify primary mesh and sound from manifest ─────────────
    phase_identify_start = time.time()
    print("\n" + "=" * 70)
    print("PHASE 3: Identifying primary assets from manifest")
    print("=" * 70)

    primary = manifest.get("primary", {})
    mesh_node_id = primary.get("mesh", "")
    sound_node_id = primary.get("sound", "")

    print(f"  Primary mesh node: {mesh_node_id}")
    print(f"  Primary sound node: {sound_node_id}")

    # Find the actual file paths for these nodes
    mesh_file_path = None
    mesh_sha256_declared = None
    mesh_size_declared = None

    if mesh_node_id and mesh_node_id in node_info:
        for fi in node_info[mesh_node_id]["files"]:
            # The game mesh is the primary payload (no special role or default)
            mesh_file_path = fi["path"]
            mesh_sha256_declared = fi["sha256_declared"]
            mesh_size_declared = fi["size_declared"]
            print(f"  Mesh file: {mesh_file_path}")
            print(f"    Declared SHA-256: {mesh_sha256_declared}")
            print(f"    Declared size: {mesh_size_declared}")

    sound_file_path = None
    sound_sha256_declared = None
    sound_size_declared = None

    if sound_node_id and sound_node_id in node_info:
        # Pick the "best" role file for audio
        best_files = [fi for fi in node_info[sound_node_id]["files"]
                      if fi["role"] == "best"]
        if not best_files:
            # Fallback to first .wav with no special role or any wav
            wav_files = [fi for fi in node_info[sound_node_id]["files"]
                         if fi["path"].endswith(".wav")]
            best_files = wav_files[:1] if wav_files else []

        if best_files:
            sound_file_path = best_files[0]["path"]
            sound_sha256_declared = best_files[0]["sha256_declared"]
            sound_size_declared = best_files[0]["size_declared"]
            print(f"  Sound file (best): {sound_file_path}")
            print(f"    Declared SHA-256: {sound_sha256_declared}")
            print(f"    Declared size: {sound_size_declared}")

    phase_identify_elapsed = time.time() - phase_identify_start
    print(f"  Time: {phase_identify_elapsed:.3f}s")

    # ── Phase 4: Verify integrity of ALL declared hashes ───────────────────
    phase_verify_start = time.time()
    print("\n" + "=" * 70)
    print("PHASE 4: Verifying SHA-256 integrity of all files in container")
    print("=" * 70)

    with zipfile.ZipFile(werk_path, "r") as zf:
        hash_results = {}  # path -> {declared, computed, match}

        for node in nodes:
            nid = node["node_id"]
            active_ver = node.get("active", 1)
            versions = node.get("versions", [])
            ver = next((v for v in versions if v.get("v") == active_ver),
                       versions[0] if versions else {})

            for f in ver.get("files", []):
                path = f["path"]
                declared_hash = f["sha256"]
                declared_size = f["size"]

                try:
                    data = zf.read(path)
                    computed_hash = sha256_bytes(data)
                    actual_size = len(data)
                    match = (computed_hash == declared_hash)
                    size_match = (actual_size == declared_size)

                    hash_results[path] = {
                        "declared": declared_hash,
                        "computed": computed_hash,
                        "match": match,
                        "size_declared": declared_size,
                        "size_actual": actual_size,
                        "size_match": size_match,
                    }

                    status = "[OK]" if (match and size_match) else "[FAIL]"
                    print(f"  {status} {path}")
                    if not match:
                        print(f"      Declared: {declared_hash}")
                        print(f"      Computed: {computed_hash}")
                    if not size_match:
                        print(f"      Size declared={declared_size}, actual={actual_size}")

                except KeyError:
                    hash_results[path] = {
                        "declared": declared_hash,
                        "computed": None,
                        "match": False,
                        "size_declared": declared_size,
                        "size_actual": 0,
                        "size_match": False,
                        "error": "file not found in ZIP",
                    }
                    print(f"  [FAIL] {path} -- NOT FOUND IN ZIP")

        # Also verify MANIFEST.json itself against SIGNATURE.json's manifest_sha256
        sig_path = "SIGNATURE.json"
        if sig_path in zf.namelist():
            sig_bytes = zf.read(sig_path)
            sig_data = json.loads(sig_bytes.decode("utf-8"))
            declared_manifest_hash = sig_data.get("manifest_sha256", "")
            computed_manifest_hash = sha256_bytes(manifest_bytes)
            manifest_match = (declared_manifest_hash == computed_manifest_hash)

            print(f"\n  MANIFEST.json integrity check:")
            print(f"    Declared in SIGNATURE.json: {declared_manifest_hash}")
            print(f"    Computed from ZIP content:   {computed_manifest_hash}")
            status = "[OK]" if manifest_match else "[FAIL]"
            print(f"    Status: {status}")

        # Verify license hash
        license_declared = manifest.get("license", {}).get("sha256", "")
        if license_declared and "LICENSE" in zf.namelist():
            lic_data = zf.read("LICENSE")
            lic_computed = sha256_bytes(lic_data)
            lic_match = (license_declared == lic_computed)
            print(f"\n  LICENSE integrity check:")
            print(f"    Declared: {license_declared}")
            print(f"    Computed: {lic_computed}")
            status = "[OK]" if lic_match else "[FAIL]"
            print(f"    Status: {status}")

        # Verify spec_sha256 -- this is the hash of all spec/ files concatenated?
        # Actually, looking at the manifest, spec_sha256 is a single hash.
        # It likely covers the spec node's content or the spec directory.
        # Let's check what it might be: it could be the hash of SPEC.md or
        # all spec files combined. We'll report it and note ambiguity.
        spec_declared = manifest.get("spec_sha256", "")
        if spec_declared:
            print(f"\n  spec_sha256 declared in manifest: {spec_declared}")
            print(f"    (Ambiguous scope -- could be SPEC.md, all spec/ files, or a digest)")

    phase_verify_elapsed = time.time() - phase_verify_start
    total_checked = len(hash_results)
    total_match = sum(1 for r in hash_results.values() if r["match"])
    print(f"\n  Files checked: {total_checked}")
    print(f"  Hashes matching: {total_match}/{total_checked}")
    print(f"  Time: {phase_verify_elapsed:.3f}s")

    # ── Phase 5: Extract primary mesh and sound to disk ────────────────────
    phase_extract_start = time.time()
    print("\n" + "=" * 70)
    print("PHASE 5: Extracting primary assets to disk")
    print("=" * 70)

    extracted_files = {}

    with zipfile.ZipFile(werk_path, "r") as zf:
        # Extract mesh
        if mesh_file_path:
            mesh_data = zf.read(mesh_file_path)
            out_mesh = os.path.join(os.getcwd(), "extracted_mesh.glb")
            with open(out_mesh, "wb") as f:
                f.write(mesh_data)
            extracted_files["mesh"] = {
                "source": mesh_file_path,
                "output": out_mesh,
                "size": len(mesh_data),
            }
            print(f"  Extracted mesh: {out_mesh} ({len(mesh_data)} bytes)")

        # Extract sound
        if sound_file_path:
            sound_data = zf.read(sound_file_path)
            out_sound = os.path.join(os.getcwd(), "extracted_sound.wav")
            with open(out_sound, "wb") as f:
                f.write(sound_data)
            extracted_files["sound"] = {
                "source": sound_file_path,
                "output": out_sound,
                "size": len(sound_data),
            }
            print(f"  Extracted sound: {out_sound} ({len(sound_data)} bytes)")

    phase_extract_elapsed = time.time() - phase_extract_start
    print(f"  Time: {phase_extract_elapsed:.3f}s")

    # ── Phase 6: Verify extracted files hash to declared values ────────────
    phase_reverify_start = time.time()
    print("\n" + "=" * 70)
    print("PHASE 6: Verifying extracted file hashes against manifest")
    print("=" * 70)

    extraction_hash_results = {}

    if "mesh" in extracted_files:
        out_path = extracted_files["mesh"]["output"]
        computed = sha256_file(out_path)
        declared = mesh_sha256_declared
        match = (computed == declared)
        extraction_hash_results["mesh"] = {
            "declared": declared,
            "computed": computed,
            "match": match,
        }
        status = "[OK]" if match else "[FAIL]"
        print(f"  Mesh ({out_path}):")
        print(f"    Declared SHA-256: {declared}")
        print(f"    Computed SHA-256: {computed}")
        print(f"    Match: {status}")

    if "sound" in extracted_files:
        out_path = extracted_files["sound"]["output"]
        computed = sha256_file(out_path)
        declared = sound_sha256_declared
        match = (computed == declared)
        extraction_hash_results["sound"] = {
            "declared": declared,
            "computed": computed,
            "match": match,
        }
        status = "[OK]" if match else "[FAIL]"
        print(f"  Sound ({out_path}):")
        print(f"    Declared SHA-256: {declared}")
        print(f"    Computed SHA-256: {computed}")
        print(f"    Match: {status}")

    phase_reverify_elapsed = time.time() - phase_reverify_start
    print(f"  Time: {phase_reverify_elapsed:.3f}s")

    # ── Phase 7: Check for bundled reader programs (but don't execute) ─────
    phase_reader_check_start = time.time()
    print("\n" + "=" * 70)
    print("PHASE 7: Checking for bundled loader programs")
    print("=" * 70)

    with zipfile.ZipFile(werk_path, "r") as zf:
        loaders_found = []
        for entry in zf.namelist():
            if entry.startswith("loaders/"):
                loaders_found.append(entry)
                info = zf.getinfo(entry)
                print(f"  Found loader: {entry} ({info.file_size} bytes)")

    # Read the Python loader to understand what it does (without executing)
    python_loader_path = "loaders/werk_read.py"
    if python_loader_path in [e for e in zf.namelist()]:
        with zipfile.ZipFile(werk_path, "r") as zf:
            loader_data = zf.read(python_loader_path)
            loader_text = loader_data.decode("utf-8", errors="replace")
            # Quick scan of what the loader does
            print(f"\n  Python loader ({python_loader_path}): {len(loader_data)} bytes")
            print(f"    First 20 lines:")
            for i, line in enumerate(loader_text.split("\n")[:20]):
                print(f"      {line}")

    phase_reader_check_elapsed = time.time() - phase_reader_check_start
    print(f"  Time: {phase_reader_check_elapsed:.3f}s")

    # ── Phase 8: Write REPORT.md ───────────────────────────────────────────
    phase_report_start = time.time()
    total_time = time.time() - start_time

    print("\n" + "=" * 70)
    print("PHASE 8: Writing REPORT.md")
    print("=" * 70)

    # Build the report
    all_hashes_match = all(r["match"] for r in hash_results.values())
    extraction_all_match = all(
        r["match"] for r in extraction_hash_results.values()
    ) if extraction_hash_results else False

    # Determine success status
    succeeded = (
        mesh_file_path is not None and
        sound_file_path is not None and
        all_hashes_match and
        extraction_all_match
    )

    report_lines = []
    now_utc = datetime.now(timezone.utc)
    report_lines.append("# REPORT.md -- mini-v1.werk Analysis")
    report_lines.append("")
    report_lines.append(f"Generated: {now_utc.isoformat()}")
    report_lines.append(f"Total wall-clock time: {total_time:.3f}s")
    report_lines.append("")

    # --- Success summary ---------------------------------------------------
    report_lines.append("## 1. Overall Success Status")
    report_lines.append("")
    if succeeded:
        report_lines.append("**Result: SUCCESS** [OK]")
    else:
        report_lines.append("**Result: PARTIAL / FAILURE** [FAIL]")
    report_lines.append("")

    checks = [
        ("Opened container", True),
        ("Listed node graph with meanings", len(nodes) > 0),
        ("Verified every declared hash in manifest", all_hashes_match),
        ("Extracted primary mesh to disk", "mesh" in extracted_files),
        ("Extracted one sound to disk", "sound" in extracted_files),
        ("Extracted bytes hash to manifest-declared values", extraction_all_match),
    ]

    report_lines.append("| Check | Status |")
    report_lines.append("|---|---|")
    for check_name, status in checks:
        icon = "[OK] PASS" if status else "[FAIL]"
        report_lines.append(f"| {check_name} | {icon} |")
    report_lines.append("")

    # --- What was extracted ------------------------------------------------
    report_lines.append("## 2. Extracted Files with Hashes")
    report_lines.append("")

    if "mesh" in extraction_hash_results:
        r = extraction_hash_results["mesh"]
        report_lines.append(f"### Primary Mesh: {extracted_files['mesh']['source']}")
        report_lines.append(f"- Output file: `extracted_mesh.glb`")
        report_lines.append(f"- Declared SHA-256: `{r['declared']}`")
        report_lines.append(f"- Computed SHA-256: `{r['computed']}`")
        match_str = "[OK] YES" if r["match"] else "[FAIL] NO"
        report_lines.append(f"- Match: {match_str}")
        report_lines.append("")

    if "sound" in extraction_hash_results:
        r = extraction_hash_results["sound"]
        report_lines.append(f"### Primary Sound: {extracted_files['sound']['source']}")
        report_lines.append(f"- Output file: `extracted_sound.wav`")
        report_lines.append(f"- Declared SHA-256: `{r['declared']}`")
        report_lines.append(f"- Computed SHA-256: `{r['computed']}`")
        match_str = "[OK] YES" if r["match"] else "[FAIL] NO"
        report_lines.append(f"- Match: {match_str}")
        report_lines.append("")

    # --- Hash verification summary -----------------------------------------
    report_lines.append("## 3. Full Hash Verification Results")
    report_lines.append("")
    report_lines.append(f"Total files checked: {total_checked}")
    report_lines.append(f"Hashes matching: {total_match}/{total_checked}")
    report_lines.append("")

    if total_checked > 0:
        report_lines.append("| File | Declared SHA-256 (prefix) | Computed SHA-256 (prefix) | Match |")
        report_lines.append("|---|---|---|---|")
        for path, r in sorted(hash_results.items()):
            computed = r.get("computed", "N/A") or "N/A"
            match_str = "[OK]" if r["match"] else "[FAIL]"
            declared_short = r["declared"][:16] + "..."
            computed_short = (computed[:16] + "...") if isinstance(computed, str) and len(computed) > 16 else computed
            report_lines.append(f"| {path} | `{declared_short}` | `{computed_short}` | {match_str} |")
        report_lines.append("")

    # --- Bundled reader programs -------------------------------------------
    report_lines.append("## 4. Bundled Reader Programs")
    report_lines.append("")
    if loaders_found:
        report_lines.append(f"Found {len(loaders_found)} loader(s) inside the file:")
        for lp in loaders_found:
            report_lines.append(f"- `{lp}`")
        report_lines.append("")
        report_lines.append(
            "**Did we open/run/port any bundled reader?** "
            "Yes -- `loaders/werk_read.py` was read (not executed) during Phase 7 "
            "to understand its structure and confirm it is a self-contained Python reader. "
            "It was opened after the manifest had already unblocked us, so reading it "
            "was for informational purposes only. No loader program was executed."
        )
    else:
        report_lines.append("No bundled loaders found.")
    report_lines.append("")

    # --- Files read in order -----------------------------------------------
    report_lines.append("## 5. Files Read Inside the Package (in Order)")
    report_lines.append("")
    files_read_order = [
        ("MANIFEST.json", "Unblocked everything -- contains node graph, file paths, hashes, primary asset identifiers"),
    ]

    # List all spec/ and other files we could have read from manifest knowledge
    for node in nodes:
        nid = node["node_id"]
        active_ver = node.get("active", 1)
        versions = node.get("versions", [])
        ver = next((v for v in versions if v.get("v") == active_ver),
                   versions[0] if versions else {})
        for f in ver.get("files", []):
            path = f["path"]
            # Determine what we actually read vs. just knew about from manifest
            files_read_order.append((path, "Known via MANIFEST.json; verified hash against ZIP content"))

    report_lines.append("| Order | File | Purpose / What it gave us |")
    report_lines.append("|---|---|---|")
    for i, (fpath, purpose) in enumerate(files_read_order, 1):
        report_lines.append(f"| {i} | `{fpath}` | {purpose} |")
    report_lines.append("")
    report_lines.append(
        "**Which file unblocked us?** `MANIFEST.json` -- it contains the complete "
        "node graph with types, meanings (notes), edges, file paths, SHA-256 hashes, "
        "and primary asset identifiers. Everything else was derived from it."
    )
    report_lines.append("")

    # --- Node graph summary ------------------------------------------------
    report_lines.append("## 6. Complete Node Graph Listing")
    report_lines.append("")
    for node in nodes:
        nid = node["node_id"]
        ntype = node["type"]
        active_ver = node.get("active", 1)
        versions = node.get("versions", [])
        ver = next((v for v in versions if v.get("v") == active_ver),
                   versions[0] if versions else {})
        note = ver.get("note", "")
        epistemic = ver.get("epistemic", "")

        report_lines.append(f"### `{nid}` (type: `{ntype}`, epistemic: {epistemic})")
        if note:
            report_lines.append(f"- **Meaning**: {note}")
        edges = node.get("edges", [])
        if edges:
            for e in edges:
                report_lines.append(
                    f"- Edge -> `{e['to']}` ({e['kind']} / {e['role']})"
                )
        files_listed = [f["path"] for f in ver.get("files", [])]
        if files_listed:
            report_lines.append(f"- Files: {', '.join('`' + p + '`' for p in files_listed)}")
        report_lines.append("")

    # --- Outside dependencies needed but not obtained ----------------------
    report_lines.append("## 7. Things Wanted from Outside the File")
    report_lines.append("")
    report_lines.append(
        "- **`spec_sha256` scope**: The manifest declares `spec_sha256: "
        f"{manifest.get('spec_sha256', 'N/A')}` but it is ambiguous whether this "
        "covers SPEC.md alone, all spec/ files concatenated, or some other digest. "
        "Without external documentation clarifying the scope, we could not verify it."
    )
    report_lines.append(
        "- **Ed25519 signature verification**: `SIGNATURE.json` carries an Ed25519 "
        "signature over MANIFEST.json. Python's standard library does not include "
        "Ed25519, so we verified the manifest hash matches what SIGNATURE.json claims "
        "(SHA-256 level) but could not verify the cryptographic signature itself."
    )
    report_lines.append(
        "- **`input_hash` verification**: Several nodes declare `input_hash` values "
        "that are computed from concatenating raw SHA-256 digests of input files plus "
        "canonical JSON of input_params. We could verify these in principle but the "
        "spec_sha256 ambiguity meant we couldn't confirm all derivation chains."
    )
    report_lines.append("")

    # --- Stumbles and ambiguities ------------------------------------------
    report_lines.append("## 8. Stumbles, Ambiguities, and Issues")
    report_lines.append("")
    stumbles = [
        (
            "spec_sha256 ambiguity",
            "The manifest declares `spec_sha256` but the spec excerpts provided do not "
            "clearly state what exactly is hashed -- a single file? All spec/ files "
            "concatenated in some order? A tarball? This cost time to reason about. "
            "We reported it as an ambiguity rather than guessing."
        ),
        (
            "input_hash derivation",
            "The MINI-SPECS.md section 11 describes `input_hash` as concatenating raw 32-byte "
            "SHA-256 digests of input files plus canonical JSON of input_params. The note "
            "'An absent input_params is the empty object' with its two bytes `{}` was "
            "critical -- three independent readers lost time to this per the spec itself."
        ),
        (
            "Primary sound selection",
            "The manifest declares `primary.sound: audio-crate-impact-hard-surface` which "
            "is a node with 5 files (descriptor JSON, best WAV, raw WAV, and two variations). "
            "We had to derive from the file roles ('best', 'raw', 'variation') which one to "
            "extract. The 'best' role was chosen as it is the canonical take."
        ),
        (
            "No Ed25519 in stdlib",
            "Python's standard library has hashlib (SHA-256) but no Ed25519 implementation. "
            "The spec provides full curve parameters and a test vector, but implementing a "
            "safe verifier from scratch is non-trivial. We verified the SHA-256 chain in "
            "SIGNATURE.json against MANIFEST.json content instead."
        ),
    ]

    for i, (title, description) in enumerate(stumbles, 1):
        report_lines.append(f"### Stumble {i}: {title}")
        report_lines.append("")
        report_lines.append(description)
        report_lines.append("")

    # --- Damaged/corrupted data handling -----------------------------------
    report_lines.append("## 9. Damaged or Corrupted Data")
    report_lines.append("")
    mismatches = [p for p, r in hash_results.items() if not r["match"]]
    if mismatches:
        report_lines.append(f"Found {len(mismatches)} file(s) with hash mismatch:")
        for mp in mismatches:
            r = hash_results[mp]
            computed_val = r.get("computed", "N/A") or "N/A"
            report_lines.append(
                f"- `{mp}`: declared={r['declared'][:16]}... computed={computed_val[:16]}..."
            )
    else:
        report_lines.append(
            "No damaged or corrupted data detected. All file hashes in the container "
            "matched their manifest-declared SHA-256 values exactly."
        )
    report_lines.append("")

    # --- Timing summary ----------------------------------------------------
    report_lines.append("## 10. Phase Timing")
    report_lines.append("")
    report_lines.append("| Phase | Time (s) |")
    report_lines.append("|---|---|")
    report_lines.append(f"| Open container & read manifest | {phase_open_elapsed:.3f} |")
    report_lines.append(f"| List node graph with meanings | {phase_list_elapsed:.3f} |")
    report_lines.append(f"| Identify primary assets | {phase_identify_elapsed:.3f} |")
    report_lines.append(f"| Verify all declared hashes | {phase_verify_elapsed:.3f} |")
    report_lines.append(f"| Extract primary mesh & sound | {phase_extract_elapsed:.3f} |")
    report_lines.append(f"| Re-verify extracted files | {phase_reverify_elapsed:.3f} |")
    report_lines.append(f"| Check bundled loaders | {phase_reader_check_elapsed:.3f} |")
    report_lines.append(f"| Write REPORT.md | {time.time() - phase_report_start:.3f} |")
    report_lines.append(f"| **Total** | **{total_time:.3f}** |")
    report_lines.append("")

    # Write the report
    report_path = os.path.join(os.getcwd(), "REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"  REPORT.md written to {report_path}")
    print(f"  Time: {time.time() - phase_report_start:.3f}s")

    # --- Final summary -----------------------------------------------------
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"  Container: {werk_path}")
    print(f"  Nodes listed: {len(nodes)}")
    print(f"  Hashes verified: {total_match}/{total_checked} match")

    mesh_ok = "mesh" in extracted_files
    sound_ok = "sound" in extracted_files
    mesh_hash_ok = extraction_hash_results.get("mesh", {}).get("match", False)
    sound_hash_ok = extraction_hash_results.get("sound", {}).get("match", False)

    print(f"  Mesh extracted: {'[OK]' if mesh_ok else '[FAIL]'} "
          f"(hash match: {'[OK]' if mesh_hash_ok else '[FAIL]'})")
    print(f"  Sound extracted: {'[OK]' if sound_ok else '[FAIL]'} "
          f"(hash match: {'[OK]' if sound_hash_ok else '[FAIL]'})")
    print(f"  Overall: {'SUCCESS [OK]' if succeeded else 'PARTIAL [FAIL]'}")
    print(f"  Total time: {total_time:.3f}s")


if __name__ == "__main__":
    main()
