import hashlib
import os
import struct
from typing import Dict, List

def read_file(path: str) -> bytes:
    """Read a file into memory."""
    with open(path, 'rb') as f:
        return f.read()

def crc32(data: bytes) -> int:
    """Compute the CRC-32 of a byte string."""
    crc = 0xFFFFFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ (0xEDB88320 if (crc & 1) else 0)
    return crc ^ 0xFFFFFFFF

def sha256(data: bytes) -> str:
    """Compute the SHA-256 of a byte string."""
    return hashlib.sha256(data).hexdigest()

def read_manifest(manifest_path: str, manifest_data: bytes) -> Dict[str, any]:
    """Read and parse the manifest file."""
    import json
    try:
        return json.loads(manifest_data.decode('utf-8'))
    except Exception as e:
        print(f"Error parsing manifest: {e}")
        return {}

def verify_hashes(manifest: Dict[str, any], files: List[Dict[str, any]]) -> bool:
    """Verify the hashes of all files in the package."""
    for file in files:
        if sha256(read_file(file['path'])) != file['sha256']:
            return False
    return True

def extract_mesh(manifest: Dict[str, any], files: List[Dict[str, any]]) -> str:
    """Extract the primary mesh from the package."""
    mesh_node_id = manifest.get('primary', {}).get('mesh')
    if mesh_node_id is None:
        print("Mesh node ID not found in manifest.")
        return ""
    for node in manifest['nodes']:
        if node['node_id'] == mesh_node_id:
            return node['versions'][0]['files'][0]['path']

def extract_sound(manifest: Dict[str, any], files: List[Dict[str, any]]) -> str:
    """Extract the primary sound from the package."""
    sound_node_id = manifest.get('primary', {}).get('sound')
    if sound_node_id is None:
        print("Sound node ID not found in manifest.")
        return ""
    for node in manifest['nodes']:
        if node['node_id'] == sound_node_id:
            return node['versions'][0]['files'][1]['path']

def main():
    # Get the current working directory
    cwd = os.getcwd()
    
    # Read the manifest file
    manifest_path = 'mini-v1.werk'
    manifest_data = read_file(manifest_path)
    
    # Parse the manifest data
    import json
    manifest = read_manifest(manifest_path, manifest_data)
    
    # Verify the hashes of all files in the package
    if 'container' not in manifest:
        print("Container not found in manifest.")
        return
    
    files = manifest['container'].get('entry_order', [])
    if not verify_hashes(manifest, files):
        print("Hash verification failed.")
        return
    
    # Extract the primary mesh and sound from the package
    mesh_path = extract_mesh(manifest, files)
    sound_path = extract_sound(manifest, files)
    
    # Print the extracted file paths and their hashes
    if mesh_path:
        print(f"Extracted mesh: {mesh_path}")
        print(f"Hash of extracted mesh: {sha256(read_file(mesh_path))}")
    if sound_path:
        print(f"Extracted sound: {sound_path}")
        print(f"Hash of extracted sound: {sha256(read_file(sound_path))}")

if __name__ == '__main__':
    main()
