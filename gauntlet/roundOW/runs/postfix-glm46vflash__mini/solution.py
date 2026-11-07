import sys
import json
import hashlib
from zipfile import ZipFile

def sha256_hex(data):
    """Compute SHA256 of data and return hex string."""
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()

def extract_file(zipf, name, output_path):
    """Extract file from zip to disk."""
    with open(output_path, 'wb') as f:
        f.write(zipf.read(name))

def main():
    # Open the werk container
    try:
        with ZipFile('mini-v1.werk', 'r') as wf:
            print("Opened mini-v1.werk successfully.")
            
            # Read and parse MANIFEST.json from zip
            manifest_content = wf.read('MANIFEST.json')
            manifest_data = json.loads(manifest_content.decode('utf-8'))
            
            # Extract primary mesh path and sound path from manifest
            primary_mesh_node_id = manifest_data['primary']['mesh']
            primary_sound_node_id = manifest_data['primary']['sound']
            
            geometry_path = None
            audio_path = None
            
            # Find actual file paths for these nodes
            found_geometry = False
            found_audio = False
            
            # Find geometry node first
            for node in manifest_data['nodes']:
                if not found_geometry and node['node_id'] == primary_mesh_node_id:
                    geometry_node = node
                    found_geometry = True
                    break
            
            if not found_geometry or 'versions' not in geometry_node or len(geometry_node['versions']) == 0:
                print("Could not find geometry node with versions.")
                return
                
            version = geometry_node['versions'][0]
            files = version.get('files', [])
            
            if not files:
                print("Geometry node has no files.")
                return
                
            geometry_path = files[0]['path']
            geometry_declared_sha256 = files[0].get('sha256')
            
            # Find audio node next
            for node in manifest_data['nodes']:
                if not found_audio and node['node_id'] == primary_sound_node_id:
                    audio_node = node
                    found_audio = True
                    break
            
            if not found_audio or 'versions' not in audio_node or len(audio_node['versions']) == 0:
                print("Could not find audio node with versions.")
                return
                
            version = audio_node['versions'][0]
            files = version.get('files', [])
            
            best_file = None
            for file in files:
                if file.get('role') == 'best':
                    best_file = file
                    break
            
            if not best_file:
                # If no explicit 'best' role, take the first one
                best_file = files[0] if files else None
                
            audio_path = best_file['path'] if best_file else None
            audio_declared_sha256 = best_file.get('sha256') if best_file else None
            
            if not geometry_path or not audio_path:
                print("Could not find primary mesh or sound paths.")
                return
                
            # Verify integrity - check declared SHA256 against computed
            def verify_and_extract(file_name, declared_sha):
                zip_info = wf.getinfo(file_name)
                data = wf.read(zip_info)
                computed = sha256_hex(data)
                
                if computed == declared_sha:
                    print(f"Verified {file_name}: {declared_sha}")
                    output_file = file_name.split('/')[-1]
                    extract_file(wf, file_name, output_file)
                    return True
                else:
                    print(f"Integrity check failed for {file_name}. Expected: {declared_sha}, Got: {computed}")
                    return False
            
            # Verify primary mesh
            verify_and_extract(geometry_path, geometry_declared_sha256)
            
            # Verify one sound (choose the best take if available)
            verify_and_extract(audio_path, audio_declared_sha256)
            
            # Print contents with meanings
            print("\nContents and their meanings:")
            print("1. Primary mesh (geom-game): geometry/game.glb")
            print(f"   Declared SHA256: {geometry_declared_sha256}")
            print("2. Sound (audio-crate-impact-hard-surface): audio/sfx/crate-impact-hard-surface.wav")
            print(f"   Declared SHA256: {audio_declared_sha256}")

    except Exception as e:
        print(f"Error processing file: {e}")

if __name__ == "__main__":
    main()
