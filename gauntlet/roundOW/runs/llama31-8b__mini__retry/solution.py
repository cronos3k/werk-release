import hashlib
import os
import zipfile
from typing import Dict, List
import json

def read_manifest(zip_file: zipfile.ZipFile) -> Dict:
    """Reads the manifest from a zip archive."""
    with zip_file.open('MANIFEST.json', 'r') as f:
        return json.load(f)

def verify_hashes(manifest: Dict, zip_file: zipfile.ZipFile) -> bool:
    """Verifies hashes in the manifest."""
    for node in manifest['nodes']:
        for version in node['versions']:
            for file in version['files']:
                with zip_file.open(file['path'], 'r') as f:
                    if not hashlib.sha256(f.read()).hexdigest() == file['sha256']:
                        return False
    return True

def extract_primary_mesh(manifest: Dict) -> str:
    """Extracts the primary mesh from the manifest."""
    node_id = manifest['primary']['mesh']
    for node in manifest['nodes']:
        if node['node_id'] == node_id:
            for version in node['versions']:
                for file in version['files']:
                    return file['path']

def extract_sound(manifest: Dict) -> str:
    """Extracts a sound from the manifest."""
    node_id = manifest['primary']['sound']
    for node in manifest['nodes']:
        if node['node_id'] == node_id:
            for version in node['versions']:
                for file in version['files']:
                    return file['path']

def extract_files(zip_file: zipfile.ZipFile, extract_paths: List[str]) -> None:
    """Extracts files from a zip archive."""
    for path in extract_paths:
        zip_file.extract(path)

def main() -> None:
    with zipfile.ZipFile('mini-v1.werk') as zip_file:
        manifest = read_manifest(zip_file)
        if not verify_hashes(manifest, zip_file):
            print("Hashes do not match.")
            return

        primary_mesh = extract_primary_mesh(manifest)
        sound = extract_sound(manifest)

        extract_files(zip_file, [primary_mesh, sound])

        with open('REPORT.md', 'w') as f:
            f.write('# Report\n')
            f.write('## Success: {}\n'.format(verify_hashes(manifest, zip_file)))
            f.write('## Extracted files:\n')
            for file in [primary_mesh, sound]:
                f.write('* {}: {}\n'.format(file, hashlib.sha256(zip_file.read(file)).hexdigest()))
            f.write('# End of report\n')

if __name__ == '__main__':
    main()
