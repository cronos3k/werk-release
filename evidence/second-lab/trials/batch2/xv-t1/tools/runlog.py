# Run werk_open.main and save its stdout plus exit code to a log file.
import sys, os, io, contextlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import werk_open as W
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = W.main(['werk_open.py', sys.argv[1], sys.argv[2]])
with open(sys.argv[3], 'w', encoding='utf-8') as f:
    f.write(buf.getvalue())
    f.write('\nexit status: %d\n' % rc)
print('exit status', rc)
