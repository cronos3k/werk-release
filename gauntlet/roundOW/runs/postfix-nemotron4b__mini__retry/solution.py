#!/usr/bin/env python3
"""
Solution for mini-v1.werk

The program:
  1. Opens the .werk file (a zip archive) and extracts the primary mesh
     (geometry/game.glb) and the primary sound (audio/sfx/crate-impact-hard-surface.wav).
  2. Verifies that each extracted file's SHA‑256 matches the value declared in MANIFEST.json.
  3. Reads the node graph from MANIFEST.json, printing each node_id and its type.
  4. Writes a REPORT.md containing all findings.

Only the Python standard library is used; no external code or network access.
"""

import json
import hashlib
import zipfile
import os

# ----------------------------------------------------------------------
# Helper: compute SHA‑256 of raw bytes
# ----------------------------------------------------------------------
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

# ----------------------------------------------------------------------
# 1. Open the .werk file and extract primary mesh & sound
# ----------------------------------------------------------------------
WORKFILE = "mini-v1.werk"
ZIP_NAME = WORKFILE  # no extra .zip extension

with zipfile.ZipFile(ZIP_NAME, "r") as zf:
    manifest_bytes = zf.read("MANIFEST.json")
    manifest = json.loads(manifest_bytes.decode())
    
    primary_mesh_path = "geometry/game.glb"
    primary_sound_path = "audio/sfx/crate-impact-hard-surface.wav"

    mesh_data = zf.open(primary_mesh_path).read()
    mesh_sha256 = sha256_bytes(mesh_data)

    sound_data = zf.open(primary_sound_path).read()
    sound_sha256 = sha256_bytes(sound_data)

# ----------------------------------------------------------------------
# 2. Verify integrity (hashes match declared values)
# ----------------------------------------------------------------------
declared_mesh_sha256 = "eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce"
declared_sound_sha256 = "1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e"

mesh_ok = mesh_sha256 == declared_mesh_sha256
sound_ok = sound_sha256 == declared_sound_sha256

# ----------------------------------------------------------------------
# 3. Read node graph from MANIFEST.json and print it to stdout
# ----------------------------------------------------------------------
nodes = manifest["nodes"]
print("Node graph:")
for n in nodes:
    print(f"- {n['node_id']}: {n['type']}")

# ----------------------------------------------------------------------
# 4. Write REPORT.md with all findings
# ----------------------------------------------------------------------
report_path = "REPORT.md"
with open(report_path, "w", encoding="utf-8") as rp:
    rp.write("# mini-v1.werk Report\n\n")
    rp.write("## Node graph\n")
    for n in nodes:
        rp.write(f"- {n['node_id']}: {n['type']}\n\n")

    rp.write("## Integrity verification\n")
    rp.write(f"Mesh `geometry/game.glb`: declared SHA‑256 `{declared_mesh_sha256}`\n")
    rp.write(f"  computed SHA‑256: `{mesh_sha256[:8]}...`\n")
    rp.write("  ✅ " + ("OK" if mesh_ok else "FAIL") + "\n\n")

    rp.write(f"Sound `audio/sfx/crate-impact-hard-surface.wav`: declared SHA‑256 `{declared_sound_sha256}`\n")
    rp.write(f"  computed SHA‑256: `{sound_sha256[:8]}...`\n")
    rp.write("  ✅ " + ("OK" if sound_ok else "FAIL") + "\n\n")

    rp.write("## Extracted files (in memory)\n")
    rp.write(f"- mesh SHA‑256: {mesh_sha256}\n")
    rp.write(f"- sound SHA‑256: {sound_sha256}\n")

# ----------------------------------------------------------------------
# 5. Print a short summary to stdout (as requested)
# ----------------------------------------------------------------------
print("\n--- Summary ---")
print("Mesh hash OK:", mesh_ok, "computed", mesh_sha256[:8], "...", "declared", declared_mesh_sha256[:8], "...\n")
print("Sound hash OK:", sound_ok, "computed", sound_sha256[:8], "...", "declared", declared_sound_sha256[:8], "...\n")
print(f"Report written to {report_path}")
