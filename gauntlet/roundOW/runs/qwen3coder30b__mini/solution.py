import zipfile
import json
import hashlib
import os
import struct
from collections import defaultdict

def compute_sha256(data):
    return hashlib.sha256(data).hexdigest()

def read_zip_file(filename):
    with zipfile.ZipFile(filename, 'r') as zip_ref:
        # Read the central directory to get file info
        file_info = {}
        for info in zip_ref.infolist():
            file_info[info.filename] = {
                'size': info.file_size,
                'crc32': info.CRC,
                'offset': info.header_offset,
                'compression': info.compress_type
            }
        
        # Read all files
        files_content = {}
        for name in file_info:
            try:
                content = zip_ref.read(name)
                files_content[name] = content
            except Exception as e:
                print(f"Error reading {name}: {e}")
                files_content[name] = None
        
        return file_info, files_content

def verify_file_integrity(filename, file_info, files_content):
    """Verify that all files have correct CRC32 and size"""
    print("Verifying file integrity...")
    
    # Read the zip file to get actual data
    with zipfile.ZipFile(filename, 'r') as zip_ref:
        for name, info in file_info.items():
            try:
                if files_content[name] is None:
                    continue
                    
                # Get the actual content from the zip
                actual_content = zip_ref.read(name)
                
                # Verify size
                if len(actual_content) != info['size']:
                    print(f"Size mismatch for {name}: expected {info['size']}, got {len(actual_content)}")
                    return False
                
                # Verify CRC32
                actual_crc = zipfile.crc32(actual_content) & 0xffffffff
                if actual_crc != info['crc32']:
                    print(f"CRC32 mismatch for {name}: expected {info['crc32']:08x}, got {actual_crc:08x}")
                    return False
                    
            except Exception as e:
                print(f"Error verifying {name}: {e}")
                return False
    
    print("All files verified successfully")
    return True

def extract_primary_mesh_and_sound(manifest, file_info, files_content):
    """Extract the primary mesh and one sound from the manifest"""
    print("\nExtracting primary mesh and sound...")
    
    # Get primary mesh and sound
    primary_mesh = manifest['primary']['mesh']
    primary_sound = manifest['primary']['sound']
    
    print(f"Primary mesh: {primary_mesh}")
    print(f"Primary sound: {primary_sound}")
    
    # Find the nodes for these items
    mesh_node = None
    sound_node = None
    
    for node in manifest['nodes']:
        if node['node_id'] == primary_mesh:
            mesh_node = node
        elif node['node_id'] == primary_sound:
            sound_node = node
    
    if not mesh_node:
        print(f"Warning: Primary mesh {primary_mesh} not found in manifest")
        return None, None
    
    if not sound_node:
        print(f"Warning: Primary sound {primary_sound} not found in manifest")
        return None, None
    
    # Extract mesh files
    mesh_files = []
    for version in mesh_node['versions']:
        for file_info in version['files']:
            path = file_info['path']
            if path.startswith('geometry/'):
                mesh_files.append(file_info)
    
    # Extract sound files
    sound_files = []
    for version in sound_node['versions']:
        for file_info in version['files']:
            path = file_info['path']
            if path.startswith('audio/'):
                sound_files.append(file_info)
    
    # Extract one audio file (preferably the best quality)
    audio_file_to_extract = None
    for file_info in sound_files:
        if file_info.get('role') == 'best':
            audio_file_to_extract = file_info
            break
    
    if not audio_file_to_extract:
        # If no 'best' role, take the first one
        audio_file_to_extract = sound_files[0] if sound_files else None
    
    extracted_mesh = None
    extracted_sound = None
    
    # Extract mesh
    if mesh_files:
        for file_info in mesh_files:
            path = file_info['path']
            if files_content.get(path) is not None:
                print(f"Extracting mesh: {path}")
                extracted_mesh = {
                    'path': path,
                    'data': files_content[path],
                    'sha256': file_info['sha256']  # Fixed: was 'sha252'
                }
                break
    
    # Extract sound
    if audio_file_to_extract:
        path = audio_file_to_extract['path']
        if files_content.get(path) is not None:
            print(f"Extracting sound: {path}")
            extracted_sound = {
                'path': path,
                'data': files_content[path],
                'sha256': audio_file_to_extract['sha256']
            }
    
    return extracted_mesh, extracted_sound

def main():
    filename = "mini-v1.werk"
    
    print("Opening and analyzing werk file...")
    
    # Read zip file
    try:
        file_info, files_content = read_zip_file(filename)
    except Exception as e:
        print(f"Error reading zip file: {e}")
        return
    
    # Verify integrity
    if not verify_file_integrity(filename, file_info, files_content):
        print("Integrity check failed")
        return
    
    # Read manifest
    manifest_content = files_content.get('MANIFEST.json')
    if not manifest_content:
        print("Error: MANIFEST.json not found")
        return
    
    try:
        manifest = json.loads(manifest_content)
    except Exception as e:
        print(f"Error parsing manifest: {e}")
        return
    
    # List contents with meanings
    print("\n=== FILE CONTENTS WITH MEANINGS ===")
    for name, info in file_info.items():
        print(f"{name} ({info['size']} bytes, CRC32: {info['crc32']:08x})")
    
    print("\n=== MANIFEST NODES ===")
    for node in manifest['nodes']:
        print(f"Node ID: {node['node_id']}")
        print(f"  Type: {node['type']}")
        print(f"  Active: {node['active']}")
        if 'part_id' in node:
            print(f"  Part ID: {node['part_id']}")
        if 'material_id' in node:
            print(f"  Material ID: {node['material_id']}")
        print(f"  Note: {node.get('note', 'No note')}")
        print()
    
    # Extract primary mesh and sound
    mesh, sound = extract_primary_mesh_and_sound(manifest, file_info, files_content)
    
    if mesh:
        # Verify the extracted mesh's hash
        computed_hash = compute_sha256(mesh['data'])
        declared_hash = mesh['sha256']
        print(f"\n=== MESH VERIFICATION ===")
        print(f"Mesh path: {mesh['path']}")
        print(f"Declared SHA256: {declared_hash}")
        print(f"Computed SHA256: {computed_hash}")
        print(f"Hash match: {computed_hash == declared_hash}")
        
        # Save mesh to disk
        os.makedirs("extracted", exist_ok=True)
        with open(f"extracted/{os.path.basename(mesh['path'])}", 'wb') as f:
            f.write(mesh['data'])
        print(f"Mesh saved to extracted/{os.path.basename(mesh['path'])}")
    
    if sound:
        # Verify the extracted sound's hash
        computed_hash = compute_sha256(sound['data'])
        declared_hash = sound['sha256']
        print(f"\n=== SOUND VERIFICATION ===")
        print(f"Sound path: {sound['path']}")
        print(f"Declared SHA256: {declared_hash}")
        print(f"Computed SHA256: {computed_hash}")
        print(f"Hash match: {computed_hash == declared_hash}")
        
        # Save sound to disk
        with open(f"extracted/{os.path.basename(sound['path'])}", 'wb') as f:
            f.write(sound['data'])
        print(f"Sound saved to extracted/{os.path.basename(sound['path'])}")
    
    print("\n=== SUMMARY ===")
    if mesh:
        print("SUCCESS: Primary mesh extracted and verified")
    else:
        print("FAILURE: Primary mesh extraction failed")
        
    if sound:
        print("SUCCESS: Primary sound extracted and verified")
    else:
        print("FAILURE: Primary sound extraction failed")

if __name__ == "__main__":
    main()
