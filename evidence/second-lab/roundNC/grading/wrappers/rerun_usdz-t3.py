# argv wrapper for usdz-t3 (grading deviation D1, see RESULTS-NC.md)
import os, shutil, subprocess, sys
SRC = 'D:\\gauntlet-sealed\\nc-20261011-1543\\usdz-t3\\tools\\inspect_usdz.py'
ARGV = ['crate-nc-v1.usdz', 'extracted']
dst = os.path.basename(SRC)
shutil.copyfile(SRC, dst)
sys.stdout.flush()
p = subprocess.run([sys.executable, "-I", "-X", "utf8", dst] + ARGV)
sys.exit(p.returncode)
