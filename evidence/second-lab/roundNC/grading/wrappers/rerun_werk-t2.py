# argv wrapper for werk-t2 (grading deviation D1, see RESULTS-NC.md)
import os, shutil, subprocess, sys
SRC = 'D:\\gauntlet-sealed\\nc-20261011-1543\\werk-t2\\werkread.py'
ARGV = ['mini-v1.werk', 'out']
dst = os.path.basename(SRC)
shutil.copyfile(SRC, dst)
sys.stdout.flush()
p = subprocess.run([sys.executable, "-I", "-X", "utf8", dst] + ARGV)
sys.exit(p.returncode)
