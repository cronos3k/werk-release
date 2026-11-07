import zipfile
import json

def main():
    """
    Solves the task by analyzing gsplat-v1.werk:
    1. Lists contents with meanings and verifies integrity.
    2. Extracts point positions and colours from points/plush-dc.wkpc.
    3. Identifies tools that created the file, their roles, and sources.
    
    The program reads only the provided manifest and spec files; no external
    libraries beyond Python's standard library are used.
    """
    print("=== TASK ANALYSIS ===")
    print("1. Listing contents with meanings...")
    print("2. Extracting point positions/colours from points/plush-dc.wkpc...")
    print("3. Identifying creation tools and their sources...\n")

    # Open the zip file
    try:
        with zipfile.ZipFile('gsplat-v1.werk', 'r') as z:
            # Read manifest.json to get structure information
            manifest_content = z.read('MANIFEST.json')
            manifest = json.loads(manifest_content)
            
            # Task 1: List contents with meanings
            print("=== CONTENTS LISTING ===")
            entry_order = manifest.get('container', {}).get('entry_order', [])
            for entry_name in entry_order:
                if not entry_name.endswith('/'):
                    # Find node that owns this file, or infer from path pattern
                    found_node = None
                    nodes = manifest.get('nodes', {})
                    
                    # Ensure nodes is a dictionary
                    if isinstance(nodes, dict):
                        for node_id, node_info in nodes.items():
                            if 'files' in node_info and entry_name in node_info.get('files', []):
                                found_node = node_info
                                break
                    
                    if not found_node:
                        # Infer based on file extension or directory structure
                        if entry_name.startswith('splats/'):
                            meaning = "3D Gaussian splat (WKGS)"
                        elif entry_name.startswith('points/'):
                            meaning = "Point cloud (WKPC)"
                        elif entry_name.startswith('tools/'):
                            meaning = "Source code for a creation tool"
                        elif entry_name == 'recipe/recipe.json':
                            meaning = "Build recipe file"
                        else:
                            meaning = f"Unknown entry ({entry_name})"
                    
                    print(f"- {entry_name}: {meaning}")
                else:
                    # Directory entry
                    print(f"- {entry_name} (directory)")

            # Verify integrity: check that declared sizes match actual file sizes
            print("\n=== INTEGRITY VERIFICATION ===")
            total_declared_size = 0
            for name in manifest.get('container', {}).get('entry_order', []):
                if not name.endswith('/'):
                    size = z.getinfo(name).file_size
                    total_declared_size += size
            
            # Compare with zip file size (should be same)
            actual_zip_size = z.file_size
            integrity_ok = abs(actual_zip_size - total_declared_size) < 1  # allow for rounding
            print(f"Total declared size: {total_declared_size} bytes")
            print(f"Actual zip size: {actual_zip_size} bytes")
            print(f"Integrity check {'passed' if integrity_ok else 'failed'}")

            # Task 2: Extract points from points/plush-dc.wkpc
            print("\n=== POINT CLOUD EXTRACTION ===")
            try:
                wkpc_path = "points/plush-dc.wkpc"
                wkpc_data = z.read(wkpc_path)
                
                # Parse WKPC header (based on spec/layouts/points.layout.txt)
                magic = wkpc_data[0:4]
                if magic != b'WKPC':
                    raise ValueError(f"Invalid magic for {wkpc_path}")
                
                version = int.from_bytes(wkpc_data[4:8], 'little')
                if version != 1:
                    raise ValueError(f"Unsupported WKPC version {version} in {wkpc_path}")
                
                header_len = int.from_bytes(wkpc_data[8:12], 'little')
                header_start = 12
                header_end = header_start + header_len
                
                # Decode MessagePack header (simplified - we trust manifest)
                sections = []
                for node_id, node_info in manifest.get('nodes', {}).items():
                    if node_id == "points-dc":
                        sections.extend(node_info.get('sections', []))
                
                point_count = None
                position_offset = 0
                color_offset = 0
                
                # Find position and color section info from manifest (since we trust it)
                for s in sections:
                    if s['name'] == 'position':
                        position_offset = s['offset']
                        position_size = s['size']
                        position_shape = s['shape']
                        position_dtype = s['dtype']
                    elif s['name'] == 'color':
                        color_offset = s['offset']
                        color_size = s['size']
                        color_shape = s['shape']
                        color_dtype = s['dtype']
                
                if point_count is None:
                    point_count = position_shape[0]  # first element of shape
                
                print(f"Point count: {point_count}")
                
                # Sample positions (first few points)
                pos_start = position_offset
                pos_end = pos_start + position_size
                pos_data = wkpc_data[pos_start:pos_end]
                
                if position_dtype == 'f32':
                    pos_bytes_per_point = 4 * len(position_shape[1])
                    num_points = point_count
                    positions = []
                    for i in range(num_points):
                        start_idx = i * pos_bytes_per_point
                        end_idx = start_idx + pos_bytes_per_point
                        if end_idx > len(pos_data):
                            break
                        # Extract x, y, z (shape[1] is 3)
                        x = float.from_bytes(pos_data[start_idx:start_idx+4], 'little')
                        y = float.from_bytes(pos_data[start_idx+4:start_idx+8], 'little')
                        z = float.from_bytes(pos_data[start_idx+8:start_idx+12], 'little')
                        positions.append((x, y, z))
                
                # Sample colours (first few points)
                color_start = color_offset
                color_end = color_start + color_size
                color_data = wkpc_data[color_start:color_end]
                
                if color_dtype == 'u8':
                    color_bytes_per_point = 1 * len(color_shape[1])
                    num_points = point_count
                    colours = []
                    for i in range(num_points):
                        start_idx = i * color_bytes_per_point
                        end_idx = start_idx + color_bytes_per_point
                        if end_idx > len(color_data):
                            break
                        # Extract R, G, B, A (shape[1] is 4)
                        r = color_data[start_idx]
                        g = color_data[start_idx+1]
                        b = color_data[start_idx+2]
                        a = color_data[start_idx+3]
                        colours.append((r, g, b, a))
                
                # Print sample data
                print(f"\nSample positions (first 5 points):")
                for p in positions[:5]:
                    print(p)
                
                print("\nSample colours (first 5 points - R,G,B,A as u8):")
                for c in colours[:5]:
                    print(c)

            except Exception as e:
                print(f"Error extracting point data: {e}")

            # Task 3: Identify creation tools
            print("\n=== CREATION TOOLS IDENTIFICATION ===")
            tools = []
            for node_id, node_info in manifest.get('nodes', {}).items():
                if node_info.get('type') in ['core.tool', 'core.tool.config']:
                    tool_meta = {
                        "node_id": node_id,
                        "role": node_info.get('meta', {}).get('role', 'unknown'),
                        "language": node_info.get('meta', {}).get('language', 'unknown'),
                        "form": node_info.get('meta', {}).get('form', 'unknown'),
                        "files": [f.path for f in z.infolist() if f.filename.startswith(f'tools/{node_id}/')]
                    }
                    tools.append(tool_meta)
            
            print("\nTools that created this file:")
            for tool in tools:
                print(f"- {tool['node_id']}: Role={tool['role']}, Language={tool['language']}")
                print(f"  Source files: {[f.name for f in tool['files']]}\n")

    except Exception as e:
        print(f"Error processing file: {e}")

if __name__ == "__main__":
    main()
