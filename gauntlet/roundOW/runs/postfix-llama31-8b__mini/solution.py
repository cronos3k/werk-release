import zipfile
import hashlib
import json
from typing import Dict, List

def read_manifest(zip_file: zipfile.ZipFile) -> Dict:
    """Reads the manifest from a zip archive."""
    with zip_file.open('MANIFEST.json', 'r') as f:
        return json.load(f)

def extract_primary_mesh(manifest: Dict) -> (str, int):
    """Extracts the primary mesh and its size from the manifest."""
    node_id = manifest['primary']['mesh']
    for node in manifest['nodes']:
        if node['node_id'] == node_id:
            for version in node['versions']:
                for file in version['files']:
                    return file['path'], file['size']

def extract_sound(manifest: Dict) -> (str, int):
    """Extracts the sound and its size from the manifest."""
    node_id = manifest['primary']['sound']
    for node in manifest['nodes']:
        if node['node_id'] == node_id:
            for version in node['versions']:
                for file in version['files']:
                    return file['path'], file['size']

def verify_hashes(manifest: Dict, extracted_files: List) -> bool:
    """Verifies the hashes of the extracted files."""
    for file in manifest['nodes'][0]['versions'][0]['files']:
        if not any(extracted_file['sha256'] == file['sha256'] and extracted_file['size'] == file['size'] for extracted_file in extracted_files):
            return False
    return True

def extract_files(zip_file: zipfile.ZipFile, manifest: Dict) -> List:
    """Extracts the files from a zip archive."""
    extracted_files = []
    for node in manifest['nodes']:
        for version in node['versions']:
            for file in version['files']:
                if 'media_type' not in file or file['media_type'] == 'application/octet-stream':
                    with zip_file.open(file['path'], 'r') as f:
                        data = f.read()
                    extracted_files.append({'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)})
    return extracted_files

def main():
    # Open the zip file
    with zipfile.ZipFile('mini-v1.werk', 'r') as zip_file:
        # Read the manifest from MANIFEST.json inside the zip archive
        manifest = read_manifest(zip_file)
        
        # Extract the primary mesh and sound
        primary_mesh_path, primary_mesh_size = extract_primary_mesh(manifest)
        sound_path, sound_size = extract_sound(manifest)
        
        # Verify the hashes of the extracted files
        extracted_files = extract_files(zip_file, manifest)
        if not verify_hashes(manifest, extracted_files):
            print("Hashes do not match")
            return
        
        # Extract the primary mesh and sound to disk
        with open('extracted_mesh.glb', 'wb') as f:
            with zip_file.open(primary_mesh_path, 'r') as zip_f:
                f.write(zip_f.read())
        
        with open('extracted_sound.wav', 'wb') as f:
            with zip_file.open(sound_path, 'r') as zip_f:
                f.write(zip_f.read())

if __name__ == "__main__":
    main()
