import hashlib
import json
from zipfile import ZipFile

def read_manifest(zip_file):
    manifest_path = "MANIFEST.json"
    with zip_file.open(manifest_path) as f:
        return json.load(f)

def extract_primary_mesh_and_sound(zip_file, manifest):
    primary_mesh = manifest["primary"]["mesh"]
    primary_sound = manifest["primary"]["sound"]

    mesh_path = f"geometry/{primary_mesh}.glb"
    sound_path = f"audio/sfx/{primary_sound}.wav"

    try:
        with zip_file.open(mesh_path) as f:
            mesh_data = f.read()
    except KeyError:
        return None, None

    try:
        with zip_file.open(sound_path) as f:
            sound_data = f.read()
    except KeyError:
        return mesh_data, None

    return mesh_data, sound_data

def verify_hashes(zip_file, manifest):
    for node in manifest["nodes"]:
        for version in node["versions"]:
            for file in version["files"]:
                path = file["path"]
                expected_sha256 = file["sha256"]

                with zip_file.open(path) as f:
                    actual_sha256 = hashlib.sha256(f.read()).hexdigest()

                if actual_sha256 != expected_sha256:
                    print(f"Hash mismatch: {path} ({expected_sha256}) vs. ({actual_sha256})")

def main():
    zip_file_path = "mini-v1.werk"
    with ZipFile(zip_file_path, 'r') as zip_file:
        manifest = read_manifest(zip_file)

        mesh_data, sound_data = extract_primary_mesh_and_sound(zip_file, manifest)
        if mesh_data is not None and sound_data is not None:
            print(f"Extracted primary mesh: {len(mesh_data)} bytes")
            print(f"Extracted primary sound: {len(sound_data)} bytes")

        verify_hashes(zip_file, manifest)

if __name__ == "__main__":
    main()
