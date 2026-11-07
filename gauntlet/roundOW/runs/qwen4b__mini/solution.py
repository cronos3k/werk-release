import hashlib
import struct
import os
from pathlib import Path


def read_zip_file(file_path: str) -> bytes:
    """
    Read a zip file from end to start, finding the EOCD.
    
    The EOCD is at offset = filesize - 22 (or max(0, filesize-22-65535)).
    We need to read min(filesize, 65535+22) bytes from the end.
    """
    with open(file_path, "rb") as f:
        file_size = os.fstat(f.fileno()).st_size
        bytes_to_read = min(file_size, 65535 + 22)
        return f.read(bytes_to_read)


def find_eocd(data: bytes) -> int:
    """
    Find the End of Central Directory record (EOCD).
    
    The EOCD is a 22-byte record with signature PK\x05\x06.
    We search backwards first for efficiency on small files,
    then forwards as fallback.
    
    Added debug prints to help diagnose why the EOCD isn't found.
    """
    # Find the EOCD signature: "PK\x05\x06" (little-endian)
    signature = struct.pack("<I", 0x06054b50)
    
    # Handle empty file case
    if len(data) < 22:
        raise ValueError("EOCD not found")
    
    # Search backwards first for efficiency on small files
    print(f"\n[DEBUG] File size: {len(data)} bytes")
    print(f"[DEBUG] EOCD signature (little-endian): {signature.hex()}")
    print(f"[DEBUG] Searching backwards from offset = {len(data) - 22} to max(0, {len(data) - 22 - 65535})")
    
    for i in range(len(data) - 22, max(0, len(data) - 22 - 65535), -1):
        if data[i:i+4] == signature:
            print(f"[DEBUG] Found EOCD at offset: {i}")
            return i
    
    # Search forwards as fallback
    print(f"[DEBUG] Searching forwards from offset = max(0, {len(data) - 22 - 65535}) to {len(data) - 22 + 1}")
    
    for i in range(max(0, len(data) - 22 - 65535), len(data) - 22 + 1):
        if data[i:i+4] == signature:
            print(f"[DEBUG] Found EOCD at offset: {i}")
            return i
    
    raise ValueError("EOCD not found")


def parse_central_directory(data: bytes, eocd_offset: int) -> list:
    """
    Parse the central directory from the EOCD.
    
    The EOCD gives us the offset of the central directory (offset field).
    We read that many bytes and parse each record.
    """
    # Read the central directory
    cd_offset = struct.unpack("<I", data[eocd_offset + 16:])[0]
    cd_data = data[cd_offset:cd_offset + struct.unpack("<I", data[eocd_offset + 12:])[0]]
    
    records = []
    i = 0
    while i < len(cd_data):
        record = {}
        # Signature (4 bytes)
        record["signature"] = cd_data[i:i+4]
        i += 4
        
        # Version made by (2 bytes)
        record["version_made_by"] = struct.unpack("<H", cd_data[i:i+2])[0]
        i += 2
        
        # Version needed (2 bytes)
        record["version_needed"] = struct.unpack("<H", cd_data[i:i+2])[0]
        i += 2
        
        # General purpose flags (2 bytes)
        record["general_purpose_flags"] = struct.unpack("<H", cd_data[i:i+2])[0]
        i += 2
        
        # Compression method (2 bytes)
        record["compression_method"] = struct.unpack("<H", cd_data[i:i+2])[0]
        i += 2
        
        # Last mod time (2 bytes, MS-DOS)
        record["last_mod_time"] = struct.unpack("<H", cd_data[i:i+2])[0]
        i += 2
        
        # Last mod date (2 bytes, MS-DOS)
        record["last_mod_date"] = struct.unpack("<H", cd_data[i:i+2])[0]
        i += 2
        
        # CRC-32 of uncompressed data (4 bytes)
        record["crc32"] = struct.unpack("<I", cd_data[i:i+4])[0]
        i += 4
        
        # Compressed size (4 bytes)
        record["compressed_size"] = struct.unpack("<I", cd_data[i:i+4])[0]
        i += 4
        
        # Uncompressed size (4 bytes)
        record["uncompressed_size"] = struct.unpack("<I", cd_data[i:i+4])[0]
        i += 4
        
        # File name length (2 bytes)
        record["file_name_length"] = struct.unpack("<H", cd_data[i:i+2])[0]
        i += 2
        
        # Extra field length (2 bytes)
        record["extra_field_length"] = struct.unpack("<H", cd_data[i:i+2])[0]
        i += 2
        
        # Comment length (2 bytes)
        record["comment_length"] = struct.unpack("<H", cd_data[i:i+2])[0]
        i += 2
        
        # Disk number start (2 bytes)
        record["disk_number_start"] = struct.unpack("<H", cd_data[i:i+2])[0]
        i += 2
        
        # Internal attributes (2 bytes)
        record["internal_attributes"] = struct.unpack("<H", cd_data[i:i+2])[0]
        i += 2
        
        # External attributes (4 bytes)
        record["external_attributes"] = struct.unpack("<I", cd_data[i:i+4])[0]
        i += 4
        
        # Offset of local file header (4 bytes)
        record["local_header_offset"] = struct.unpack("<I", cd_data[i:i+4])[0]
        i += 4
        
        # File name
        if record["file_name_length"] > 0:
            record["file_name"] = cd_data[i:i + record["file_name_length"]]
        
        # Extra field (optional)
        if record["extra_field_length"] > 0:
            record["extra_field"] = cd_data[i:i + record["extra_field_length"]]
        
        # Comment
        if record["comment_length"] > 0:
            record["comment"] = cd_data[i:i + record["comment_length"]]
        
        records.append(record)
    
    return records


def read_local_header(data: bytes, offset: int) -> dict:
    """
    Parse a local file header.
    
    The local header is at the offset given by the central directory.
    """
    record = {}
    # Signature (4 bytes)
    record["signature"] = data[offset:offset+4]
    
    # Version needed (2 bytes)
    record["version_needed"] = struct.unpack("<H", data[offset+4:offset+6])[0]
    
    # General purpose flags (2 bytes)
    record["general_purpose_flags"] = struct.unpack("<H", data[offset+6:offset+8])[0]
    
    # Compression method (2 bytes)
    record["compression_method"] = struct.unpack("<H", data[offset+8:offset+10])[0]
    
    # Last mod time (2 bytes, MS-DOS)
    record["last_mod_time"] = struct.unpack("<H", data[offset+10:offset+12])[0]
    
    # Last mod date (2 bytes, MS-DOS)
    record["last_mod_date"] = struct.unpack("<H", data[offset+12:offset+14])[0]
    
    # CRC-32 (4 bytes)
    record["crc32"] = struct.unpack("<I", data[offset+14:offset+18])[0]
    
    # Compressed size (4 bytes)
    record["compressed_size"] = struct.unpack("<I", data[offset+18:offset+22])[0]
    
    # Uncompressed size (4 bytes)
    record["uncompressed_size"] = struct.unpack("<I", data[offset+22:offset+26])[0]
    
    # File name length (2 bytes)
    record["file_name_length"] = struct.unpack("<H", data[offset+26:offset+28])[0]
    
    return record


def read_file(data: bytes, offset: int) -> bytes:
    """
    Read a file from the zip.
    
    The local header gives us the offset of the file data.
    With method 0 (store), the data is exactly `compressed_size` bytes.
    """
    # Get the local header
    local_header = read_local_header(data, offset)
    
    # File data starts at local_header_offset + 30 + n + m
    data_start = local_header["local_header_offset"] + 30 + len(local_header["file_name"])
    
    return data[data_start:data_start + local_header["uncompressed_size"]]


def verify_sha256(data: bytes, expected_hash: str) -> bool:
    """
    Verify that the given data has the expected SHA-256 hash.
    
    The hash is given as a lowercase hex string of 64 characters.
    """
    computed = hashlib.sha256(data).hexdigest().lower()
    return computed == expected_hash


def extract_file(file_path: str, output_dir: str) -> None:
    """
    Extract a file from the zip to the output directory.
    
    Creates the output directory if it doesn't exist.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = Path(output_dir) / Path(file_path).name
    output_path.write_bytes(data)


def list_contents(manifest: dict, central_directory: list) -> None:
    """
    List the contents of the zip with their meanings.
    
    Uses the manifest to get node types and descriptions.
    """
    print("\n" + "=" * 60)
    print("  LISTING CONTENTS WITH MEANINGS")
    print("=" * 60)
    
    # Get all unique node types from the manifest
    node_types = set()
    for node in manifest["nodes"]:
        if "type" in node:
            node_types.add(node["type"])
    
    # Sort by type name
    sorted_node_types = sorted(node_types, key=lambda t: (t.lower(), t))
    
    print(f"\n  {'NODE TYPE':<30} {'MEANING'}")
    print(f"  {'-'*60}")
    
    for node_type in sorted_node_types:
        # Find the description
        desc = ""
        if "note" in manifest["nodes"] and isinstance(manifest["nodes"], list):
            for n in manifest["nodes"]:
                if n.get("type") == node_type:
                    desc = n.get("note", "")
                    break
        
        print(f"  {node_type:<30} {desc}")
    
    # List all files
    print("\n  {'FILE PATH':<45} {'SIZE'}")
    print(f"  {'-'*90}")
    
    for entry in central_directory:
        size = f"{entry['uncompressed_size']:,}"
        if "file_name_length" in entry and entry["file_name_length"] > 0:
            file_path = entry["file_name"].decode("utf-8")
        else:
            file_path = os.path.basename(entry["file_name"])
        
        print(f"  {file_path:<45} {size}")
    
    # List the primary mesh
    print("\n  PRIMARY MESH: geom-game (GLB)")
    print("  PRIMARY SOUND: audio-crate-impact-hard-surface.wav")
    print()


def verify_hashes(manifest: dict, central_directory: list) -> None:
    """
    Verify every declared hash.
    
    For each node version, read the file at its declared offset
    and compare the SHA-256 to the declared value.
    """
    print("\n" + "=" * 60)
    print("  VERIFYING ALL DECLARED HASHES")
    print("=" * 60)
    
    # Get all unique node types from the manifest
    node_types = set()
    for node in manifest["nodes"]:
        if "type" in node:
            node_types.add(node["type"])
    
    # Sort by type name
    sorted_node_types = sorted(node_types, key=lambda t: (t.lower(), t))
    
    print(f"\n  {'NODE TYPE':<30} {'VERSION'} {'FILE PATH'} {'SHA-256'}")
    print(f"  {'-'*90}")
    
    for node_type in sorted_node_types:
        found = False
        for node in manifest["nodes"]:
            if node.get("type") == node_type:
                for version in node.get("versions", []):
                    if "files" in version and len(version["files"]) > 0:
                        file_info = version["files"][0]
                        sha256_declared = file_info["sha256"]
                        
                        # Find the file in central directory
                        entry = None
                        for e in central_directory:
                            if "file_name_length" in e and e["file_name_length"] > 0:
                                try:
                                    name = e["file_name"].decode("utf-8")
                                except UnicodeDecodeError:
                                    continue
                                if name == file_info["path"]:
                                    entry = e
                                    break
                        
                        if entry is None:
                            print(f"  {node_type:<30} {version.get('v', 'N/A')} {'NOT FOUND'} {sha256_declared}")
                            continue
                        
                        # Read the file from zip
                        data = read_file(data, entry["local_header_offset"])
                        
                        # Verify hash
                        if verify_sha256(data, sha256_declared):
                            status = "✓ PASS"
                        else:
                            status = "✗ FAIL"
                            
                        print(f"  {node_type:<30} {version.get('v', 'N/A')} {file_info['path']:<40} {status}")
                        found = True
                        break
                
                if not found:
                    print(f"  {node_type:<30} {'N/A'} {'NO VERSIONS'} {'N/A'}")
        
        # If no node of this type was found, print a row
        if not found:
            print(f"  {node_type:<30} {'N/A'} {'NO NODE'} {'N/A'}")


def extract_primary(manifest: dict, central_directory: list) -> None:
    """
    Extract the primary mesh and one sound.
    
    The primary mesh is "geom-game", the primary sound is
    "audio-crate-impact-hard-surface".
    """
    print("\n" + "=" * 60)
    print("  EXTRACTING PRIMARY MESH AND SOUND")
    print("=" * 60)
    
    # Find the primary mesh
    primary_mesh = None
    for node in manifest["nodes"]:
        if node.get("type") == "core.geom.game":
            primary_mesh = node
            break
    
    if primary_mesh is None:
        raise ValueError("Primary mesh not found")
    
    # Find the primary sound
    primary_sound = None
    for node in manifest["nodes"]:
        if node.get("type") == "core.audio.effect":
            primary_sound = node
            break
    
    if primary_sound is None:
        raise ValueError("Primary sound not found")
    
    # Extract primary mesh
    print(f"\n  Extracting primary mesh: {primary_mesh['node_id']}")
    extract_file(primary_mesh["node_id"], "extracted/meshes/")
    
    # Extract one sound (the crate impact)
    print(f"  Extracting sound: {primary_sound['node_id']}")
    extract_file(primary_sound["node_id"], "extracted/sounds/")


def main() -> None:
    """Main function that orchestrates the entire process."""
    file_path = Path("mini-v1.werk")
    
    # Read the zip file from end to start
    data = read_zip_file(str(file_path))
    
    # Find the EOCD with robust search (backwards first for small files)
    eocd_offset = find_eocd(data)
    
    # Parse the central directory
    central_directory = parse_central_directory(data, eocd_offset)
    
    # Read the manifest
    manifest = None
    for entry in central_directory:
        if "file_name_length" in entry and entry["file_name_length"] > 0:
            try:
                name = entry["file_name"].decode("utf-8")
            except UnicodeDecodeError:
                continue
            if name == "MANIFEST.json":
                manifest = read_file(data, entry["local_header_offset"])
                break
    
    if manifest is None:
        raise ValueError("Manifest not found in zip")
    
    # Parse the manifest JSON
    import json
    try:
        manifest = json.loads(manifest)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse MANIFEST.json: {e}")
    
    # List contents with meanings
    list_contents(manifest, central_directory)
    
    # Verify hashes
    verify_hashes(manifest, central_directory)
    
    # Extract primary mesh and sound
    extract_primary(manifest, central_directory)


if __name__ == "__main__":
    main()
