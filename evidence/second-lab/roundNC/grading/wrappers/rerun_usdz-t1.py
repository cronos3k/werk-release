# argv wrapper for usdz-t1 (grading deviation D1, see RESULTS-NC.md)
import os, shutil, subprocess, sys
SRC = 'D:\\gauntlet-sealed\\nc-20261011-1543\\usdz-t1\\crate_probe.py'
ARGV = ['crate-nc-v1.usdz']
dst = os.path.basename(SRC)
shutil.copyfile(SRC, dst)
sys.stdout.flush()
p = subprocess.run([sys.executable, "-I", "-X", "utf8", dst] + ARGV)
sys.exit(p.returncode)
