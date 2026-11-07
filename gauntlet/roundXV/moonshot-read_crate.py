#!/usr/bin/env python3
"""Standalone reader for crate-v1.werk.

Opens the .werk container (a zip file), parses MANIFEST.json, prints the node
graph with short meanings, verifies every sha256 declared in the manifest,
and extracts the primary mesh and primary sound to the current directory.

Only uses the Python standard library.  Does not run any loader bundled
inside the package.
"""

import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

ARCHIVE = Path("crate-v1.werk")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_file(member_name: str, data: bytes, declared_hash: str) -> bool:
    return sha256_bytes(data) == declared_hash


def main() -> int:
    start_time = __import__("time").time()

    if not ARCHIVE.is_file():
        print(f"ERROR: {ARCHIVE} not found", file=sys.stderr)
        return 1

    with zipfile.ZipFile(ARCHIVE, "r") as zf:
        # Sanity check: zip compression is expected to be "store" for payload.
        for info in zf.infolist():
            if info.compress_type != zipfile.ZIP_STORED:
                print(
                    f"WARNING: {info.filename} is not stored "
                    f"(compression={info.compress_type})",
                    file=sys.stderr,
                )

        # 1. Open and parse MANIFEST.json
        manifest_data = zf.read("MANIFEST.json")
        manifest = json.loads(manifest_data)

        # 2. List node graph with meanings
        print("=" * 70)
        print(f"Archive: {ARCHIVE} ({os.path.getsize(ARCHIVE)} bytes)")
        print(f"Format:  werk {manifest['werk']['major']}.{manifest['werk']['minor']}")
        print(f"Profile: {manifest['profile']}")
        print(f"Entity:  {manifest['entity']['uuid']} - {manifest['entity']['name']}")
        print(f"Primary mesh:  {manifest['primary']['mesh']}")
        print(f"Primary sound: {manifest['primary']['sound']}")
        print("=" * 70)
        print()

        nodes = manifest.get("nodes", [])
        print(f"NODE GRAPH ({len(nodes)} nodes)")
        print("-" * 70)

        # Build node lookup
        node_by_id = {}
        for node in nodes:
            node_by_id[node["node_id"]] = node
            active_version = None
            for v in node.get("versions", []):
                if v.get("v") == node.get("active"):
                    active_version = v
                    break
            # Fallback: use the first version if active not matched.
            if active_version is None and node.get("versions"):
                active_version = node["versions"][0]

            files_summary = []
            if active_version:
                for f in active_version.get("files", []):
                    files_summary.append(f"{f.get('path')} ({f.get('size')} bytes)")

            edges = node.get("edges", [])
            edge_str = ", ".join(
                f"{e.get('kind')}->{e.get('to')} ({e.get('role')})" for e in edges
            ) or "none"

            print(f"  node_id : {node['node_id']}")
            print(f"  type    : {node['type']}")
            if active_version and active_version.get("note"):
                print(f"  meaning : {active_version['note']}")
            print(f"  files   : {len(active_version.get('files', [])) if active_version else 0}")
            for fs in files_summary:
                print(f"            - {fs}")
            print(f"  edges   : {edge_str}")
            print()

        # 3. Verify every declared hash
        print("=" * 70)
        print("INTEGRITY CHECK (sha256)")
        print("-" * 70)

        failures = []
        checked_files = []

        for node in nodes:
            active_version = None
            for v in node.get("versions", []):
                if v.get("v") == node.get("active"):
                    active_version = v
                    break
            if active_version is None and node.get("versions"):
                active_version = node["versions"][0]
            if active_version is None:
                continue

            for fdecl in active_version.get("files", []):
                path = fdecl["path"]
                declared = fdecl.get("sha256")
                declared_size = fdecl.get("size")

                try:
                    data = zf.read(path)
                except KeyError:
                    failures.append((node["node_id"], path, "missing from archive"))
                    checked_files.append(
                        {
                            "node_id": node["node_id"],
                            "path": path,
                            "declared": declared,
                            "computed": None,
                            "ok": False,
                            "reason": "missing from archive",
                        }
                    )
                    continue

                actual_size = len(data)
                size_ok = declared_size is None or actual_size == declared_size
                computed = sha256_bytes(data)
                hash_ok = declared is not None and computed == declared

                status = "OK" if (hash_ok and size_ok) else "FAIL"
                if not (hash_ok and size_ok):
                    reasons = []
                    if not hash_ok:
                        reasons.append("hash mismatch")
                    if not size_ok:
                        reasons.append(
                            f"size mismatch (declared {declared_size}, got {actual_size})"
                        )
                    failures.append((node["node_id"], path, "; ".join(reasons)))

                checked_files.append(
                    {
                        "node_id": node["node_id"],
                        "path": path,
                        "declared": declared,
                        "computed": computed,
                        "size_declared": declared_size,
                        "size_actual": actual_size,
                        "ok": hash_ok and size_ok,
                    }
                )
                print(f"  [{status}] {node['node_id']:40s} {path}")

        # 4. Extract primary mesh and primary sound
        print()
        print("=" * 70)
        print("EXTRACTION")
        print("-" * 70)

        primary = manifest.get("primary", {})
        primary_mesh_id = primary.get("mesh")
        primary_sound_id = primary.get("sound")

        extracted = []

        def extract_primary_file(node_id: str, role: str, default_path: str | None = None):
            node = node_by_id.get(node_id)
            if node is None:
                return None
            active_version = None
            for v in node.get("versions", []):
                if v.get("v") == node.get("active"):
                    active_version = v
                    break
            if active_version is None and node.get("versions"):
                active_version = node["versions"][0]
            if active_version is None:
                return None

            target_file = None
            for fdecl in active_version.get("files", []):
                if fdecl.get("role") == role:
                    target_file = fdecl
                    break
            if target_file is None and default_path:
                for fdecl in active_version.get("files", []):
                    if fdecl["path"] == default_path:
                        target_file = fdecl
                        break
            if target_file is None:
                # Last resort: pick the first non-descriptor file.
                for fdecl in active_version.get("files", []):
                    if fdecl.get("role") != "descriptor":
                        target_file = fdecl
                        break
            if target_file is None:
                return None

            src_path = target_file["path"]
            data = zf.read(src_path)
            out_name = Path(src_path).name
            out_path = Path(out_name)
            with open(out_path, "wb") as out:
                out.write(data)
            return {
                "node_id": node_id,
                "role": role,
                "src_path": src_path,
                "out_path": str(out_path),
                "declared_sha256": target_file.get("sha256"),
                "computed_sha256": sha256_bytes(data),
                "size": len(data),
            }

        mesh_info = extract_primary_file(primary_mesh_id, role=None)
        if mesh_info is None:
            print(f"ERROR: could not locate primary mesh node '{primary_mesh_id}'", file=sys.stderr)
            failures.append(("primary", primary_mesh_id, "not found"))
        else:
            print(
                f"  Extracted mesh: {mesh_info['src_path']} -> {mesh_info['out_path']} "
                f"({mesh_info['size']} bytes)"
            )
            extracted.append(mesh_info)

        sound_info = extract_primary_file(primary_sound_id, role="best")
        if sound_info is None:
            print(f"ERROR: could not locate primary sound node '{primary_sound_id}'", file=sys.stderr)
            failures.append(("primary", primary_sound_id, "not found"))
        else:
            print(
                f"  Extracted sound: {sound_info['src_path']} -> {sound_info['out_path']} "
                f"({sound_info['size']} bytes)"
            )
            extracted.append(sound_info)

    # 5. Summary
    elapsed = __import__("time").time() - start_time
    print()
    print("=" * 70)
    print("SUMMARY")
    print("-" * 70)
    print(f"Files checked: {len(checked_files)}")
    print(f"Files OK:      {sum(1 for f in checked_files if f.get('ok'))}")
    print(f"Files FAIL:    {sum(1 for f in checked_files if not f.get('ok'))}")
    if failures:
        print("Failures:")
        for node_id, path, reason in failures:
            print(f"  - {node_id} / {path}: {reason}")
    else:
        print("All declared hashes verified successfully.")
    print(f"Extracted {len(extracted)} primary asset(s).")
    for item in extracted:
        print(
            f"  {item['out_path']}: declared={item['declared_sha256']} "
            f"computed={item['computed_sha256']}"
        )
    print(f"Wall time: {elapsed:.3f}s")

    # Return non-zero if anything failed.
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())
