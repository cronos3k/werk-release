import json
from typing import Dict, List

def read_manifest(file_path: str) -> Dict:
    """Reads the manifest from a file and returns it as a dictionary."""
    with open(file_path, 'rb') as f:
        return json.load(f)

def print_node_info(node: Dict) -> None:
    """Prints information about a node, including its type, versions, and edges."""
    print(f"Node ID: {node['node_id']}")
    print(f"Type: {node['type']}")
    if 'versions' in node:
        for version in node['versions']:
            print(f"Version: {version['v']}")
            if 'files' in version:
                for file in version['files']:
                    print(f"File: {file['path']} (SHA256: {file['sha256']})")
    if 'edges' in node:
        for edge in node['edges']:
            print(f"Edge to: {edge['to']} (kind: {edge['kind']}, role: {edge['role']})")

def print_reader_info(reader_node: Dict) -> None:
    """Prints information about a reader, including its type and source code."""
    print(f"Reader Node ID: {reader_node['node_id']}")
    print(f"Type: {reader_node['type']}")
    if 'versions' in reader_node:
        for version in reader_node['versions']:
            print(f"Version: {version['v']}")
            if 'files' in version:
                for file in version['files']:
                    print(f"File: {file['path']} (SHA256: {file['sha256']})")
    if 'meta' in reader_node:
        print(f"Language: {reader_node['meta']['language']}")
        print(f"Source Code:")
        with open(reader_node['meta']['entrypoint'], 'r', encoding='utf-8') as f:
            print(f.read())

def main() -> None:
    # Read the manifest
    manifest = read_manifest('mini-v1.werk')

    # Print information about each node in the manifest
    for node_id, node in manifest['nodes'].items():
        print_node_info(node)

    # Find and print information about the reader nodes
    loader_nodes = [node for node in manifest['nodes'] if node['type'] == 'core.loader']
    for loader_node in loader_nodes:
        print_reader_info(loader_node)

if __name__ == '__main__':
    main()
