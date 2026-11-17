"""ue_python_gate.py -- runs INSIDE the Unreal editor (`-run=pythonscript`).

    UnrealEditor-Cmd.exe <project> -run=pythonscript -script=<this file> ...
    (job file named by the environment variable WERK_UE_JOB)

For every fixture in the job: import it with WerkLink's Python entry point
(`unreal.WerkLinkScripting.import_werk`), export every asset the import
created back to a .werk (`export_werk`, spec/ and loaders/ embedded from the
job's repo), and re-import that export. Everything WerkLink returns is written
to the job's result file as JSON; this script decides nothing -- the outer
gate (gate.py) judges it with the release readers.
"""

import json
import os
import time
import traceback

import unreal

JOB = os.environ.get("WERK_UE_JOB", "")


def main():
    job = json.load(open(JOB, "r", encoding="utf-8"))
    out = {"engine": unreal.SystemLibrary.get_engine_version(), "fixtures": [], "error": None}
    lib = unreal.WerkLinkScripting
    for fx in job["fixtures"]:
        row = {"name": fx["name"], "path": fx["path"]}
        try:
            t0 = time.time()
            imp = json.loads(lib.import_werk(fx["path"], "/Game/WerkPy/" + fx["name"], True, ""))
            row["import_seconds"] = round(time.time() - t0, 2)
            row["import"] = imp
            assets = imp.get("created_assets") or []
            if assets:
                dst = os.path.join(job["out_dir"], fx["name"] + "-ue.werk").replace("\\", "/")
                if os.path.isfile(dst):
                    os.remove(dst)
                t0 = time.time()
                exp = json.loads(lib.export_werk(dst, assets, job["spec"],
                                                 imp.get("entity_name") or fx["name"], False))
                row["export_seconds"] = round(time.time() - t0, 2)
                row["export"] = exp
                if os.path.isfile(dst):
                    t0 = time.time()
                    rt = json.loads(lib.import_werk(dst, "/Game/WerkPyRT/" + fx["name"], True, ""))
                    row["reimport_seconds"] = round(time.time() - t0, 2)
                    row["reimport"] = rt
        except Exception:
            row["exception"] = traceback.format_exc()
        out["fixtures"].append(row)
        unreal.log("W5C-GATE %s done" % fx["name"])
    with open(job["result"], "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    unreal.log("W5C-GATE result written: %s" % job["result"])


try:
    main()
except Exception:
    with open(json.load(open(JOB))["result"], "w", encoding="utf-8") as fh:
        json.dump({"error": traceback.format_exc()}, fh)
    raise
