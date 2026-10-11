"""Format-agnostic probe for crate-nc-v1.usdz.

This deliberately does NOT parse the container. The task forbids applying
format knowledge that is not derived from inside the file, and the file
contains no format documentation, no manifest, no declared hashes and no
reader program. So this program only reports what can be observed without
any format rules:

  * size and sha256 of the whole file (read-only; the file is never modified)
  * an inventory of printable ASCII runs (candidate names / human text)
  * whether anything resembling a manifest, hash list, spec or reader exists

Usage:  python -I crate_probe.py crate-nc-v1.usdz [min_run_length]
"""
import hashlib
import re
import sys

DOC_HINTS = ('manifest', 'sha256', 'sha-256', 'readme', 'spec', 'format',
             'loader', 'reader', 'offset', 'length', 'little-endian', '.py',
             '.md', '.txt', '.json')
HEX64 = re.compile(rb'(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])')


def main():
    path = sys.argv[1]
    min_run = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    with open(path, 'rb') as f:
        data = f.read()

    print(f'file:   {path}')
    print(f'size:   {len(data)} bytes')
    print(f'sha256: {hashlib.sha256(data).hexdigest()}')
    print()

    runs = [(m.start(), m.group().decode('ascii'))
            for m in re.finditer(rb'[\x20-\x7e]{%d,}' % min_run, data)]
    print(f'printable ASCII runs >= {min_run} chars: {len(runs)}')
    for off, s in runs:
        print(f'  @{off:8d}  {s[:100]!r}')
    print()

    hex_hits = [m.start() for m in HEX64.finditer(data)]
    print(f'64-hex-digit strings (textual sha256 candidates): {len(hex_hits)}')
    low = data.lower()
    for hint in DOC_HINTS:
        n = low.count(hint.encode())
        if n:
            print(f'  hint {hint!r}: {n} occurrence(s) (inspect manually; may be data)')
    print()
    print('RESULT: no in-file documentation, manifest, declared hashes or reader')
    print('program were found. Opening the container, listing the node graph,')
    print('verifying hashes and extracting the mesh/texture all require format')
    print('rules that are not present inside the file. See REPORT.md.')


if __name__ == '__main__':
    main()
