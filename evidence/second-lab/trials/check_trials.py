"""Re-run the retained second-lab trial programs and check their output bytes.

Usage (from the repository root, Python 3.10 or later, standard library only):

    python results/second-lab/trials/check_trials.py [--fixtures DIR] [TRIAL ...]

DIR holds crate-v1.werk and gsplat-v1.werk (tools/fetch_fixtures.py or the
fixtures-v1 release). mini-v1.werk is taken from gauntlet/roundOW/.
Each fixture must hash to the pin in batch2/FIXTURE-SHA256.txt.

For each trial the program and its sibling files are copied into a fresh
temporary folder with only the fixture, then run with the recorded arguments.
Checks:
  round 1  : an output file has the declared digest of the primary mesh, and
             an output file has a declared digest of a primary sound .wav.
  envelope : the output gives the decoded values of both pose records.
  gsplat   : a CSV in the output has all 281,498 points, and every row equals
             the package's float32 positions and 8-bit colours.
This checks bytes only. The listing and damage clauses are in
../audits/rubric.md.
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / 'gauntlet' / 'roundGF'))
from grade_gsplat import envelope, section  # noqa: E402

# trial: (folder, program, arguments, fixture, task)
TRIALS = {
    'r1-t1': ('batch1/r1-t1', 'tools/werk_reader.py', ['mini-v1.werk', 'out'], 'mini-v1.werk', 'round1'),
    'r1-t2': ('batch1/r1-t2', 'werk_open.py', ['mini-v1.werk', 'extracted'], 'mini-v1.werk', 'round1'),
    'r1-t3': ('batch1/r1-t3', 'werk_reader.py', ['mini-v1.werk', 'extracted'], 'mini-v1.werk', 'round1'),
    'env-t1': ('batch1/env-t1', 'tools/werk_inspect.py', ['mini-v1.werk'], 'mini-v1.werk', 'envelope'),
    'xv-t1': ('batch2/xv-t1', 'werk_open.py', ['crate-v1.werk', 'extracted'], 'crate-v1.werk', 'round1'),
    'xv-t2': ('batch2/xv-t2', 'werk_reader.py', ['crate-v1.werk', 'extracted', '--log', 'run.log'], 'crate-v1.werk', 'round1'),
    'xv-t3': ('batch2/xv-t3', 'werk_reader.py', ['crate-v1.werk', '--out', 'extracted'], 'crate-v1.werk', 'round1'),
    # The splat programs write points.csv only with --out (their REPORT.md gives this command).
    'splat-t1': ('batch2/splat-t1', 'scripts/werk_inspect.py', ['gsplat-v1.werk', '--out', 'out'], 'gsplat-v1.werk', 'gsplat'),
    'splat-t2': ('batch2/splat-t2', 'mytools/werk_inspect.py', ['gsplat-v1.werk', '--out', 'output'], 'gsplat-v1.werk', 'gsplat'),
    'env-t2': ('batch2/env-t2', 'tools/werk_inspect.py', ['mini-v1.werk'], 'mini-v1.werk', 'envelope'),
    'env-t3': ('batch2/env-t3', 'tools/werkread.py', ['mini-v1.werk'], 'mini-v1.werk', 'envelope'),
}
# Decoded from poses/rest.wkrp in mini-v1.werk (criteria-2026-10-05.md, task T2).
POSE_VALUES = ['0.62', '0.38', '0.25', '0.105', '0.7071']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pins():
    out = {}
    for line in (HERE / 'batch2' / 'FIXTURE-SHA256.txt').read_text().splitlines():
        digest, path = line.split(None, 1)
        out[path.strip('*').split('/')[-1]] = digest
    return out


def declared_primary(fixture):
    m = json.loads(zipfile.ZipFile(fixture).read('MANIFEST.json'))
    nodes = {n['node_id']: n for n in m['nodes']}
    def files(node_id):
        n = nodes[node_id]
        v = next(v for v in n['versions'] if v['v'] == n.get('active', 1))
        return v['files']
    mesh = {f['sha256'] for f in files(m['primary']['mesh'])}
    sound = {f['sha256'] for f in files(m['primary']['sound']) if f['path'].endswith('.wav')}
    return mesh, sound


def output_text(folder, stdout):
    parts = [stdout]
    for f in folder.rglob('*'):
        if f.is_file() and f.suffix.lower() in ('.md', '.txt', '.json', '.log') and f.stat().st_size < 5_000_000:
            parts.append(f.read_text(encoding='utf-8', errors='replace'))
    return '\n'.join(parts)


def check_round1(folder, fixture):
    mesh, sound = declared_primary(fixture)
    digests = {sha(f) for f in folder.rglob('*') if f.is_file() and f.suffix != '.werk'}
    ok_mesh, ok_sound = bool(mesh & digests), bool(sound & digests)
    return ok_mesh and ok_sound, 'mesh %s, sound %s' % ('match' if ok_mesh else 'MISSING', 'match' if ok_sound else 'MISSING')


def check_envelope(folder, fixture, stdout):
    text = output_text(folder, stdout)
    missing = [v for v in POSE_VALUES if v not in text]
    return not missing, 'pose values ' + ('all present' if not missing else 'missing ' + ', '.join(missing))


def check_gsplat(folder, fixture):
    z = zipfile.ZipFile(fixture)
    pc = z.read('points/plush-dc.wkpc')
    _, _, ph = envelope(pc)
    _, posb = section(pc, ph, 'position')
    _, colb = section(pc, ph, 'color')
    count = ph['count']
    for f in sorted(folder.rglob('*.csv')):
        with open(f, newline='', encoding='utf-8') as fh:
            rows = list(csv.reader(fh))
        header, body = rows[0], rows[1:]
        if len(body) != count:
            continue
        cols = [c.strip().lower() for c in header]
        xi = cols.index('x')
        ci = next((i for i, c in enumerate(cols) if c in ('r_u8', 'r', 'red')), None)
        bad = 0
        for k, row in enumerate(body):
            want = struct.unpack_from('<3f', posb, 12 * k)
            got = tuple(float(v) for v in row[xi:xi + 3])
            if any(struct.unpack('<f', struct.pack('<f', g))[0] != w for g, w in zip(got, want)):
                bad += 1
            elif ci is not None and tuple(int(float(v)) for v in row[ci:ci + 3]) != tuple(colb[3 * k:3 * k + 3]):
                bad += 1
        return bad == 0, '%s: %d rows, %d differ' % (f.relative_to(folder).as_posix(), len(body), bad)
    return False, 'no CSV with %d rows' % count


def run(trial, fixtures):
    folder, program, argv, fixture_name, task = TRIALS[trial]
    src = HERE / folder
    fixture = fixtures[fixture_name]
    with tempfile.TemporaryDirectory(prefix='werk-trial-') as tmp:
        work = Path(tmp)
        for f in src.rglob('*'):
            if f.is_file() and f.name not in ('FILES.tsv', 'REPORT.md', 'claude-result.json'):
                dest = work / f.relative_to(src)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
        for d in ('out', 'output', 'extracted'):
            shutil.rmtree(work / d, ignore_errors=True)
        shutil.copy2(fixture, work / fixture_name)
        env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
        p = subprocess.run([sys.executable, program] + argv, cwd=work, env=env,
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1800)
        (work / fixture_name).unlink()
        if task == 'round1':
            ok, detail = check_round1(work, fixture)
        elif task == 'envelope':
            ok, detail = check_envelope(work, fixture, p.stdout)
        else:
            ok, detail = check_gsplat(work, fixture)
        return ok, p.returncode, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fixtures', default=str(REPO / 'fixtures'))
    ap.add_argument('trials', nargs='*', default=list(TRIALS))
    a = ap.parse_args()
    want = pins()
    fixtures = {'crate-v1.werk': Path(a.fixtures) / 'crate-v1.werk',
                'gsplat-v1.werk': Path(a.fixtures) / 'gsplat-v1.werk',
                'mini-v1.werk': REPO / 'gauntlet' / 'roundOW' / 'mini-v1.werk'}
    for name, path in fixtures.items():
        if not path.exists():
            sys.exit('missing fixture %s (see --fixtures)' % path)
        if sha(path) != want[name]:
            sys.exit('fixture %s does not match its pin %s' % (path, want[name]))
    passed = 0
    for t in a.trials:
        ok, rc, detail = run(t, fixtures)
        passed += ok
        print('%-9s %-4s exit %-3s %s' % (t, 'PASS' if ok else 'FAIL', rc, detail), flush=True)
    print('%d of %d trials reproduce their output bytes' % (passed, len(a.trials)))
    sys.exit(0 if passed == len(a.trials) else 1)


if __name__ == '__main__':
    main()
