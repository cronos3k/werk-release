# Hash every file in the batch folder (read-only), to prove grading did not modify it.
import hashlib, os, sys
T = r"D:\gauntlet-sealed\nc-20261011-1543"
out = []
for root, dirs, files in os.walk(T):
    dirs.sort()
    for n in sorted(files):
        p = os.path.join(root, n)
        st = os.stat(p)
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        out.append("%s %d %d %s" % (h, st.st_size, int(st.st_mtime), os.path.relpath(p, T)))
open(sys.argv[1], "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
print(len(out), "files; newest mtime", max(int(l.split()[2]) for l in out))
