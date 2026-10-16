"""Validate attempt identity, file hashes, and the mapped attempt counts."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--workspace", type=Path, default=Path("D:/werk"),
                        help="local second-lab folder; replaces <second-lab>/")
    parser.add_argument("--sealed", type=Path, default=Path("D:/gauntlet-sealed"),
                        help="sealed trial folder; replaces <second-lab>/gauntlet-sealed/")
    parser.add_argument("--scratch", type=Path,
                        help="local re-run folder; replaces <scratch>/ (default: k-results in --workspace)")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    ledger = Path(__file__).with_name("attempts.jsonl")
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line]
    problems, unavailable = [], []
    counts = Counter(row["attempt_id"] for row in rows)
    problems += ["duplicate attempt: " + name for name, count in counts.items() if count != 1]

    scratch = args.scratch or args.workspace / "k-results"
    prefixes = [("repo:", args.source_repo), ("workspace:", args.workspace),
                ("<second-lab>/gauntlet-sealed/", args.sealed),
                ("<second-lab>/", args.workspace), ("<scratch>/", scratch)]

    def resolve(value):
        value = value.replace("\\", "/")
        for prefix, base in prefixes:
            if value.startswith(prefix):
                return base / value[len(prefix):]
        return Path(value.replace("C:/Users/<user>", str(Path.home()).replace("\\", "/")))

    hashed = {}
    def verify(attempt, location, digest):
        if not location or not digest:
            unavailable.append(attempt + ": hash or location not recorded")
            return
        path = resolve(location)
        if not path.is_file():
            unavailable.append(attempt + ": file unavailable: " + location)
            return
        if path not in hashed:
            hashed[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        if hashed[path] != digest:
            problems.append(attempt + ": hash mismatch: " + location)

    for row in rows:
        for field in ["original_verdict_source", "artifact_location"]:
            if row.get(field) is None:
                unavailable.append(row["attempt_id"] + ": " + field + " not recorded")
        verify(row["attempt_id"] + " prompt", row["prompt_file"], row["prompt_sha256"])
        inputs = row.get("fixture_inputs") or [{"location": row["fixture_location"],
                                                "sha256": row["fixture_sha256"]}]
        for item in inputs:
            verify(row["attempt_id"] + " fixture", item.get("location"), item.get("sha256"))

    retained = [r for r in rows if not r["excluded"]]
    author = [r for r in retained if r["lab"] == "author"]
    second = [r for r in retained if r["lab"] == "second"]
    claims = []
    def claim(name, expected, selected):
        observed = len(selected)
        claims.append({"claim": name, "reported": expected, "ledger": observed,
                       "reproduced": observed == expected})
        if observed != expected:
            problems.append("count not reproduced: %s (%s versus %s)" % (name, expected, observed))

    for round_, expected in [("round1", 4), ("round2", 2), ("round3", 1), ("roundXV", 4),
                              ("roundSR", 2), ("roundHC", 1), ("roundGF", 4), ("roundDS", 4), ("roundOW", 22)]:
        claim("author retained attempts in " + round_, expected, [r for r in author if r["round"] == round_])
    for round_, expected in [("august", 1), ("batch1", 4), ("batch2", 7), ("negative-control", 12)]:
        claim("second-lab retained attempts in " + round_, expected, [r for r in second if r["round"] == round_])
    replication = [r for r in second if r["round"] != "negative-control"]
    claim("second-lab replication total", 12, replication)
    for task, expected in [("mesh/image", 1), ("mesh/sound", 6), ("envelope", 3), ("splat", 2)]:
        claim("second-lab replication task " + task, expected, [r for r in replication if r["task"] == task])
    claim("original comparison scope after current-input round2 reruns", 39,
          [r for r in author if r["round"] not in ("round1", "round3")])
    claim("author discarded task attempts", 5,
          [r for r in rows if r["lab"] == "author" and r["excluded"] and r["task"] != "preflight"])

    mappings_path = Path(__file__).with_name("count-statements.json")
    mappings = json.loads(mappings_path.read_text(encoding="utf-8")) if mappings_path.exists() else []
    mapping_index = {(m["source"], m["line"]): m for m in mappings}
    statement_results = []
    # A hash binds each mapping to the source statement. Changed statements require review.
    unmapped = []
    sources = [(file,args.source_repo / file) for file in
               ["paper/v2/PAPER.md", "paper/v2/NUMBERS.md", "gauntlet/RESULTS.md"]]
    sources += [("secondlab:"+file,args.workspace / "wt-secondlab" / file) for file in
                ["results/SECOND-LAB-REPLICATION.md"]]
    for file, path in sources:
        if path.exists():
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                ratio = re.search(r"\b\d+\s*(?:/|of)\s*\d+\b",line)
                count = re.search(r"\b(?:\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fourteen|fifteen)\s+(?:(?:fresh|isolated|retained|agentic|independent|standalone|recent)\s+)*(?:agents?|trials?|attempts?|models?|runs?|PASS|FAIL|PARTIAL|SUCCESS|passed|failed)\b",line,re.I)
                if (ratio or count) and re.search(r"agent|trial|attempt|model|verdict|\bPASS\b|\bFAIL\b|\bPARTIAL\b",line,re.I):
                    mapping = mapping_index.get((file, number))
                    digest = hashlib.sha256(line.encode("utf-8")).hexdigest()
                    if not mapping or mapping["statement_sha256"] != digest:
                        unmapped.append({"source": file, "line": number,
                                         "reason": "mapping absent or source statement changed"})
                    else:
                        selected = [r for r in retained if r["attempt_id"] in mapping["attempt_ids"]]
                        if len(selected) != len(mapping["attempt_ids"]):
                            problems.append("unknown attempt in statement mapping: %s:%s" % (file, number))
                        ratios = [(int(a),int(b)) for a,b in re.findall(r"\b(\d+)\s*(?:/|of)\s*(\d+)\b",line)]
                        passed = sum(str(r['original_verdict']).upper().startswith(('PASS','SUCCESS')) for r in selected)
                        checks = []
                        for numerator, denominator in ratios:
                            reproduced = (mapping['kind']=='attempt or model-group count' and len(ratios)==1
                                          and denominator==len(selected) and numerator==passed)
                            model_groups = {}
                            for row in selected:
                                model_groups.setdefault(row['model'], []).append(row)
                            if mapping['kind']=='attempt or model-group count' and denominator==len(model_groups) and denominator!=len(selected):
                                first_only = ('first' in line.lower() and (len(ratios)==1 or not checks))
                                group_passes = sum(any(str(row['original_verdict']).upper().startswith(('PASS','SUCCESS'))
                                    for row in (sorted(group,key=lambda r:r['retry_index'])[:1] if first_only else group))
                                    for group in model_groups.values())
                                reproduced = numerator==group_passes
                            checks.append({'reported_numerator':numerator,'reported_denominator':denominator,
                                           'ledger_attempts':len(selected),'original_success_labels':passed,
                                           'reproduced_from_ledger':reproduced,
                                           'reason':'Original PASS/SUCCESS labels reproduce this ratio under its attempt or model-group rule.' if reproduced else mapping['reason']})
                        statement_results.append(dict(mapping, ledger_attempts=len(selected),ratio_checks=checks))
    result = {"attempts": len(rows), "retained": len(retained), "excluded": len(rows)-len(retained),
              "files_hashed": len(hashed), "problems": problems, "unavailable": unavailable,
              "mapped_counts": claims, "count_statements": statement_results,
              "counts_not_reproduced_from_ledger": [dict(source=s['source'],line=s['line'],**c)
                  for s in statement_results for c in s['ratio_checks'] if not c['reproduced_from_ledger']],
              "count_statements_requiring_mapping": unmapped}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("attempts=%d retained=%d excluded=%d hashed_files=%d" %
          (len(rows), len(retained), len(rows)-len(retained), len(hashed)))
    print("errors=%d unavailable_fields_or_files=%d count_statements_requiring_mapping=%d" %
          (len(problems), len(unavailable), len(unmapped)))
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
