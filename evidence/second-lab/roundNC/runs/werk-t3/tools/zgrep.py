"""Regex-search one entry of the container (in memory). usage: zgrep.py <container> <entry> <regex>"""
import sys, re, zipfile
sys.stdout.reconfigure(encoding='utf-8')
z = zipfile.ZipFile(sys.argv[1])
rx = re.compile(sys.argv[3])
for i, line in enumerate(z.read(sys.argv[2]).decode('utf-8', 'replace').split('\n')):
    if rx.search(line):
        print(f'{i + 1:5d}| {line[:220]}')
