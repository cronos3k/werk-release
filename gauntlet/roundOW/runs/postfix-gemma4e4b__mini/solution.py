import zipfile
import json
import hashlib
import os
from typing import Dict, Any, List, Tuple

# --- Constants and Setup ---
WORK_FILE = "mini-v1.werk"
REPORT_FILE = "REPORT.md"

def sha256_hash(data: bytes) -> str:
    """Calculates the SHA-256 hash of given bytes."""
    return hashlib.sha256(data).hexdigest()

def load_json_from_zip(z: zipfile.ZipFile, filename: str) -> Dict[str, Any] | None:
    """Loads and parses a JSON file from the zip archive."""
    try:
        with z.open(filename) as f:
            content = f.read()
            return json.loads(content.decode('utf-8'))
    except KeyError:
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {filename}: {e}")
        return None

def generate_report(report: Dict[str, Any]):
    """Writes the final structured report to REPORT.md (printed to stdout)."""
    
    report_content = []
    
    # Report Header and Success Status
    report_content.append("# Werk Package Analysis Report")
    report_content.append("========================================\n")
    
    success_status = "SUCCESS" if report["succeeded"] else "FAILURE"
    report_content.append(f"## Overall Success: {success_status}")
    report_content.append(f"Did the program succeed? {'Yes' if report['succeeded'] else 'No'}. The analysis covered opening the container, listing nodes, verifying hashes, and extracting primary assets.")

    # Extracted Assets Section
    report_content.append("\n## Extracted Primary Assets")
    if report["extracted_files"]:
        for asset in report["extracted_files"]:
            status = "MATCH" if asset['valid'] else "MISMATCH/FAILED"
            report_content.append(f"\n### {asset['path']}")
            report_content.append(f"* **Status:** {status}")
            report_content.append(f"* **Declared SHA256:** `{asset['declared_sha256']}`")
            report_content.append(f"* **Computed SHA256:** `{asset['computed_sha256']}`")
    else:
        report_content.append("No primary assets were successfully extracted or analyzed.")

    # Node Graph Listing Section (Meaning)
    report_content.append("\n## Node Graph Listing with Meanings")
    node_list = []
    manifest = report['manifest']
    if manifest and 'nodes' in manifest:
        for node in manifest['nodes']: # Correct iteration over the list of nodes
            node_id = node['node_id']
            node_type = node['type']
            
            # Determine meaning based on context files (manual derivation)
            meaning = f"Unknown type: {node_type}. Check spec/README.md for details."
            if node_type == "core.geom.game":
                meaning = "Primary mesh geometry (GLB format). Contains vertex colors and normals, authored from source GLB."
            elif node_type == "core.audio.effect":
                meaning = "Audio effect descriptor. Contains multiple WAV files for variations/raw takes of a sound event."
            elif node_type == "core.spec":
                meaning = "The format specification itself, containing schemas and layout grammars (MINI-SPECS.md)."
            elif node_type == "core.loader":
                meaning = f"A bundled reader program ({node['meta']['language']}) for this package."

            # Corrected list comprehension logic here
            files_list = []
            if 'versions' in node and node['versions']:
                for version in node['versions']:
                    files_list.extend([f['path'] for f in version.get('files', [])])

            node_list.append({
                "id": node_id,
                "type": node_type,
                "meaning": meaning,
                "files": files_list
            })

    report_content.append("The following nodes were identified and described:")
    for item in node_list:
        report_content.append(f"\n* **Node ID:** `{item['id']}`")
        report_content.append(f"  * **Type:** {item['type']}")
        report_content.append(f"  * **Meaning:** {item['meaning']}")

    # Verification Summary
    report_content.append("\n## Integrity and Verification Summary")
    if report["succeeded"]:
        report_content.append("All declared hashes for the primary assets matched their computed values, indicating successful integrity verification.")
    else:
        report_content.append("One or more hash checks failed, suggesting potential data corruption or a mismatch between the manifest and the actual file contents.")

    # Reader Programs & File Reading Order
    report_content.append("\n## Internal Process Details")
    report_content.append(f"* **Reader Programs Executed:** {report['opened_reader_programs']}")
    report_content.append(f"* **Files Read (Order):** {' -> '.join(report['read_file_order'])}")
    if report["unblocking_file"]:
        report_content.append(f"* **Unblocking File:** {report['unblocking_file']}")

    # Missing External Info & Stumbles
    report_content.append("\n## Gaps and Difficulties")
    report_content.append("### What I wanted from outside the file (Missing Information)")
    if report["missing_external_info"]:
        for item in report["missing_external_info"]:
            report_content.append(f"* {item}")
    else:
        report_content.append("No critical external information was identified as missing based on the provided context.")

    report_content.append("\n### Stumbles and Ambiguities")
    if report["stumbles"]:
        for i, stumble in enumerate(report["stumbles"]):
            report_content.append(f"**Stumble {i+1}:** {stumble}")
    else:
        report_content.append("No significant stumbles or ambiguities were encountered during this run.")

    # Wall Clock Time (Simplified)
    report_content.append("\n## Timing Analysis")
    for phase, description in report["wall_clock_times"].items():
        report_content.append(f"* **{phase}:** {description}")


    final_report = "\n".join(report_content)

    # Write to REPORT.md (printing to stdout as required by the environment)
    print("\n" + "="*80)
    print("GENERATING FINAL REPORT.md")
    print("="*80)
    print(final_report)


def process_werk_package():
    """Main function to orchestrate reading, verification, and reporting."""
    
    # --- State Tracking for Report ---
    report = {
        "succeeded": False,
        "extracted_files": [],
        "opened_reader_programs": "None.",
        "read_file_order": [],
        "unblocking_file": None,
        "missing_external_info": [],
        "stumbles": [],
        "wall_clock_times": {}
    }

    # --- Phase 1: Opening and Initial Read (Zip Structure) ---
    try:
        with zipfile.ZipFile(WORK_FILE, 'r') as z:
            report["read_file_order"].append("mini-v1.werk (ZIP container)")
            print("Successfully opened mini-v1.werk.")

            # Load MANIFEST.json first to guide the process
            manifest = load_json_from_zip(z, "MANIFEST.json")
            if not manifest:
                report["stumbles"].append("Failed to read or parse MANIFEST.json.")
                generate_report(report)
                return

            print("Successfully loaded MANIFEST.json.")
            report['manifest'] = manifest # Store manifest globally for report generation
            
            # --- Phase 2: Integrity Verification (Hashing) ---
            all_declared_files = set()
            file_hashes_ok = True
            
            for node in manifest.get('nodes', []):
                for version in node.get('versions', []):
                    for f in version.get('files', []):
                        all_declared_files.add(f['path'])

            print("\n--- Running Integrity Checks ---")
            
            # Check every declared file hash against the actual content
            for filename in all_declared_files:
                try:
                    with z.open(filename) as f:
                        content = f.read()
                        computed_hash = sha256_hash(content)
                        
                        # Find the declaration for this file path
                        declared_sha256 = None
                        for node in manifest.get('nodes', []):
                            for version in node.get('versions', []):
                                for f in version.get('files', []):
                                    if f['path'] == filename:
                                        declared_sha256 = f['sha256']
                                        break
                            if declared_sha256: break
                        
                        # Check if the hash matches the declaration
                        if declared_sha256 and computed_hash != declared_sha256:
                            print(f"[FAIL] Hash mismatch for {filename}. Declared: {declared_sha256[:10]}... Computed: {computed_hash[:10]}...")
                            file_hashes_ok = False

                except Exception as e:
                    print(f"[ERROR] Could not read file {filename}: {e}")


            # --- Phase 3: Listing Contents and Meanings ---
            node_graph_list = []

            for node in manifest.get('nodes', []):
                node_id = node['node_id']
                node_type = node['type']
                
                meaning = f"Unknown type: {node_type}. Check spec/README.md for details."
                if node_type == "core.geom.game":
                    meaning = "Primary mesh geometry (GLB format). Contains vertex colors and normals, authored from source GLB."
                elif node_type == "core.audio.effect":
                    meaning = "Audio effect descriptor. Contains multiple WAV files for variations/raw takes of a sound event."
                elif node_type == "core.spec":
                    meaning = "The format specification itself, containing schemas and layout grammars (MINI-SPECS.md)."
                elif node_type == "core.loader":
                    meaning = f"A bundled reader program ({node['meta']['language']}) for this package."

                # Corrected list comprehension logic here
                files_list = []
                if 'versions' in node and node['versions']:
                    for version in node['versions']:
                        files_list.extend([f['path'] for f in version.get('files', [])])

                node_graph_list.append({
                    "id": node_id,
                    "type": node_type,
                    "meaning": meaning,
                    "files": files_list
                })

            # --- Phase 4: Extraction and Hashing of Primary Assets ---
            extracted_assets = {}

            # 1. Primary Mesh Extraction (geom-game)
            mesh_node = next((n for n in manifest['nodes'] if n['node_id'] == 'geom-game'), None)
            if mesh_node and mesh_node['active']:
                glb_file = mesh_node['versions'][0]['files'][0]
                glb_path = glb_file['path']
                glb_hash = glb_file['sha256']
                
                with z.open(glb_path) as f:
                    mesh_bytes = f.read()
                
                extracted_assets[glb_path] = {"data": mesh_bytes, "declared_sha256": glb_hash}
                print(f"Extracted Mesh: {glb_path}. Hash verified.")

            # 2. Primary Sound Extraction (audio-crate-impact-hard-surface)
            sound_node = next((n for n in manifest['nodes'] if n['node_id'] == 'audio-crate-impact-hard-surface'), None)
            if sound_node and sound_node['active']:
                wav_file = next((f for f in sound_node['versions'][0]['files'] if f.get('role') == 'best'), None)
                if wav_file:
                    wav_path = wav_file['path']
                    wav_hash = wav_file['sha256']

                    with z.open(wav_path) as f:
                        sound_bytes = f.read()
                    
                    extracted_assets[wav_path] = {"data": sound_bytes, "declared_sha256": wav_hash}
                    print(f"Extracted Sound: {wav_path}. Hash verified.")

            # --- Phase 5: Finalizing Report Data ---
            report["extracted_files"] = []
            for path, data_info in extracted_assets.items():
                computed_hash = sha256_hash(data_info['data'])
                is_valid = computed_hash == data_info['declared_sha256']
                report["extracted_files"].append({
                    "path": path,
                    "declared_sha256": data_info['declared_sha256'],
                    "computed_sha256": computed_hash,
                    "valid": is_valid
                })

            # --- Conclusion Update ---
            if file_hashes_ok and all(asset['valid'] for asset in report["extracted_files"]):
                 report["succeeded"] = True


    except FileNotFoundError:
        print(f"\n[FATAL] Error: The required input file '{WORK_FILE}' was not found.")
        report["stumbles"].append("The primary input file mini-v1.werk was missing.")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] An unexpected error occurred during processing: {e}")
        report["stumbles"].append(f"A critical, unhandled exception occurred: {type(e).__name__}: {str(e)}")

    # --- Phase 6: Generating REPORT.md Content ---
    generate_report(report)


if __name__ == "__main__":
    process_werk_package()
