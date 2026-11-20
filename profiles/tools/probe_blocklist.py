#!/usr/bin/env python3
"""probe_blocklist.py -- validate the rich-document/1 fixture's inflated blocks array against the
profile's `$defs/BlockList` with werkc's JSON Schema validator.

    python profiles/tools/probe_blocklist.py --werkc PATH --out DIR

werkc validates a node's PAYLOAD file against the schema the manifest names; the blocks array
of a core.text.blocks node is not its payload (the payload is the header), so werkc does not
reach it in the fixture. This probe writes two throw-away packages into DIR: one carrying the
fixture's inflated array as the payload of an `x.probe.blocklist` node whose schema is
`{"$ref": "#/$defs/BlockList"}` over the profile's own definitions, and a negative control with
one run length made a string. Expected: the first verifies with 0 errors, the second has the
probe node dead with `payload-schema-invalid`. Exit 0 when both hold.
"""
import argparse
import json
import os
import subprocess
import sys
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import profilekit as K  # noqa: E402


def build(schema, data, out):
    probe = {"$schema": schema.get("$schema"), "$id": "https://werk.format/spec/schemas/x.probe.blocklist.schema.json",
             "$ref": "#/$defs/BlockList", "$defs": schema["$defs"]}
    pp = K.ProfilePackage("rich-document", "probe", summary="probe", readme_text="probe readme text\n")
    pp.w.add_spec_file("spec/schemas/x.probe.blocklist.schema.json", (json.dumps(probe) + "\n").encode(),
                       "application/schema+json")
    pp.w.add_node("x-probe", "x.probe.blocklist", [pp.w.file("probe/blocks.json", data, "application/json")],
                  note="The inflated blocks array, to validate against BlockList.")
    pp.w.set_schema("x.probe.blocklist", "spec/schemas/x.probe.blocklist.schema.json")
    doc = {"schema_version": 1, "body": [], "bodyNextId": 1, "finalSection": {}, "stories": [], "noteSeparators": [],
           "media": []}
    pp.w.add_node("document", "core.text.document", [pp.w.file("document/document.json", K.cjson(doc), "application/json")],
                  note="Empty structure for the probe.")
    pp.w.set_primary("document", "document")
    pp.write(out, "Probe: validate the fixture's blocks array.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--werkc", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--fixture", default=os.path.join(PROFILES, "fixtures", "rich-document-v1.werk"))
    a = ap.parse_args()
    blocks = zlib.decompress(zipfile.ZipFile(a.fixture).read("text/body-000001.blocks.zlib"))
    schema = json.loads(open(os.path.join(PROFILES, "rich-document", "spec", "schemas", "core.text.blocks.schema.json"),
                             encoding="utf-8").read())
    os.makedirs(a.out, exist_ok=True)
    good, bad = os.path.join(a.out, "blocklist-probe.werk"), os.path.join(a.out, "blocklist-negative.werk")
    build(schema, blocks, good)
    neg = json.loads(blocks)
    neg[0]["runs"][0]["len"] = "x"
    build(schema, json.dumps(neg).encode("utf-8"), bad)
    r1 = subprocess.run([a.werkc, "verify", good], capture_output=True, text=True)
    r2 = subprocess.run([a.werkc, "verify", bad], capture_output=True, text=True)
    ok1 = r1.returncode == 0 and "payload-schema-invalid" not in r1.stdout
    ok2 = r2.returncode == 1 and "payload-schema-invalid node=x-probe" in r2.stdout
    print("fixture blocks array valid against BlockList: %s (werkc exit %d)" % (ok1, r1.returncode))
    print("negative control rejected: %s (werkc exit %d)" % (ok2, r2.returncode))
    return 0 if ok1 and ok2 else 1


if __name__ == "__main__":
    sys.exit(main())
