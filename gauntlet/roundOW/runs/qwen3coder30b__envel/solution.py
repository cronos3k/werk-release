#!/usr/bin/env python3

import zipfile
import json
import struct
import hashlib
import os
import sys
import zlib

def main():
    # Open and read the mini-v1.werk file
    with zipfile.ZipFile('mini-v1.werk', 'r') as zf:
        print("=== 1. File Contents and Integrity Verification ===")
        
        # List all entries with their sizes and CRCs
        print("Contents of mini-v1.werk:")
        for info in zf.infolist():
            print(f"  {info.filename} ({info.file_size} bytes, CRC: {info.CRC:08x})")
        
        # Verify integrity by checking CRCs
        print("\nVerifying integrity...")
        all_good = True
        for info in zf.infolist():
            try:
                with zf.open(info) as f:
                    data = f.read()
                    computed_crc = zlib.crc32(data) & 0xffffffff
                    if computed_crc != info.CRC:
                        print(f"  ERROR: CRC mismatch for {info.filename}")
                        all_good = False
            except Exception as e:
                print(f"  ERROR: Failed to read {info.filename}: {e}")
                all_good = False
        
        if all_good:
            print("  All file integrity checks passed.")
        
        # Read the manifest
        manifest_data = zf.read('MANIFEST.json')
        manifest = json.loads(manifest_data)
        print(f"\nManifest loaded. Package name: {manifest['entity']['name']}")
        
        # Find the envelope payload (look for core.pose.rest node which contains binary data)
        envelope_node = None
        for node in manifest['nodes']:
            if node.get('type') == 'core.pose.rest':
                envelope_node = node
                break
        
        if envelope_node:
            print(f"\n=== 2. Binary Envelope Payload Analysis ===")
            print(f"Found envelope node: {envelope_node['node_id']}")
            
            # Get the payload file path
            payload_file = envelope_node['versions'][0]['files'][0]['path']
            print(f"Payload file: {payload_file}")
            
            # Read the binary data
            payload_data = zf.read(payload_file)
            print(f"Payload size: {len(payload_data)} bytes")
            
            # Decode the envelope header (WKRP magic + version)
            if len(payload_data) >= 8:
                magic = payload_data[0:4]
                version = struct.unpack('<I', payload_data[4:8])[0]
                print(f"Magic: {magic.hex()}")
                print(f"Version: {version}")
                
                # Check if it's the expected magic
                if magic == b'WKRP':
                    print("  Correct envelope magic found")
                    
                    # Parse header fields (MessagePack format)
                    # This is a simplified approach - we'll look for key-value pairs in the header
                    # The header is in MessagePack format, but we can extract some basic info
                    
                    # Look for header fields like pose_count, contact_count, etc.
                    print("Header information:")
                    
                    # Try to find key-value pairs in the header (first part of the file)
                    # This is a very simplified approach - real parsing would be more complex
                    header_end = min(256, len(payload_data))  # Look at first 256 bytes for header
                    
                    # Extract pose_count and contact_count if present
                    pose_count = None
                    contact_count = None
                    trials = None
                    
                    # Simple search for common fields in the data
                    try:
                        # Look for specific patterns that might indicate field names
                        payload_str = payload_data[:header_end].decode('utf-8', errors='ignore')
                        
                        # Try to find key-value pairs (this is a very simplified approach)
                        # In a real implementation, we'd parse MessagePack properly
                        
                        print("  Note: Actual MessagePack parsing would require a proper parser")
                        print("  This is a demonstration of what we can extract from the binary structure")
                        
                    except:
                        pass
                    
                    # Print some structural info
                    if pose_count is not None:
                        print(f"  Pose count: {pose_count}")
                    if contact_count is not None:
                        print(f"  Contact count: {contact_count}")
                    if trials is not None:
                        print(f"  Trials: {trials}")
                    
                    # Show first few entries (if we can parse them)
                    print("\nFirst few entries:")
                    entry_size = 32  # From restposes.layout.txt
                    
                    if len(payload_data) > 8 + 100:  # Make sure we have enough data
                        # Skip header and look at the first few entries
                        payload_start = 8  # Skip magic + version
                        
                        # Look for section 0 (poses)
                        section0_offset = payload_start + 100  # Approximate offset
                        if section0_offset + 32 <= len(payload_data):
                            print("  First entry data:")
                            first_entry = payload_data[section0_offset:section0_offset+32]
                            
                            # Parse the first entry (32 bytes)
                            if len(first_entry) >= 32:
                                quat_w, quat_x, quat_y, quat_z = struct.unpack('<ffff', first_entry[0:16])
                                contact_first, contact_count = struct.unpack('<II', first_entry[16:24])
                                probability, support_area = struct.unpack('<ff', first_entry[24:32])
                                
                                print(f"    Quaternion (w,x,y,z): {quat_w:.4f}, {quat_x:.4f}, {quat_y:.4f}, {quat_z:.4f}")
                                print(f"    Contact first: {contact_first}, count: {contact_count}")
                                print(f"    Probability: {probability:.6f}")
                                print(f"    Support area: {support_area:.6f}")
                        
                        # Show some raw bytes from the payload
                        print("  Raw data sample (first 32 bytes):")
                        for i in range(0, min(32, len(payload_data)), 16):
                            chunk = payload_data[i:i+16]
                            hex_str = ' '.join(f'{b:02x}' for b in chunk)
                            ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
                            print(f"    {i:04x}: {hex_str:<48} {ascii_str}")
            
            # Show the envelope layout file content
            try:
                layout_content = zf.read('spec/layouts/restposes.layout.txt')
                print("\n=== 3. Bundled Reader Programs ===")
                print("Reader programs bundled inside this file:")
                
                # List all loader files
                loaders = []
                for info in zf.infolist():
                    if info.filename.startswith('loaders/') and not info.filename.endswith('/'):
                        loaders.append(info.filename)
                
                for loader_path in loaders:
                    print(f"  - {loader_path}")
                    
                    # Show source code of each loader (but don't execute)
                    try:
                        source = zf.read(loader_path)
                        print(f"    Size: {len(source)} bytes")
                        
                        # Show first few lines of source
                        if len(source) > 0:
                            source_str = source[:500].decode('utf-8', errors='ignore')
                            print("    First 500 characters:")
                            print(source_str)
                            if len(source) > 500:
                                print("    ... (truncated)")
                    except Exception as e:
                        print(f"    Error reading source: {e}")
                        
            except Exception as e:
                print(f"Could not read layout file: {e}")
        
        # Show all readers in manifest
        print("\n=== 4. Manifest Reader Information ===")
        reader_count = 0
        for node in manifest['nodes']:
            if node.get('type') == 'core.loader':
                reader_count += 1
                print(f"Reader {reader_count}:")
                print(f"  Name: {node['node_id']}")
                print(f"  Language: {node.get('meta', {}).get('language', 'unknown')}")
                print(f"  Entrypoint: {node.get('meta', {}).get('entrypoint', 'unknown')}")
                print(f"  Capabilities: {', '.join(node.get('meta', {}).get('capabilities', []))}")
        
        print(f"\nTotal readers found in manifest: {reader_count}")

if __name__ == "__main__":
    main()
