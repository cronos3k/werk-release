"""Apply the round-1 (mesh and sound) scoring rubric mechanically.

Usage (from the repository root):

    python results/second-lab/audits/rubric_check.py RERUNS_DIR

RERUNS_DIR holds the fresh re-runs: results.json plus one folder per attempt
with clean/, payload/ and spec/ sub-folders. It is not in the repository
(see log-policy.md). The script reads the ledger, measures four facts per
attempt, derives a verdict from rubric.md, and prints one row per attempt.
It exits 1 if any derived verdict differs from the ledger's corrected_verdict.
Python 3 standard library only.
"""
import json
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEDGER = HERE.parent / 'ledger' / 'attempts.jsonl'
MESH_SHA = 'eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce'
SIGNAL = re.compile(r'mismatch|fail|error|computed|expected|corrupt|invalid|bad|differ|!=', re.I)
TEXT_SUFFIXES = ('.md', '.txt', '.json', '.csv', '.log')


def local(path_text, runs):
    """Map a recorded scratch path onto RERUNS_DIR."""
    parts = re.split(r'[\\/]', path_text)
    for i, part in enumerate(parts):
        if re.match(r'\d\d-', part):
            return runs.joinpath(*parts[i:])
    return Path(path_text)


def text_of(folder):
    """Program output plus every text file the program wrote."""
    out = []
    for name in ('stdout.txt', 'stderr.txt'):
        f = folder / '_harness' / name
        if f.exists():
            out.append(f.read_text(encoding='utf-8', errors='replace'))
    for f in sorted(folder.rglob('*')):
        if f.is_file() and f.suffix.lower() in TEXT_SUFFIXES and '_harness' not in f.parts:
            out.append(f.read_text(encoding='utf-8', errors='replace'))
    return '\n'.join(out)


def names_damage(run, runs):
    """True if a line of output names the damaged file next to an error signal."""
    target = run.get('damaged_file')
    if not target:
        return None
    base = target.split('/')[-1]
    text = text_of(local(run['scratch'], runs))
    return any(base in line and SIGNAL.search(line) for line in text.splitlines())


def measure(result, runs):
    clean = result['runs']['clean']
    folder = local(clean['scratch'], runs)
    werk = next(folder.glob('*.werk'))
    manifest = json.loads(zipfile.ZipFile(werk).read('MANIFEST.json'))
    nodes = [n['node_id'] for n in manifest['nodes']]
    text = text_of(folder)
    listed = sum(1 for n in nodes if re.search(r'(?<![\w-])' + re.escape(n) + r'(?![\w-])', text))
    extracted = clean.get('extracted_intact_payloads', [])
    mesh = 'geometry/game.glb' in extracted or MESH_SHA in clean.get('output_hashes', {}).values()
    sound = any(p.endswith('.wav') for p in extracted)
    return {
        'mesh': mesh,
        'sound': sound,
        'listed': listed,
        'nodes': len(nodes),
        'damage_payload_named': names_damage(result['runs'].get('payload') or {}, runs),
        'damage_spec_named': names_damage(result['runs'].get('spec') or {}, runs),
    }


def verdict(m):
    if not (m['mesh'] or m['sound']):
        return 'FAIL'
    if not (m['mesh'] and m['sound']):
        return 'PARTIAL'
    if m['listed'] == m['nodes'] and m['damage_payload_named'] and m['damage_spec_named']:
        return 'PASS'
    return 'PARTIAL'


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    runs = Path(sys.argv[1])
    results = {r['attempt_id']: r for r in json.loads((runs / 'results.json').read_text())}
    ledger = [json.loads(s) for s in LEDGER.read_text(encoding='utf-8').splitlines()]
    rows, differ = [], 0
    for row in ledger:
        # Round-1 attempts only. Three author envelope rows carry task "mini"
        # (the fixture name), so the prompt file decides.
        if row['task'] not in ('mini', 'mesh/sound') or row['attempt_id'] not in results:
            continue
        if 'envelope' in (row.get('prompt_file') or ''):
            continue
        m = measure(results[row['attempt_id']], runs)
        derived = verdict(m)
        same = derived == row['corrected_verdict']
        differ += not same
        rows.append(dict(attempt_id=row['attempt_id'], original=row['original_verdict'],
                         ledger=row['corrected_verdict'], derived=derived, agrees=same, **m))
    for r in rows:
        print('%-48s ledger %-8s derived %-8s mesh %-5s sound %-5s listed %2d/%-2d damage %s/%s %s' % (
            r['attempt_id'], r['ledger'], r['derived'], r['mesh'], r['sound'], r['listed'], r['nodes'],
            r['damage_payload_named'], r['damage_spec_named'], '' if r['agrees'] else 'DIFFERS'))
    print('%d attempts, %d differ from the ledger' % (len(rows), differ))
    (HERE / 'rubric-check.json').write_text(json.dumps(rows, indent=1) + '\n', encoding='utf-8')
    sys.exit(1 if differ else 0)


if __name__ == '__main__':
    main()
