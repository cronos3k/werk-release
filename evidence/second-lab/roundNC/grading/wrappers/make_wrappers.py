# Writes one argv wrapper per trial. The frozen grade_nc.py --rerun runs "python <prog>" with no
# arguments. Each wrapper copies the agent's final program (read-only source) into the clean
# re-run dir (its cwd) and runs it with the argv its REPORT.md states. Exit code and
# stdout/stderr are passed through unchanged, so grade_nc.py grades the agent program's run.
import os
T = r"D:\gauntlet-sealed\nc-20261011-1543"
PROGS = {
    "werk-t1": ("werk_reader.py", ["mini-v1.werk", "extracted"]),
    "werk-t2": ("werkread.py", ["mini-v1.werk", "out"]),
    "werk-t3": ("werk_reader.py", ["mini-v1.werk", "--out", "extracted"]),
    "fbx-t1": ("fbx_extract.py", ["crate-nc-v1.fbx", "extracted"]),
    "fbx-t2": (r"tools\crate_reader.py", ["crate-nc-v1.fbx", "out"]),
    "fbx-t3": (r"tools\fbxpkg.py", ["crate-nc-v1.fbx", "extracted"]),
    "gltf-t1": (r"tools\crate_reader.py", [".", "extracted"]),
    "gltf-t2": (r"tools\crate_reader.py", [".", "out"]),
    "gltf-t3": ("crate_reader.py", [".", "out"]),
    "usdz-t1": ("crate_probe.py", ["crate-nc-v1.usdz"]),
    "usdz-t2": ("usdz_tool.py", ["crate-nc-v1.usdz", "extracted"]),
    "usdz-t3": (r"tools\inspect_usdz.py", ["crate-nc-v1.usdz", "extracted"]),
}
TPL = '''# argv wrapper for {trial} (grading deviation D1, see RESULTS-NC.md)
import os, shutil, subprocess, sys
SRC = {src!r}
ARGV = {argv!r}
dst = os.path.basename(SRC)
shutil.copyfile(SRC, dst)
sys.stdout.flush()
p = subprocess.run([sys.executable, "-I", "-X", "utf8", dst] + ARGV)
sys.exit(p.returncode)
'''
here = os.path.dirname(os.path.abspath(__file__))
for t, (prog, argv) in PROGS.items():
    src = os.path.join(T, t, prog)
    assert os.path.isfile(src), src
    with open(os.path.join(here, "rerun_%s.py" % t), "w", encoding="utf-8", newline="\n") as f:
        f.write(TPL.format(trial=t, src=src, argv=argv))
print("ok", len(PROGS))
