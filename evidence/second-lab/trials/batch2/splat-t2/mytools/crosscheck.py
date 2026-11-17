"""Two extra checks, no package code executed:
 (a) my envelope decoder against spec/examples/gsplat.example.wkgs, whose
     decoded values are printed in spec/examples/gsplat.example.hex.txt;
 (b) the WKGS means / WKPC colours against the raw source .splat, using only
     the 32-byte record table printed in splat_to_ply.py's docstring
     (pos f32x3 @0, scale f32x3 @12, rgba u8 @24, rot u8 @28)."""
import sys, zipfile, struct
sys.path.insert(0, sys.argv[2])          # my own tools dir, for werk_inspect
import werk_inspect as W

z = zipfile.ZipFile(sys.argv[1])

# (a)
ex = memoryview(z.read("spec/examples/gsplat.example.wkgs"))
magic, ver, h, sec = W.read_envelope(ex, "example")
m = list(W.column(ex, sec["means"], 3))
s = list(W.column(ex, sec["scales"], 3))
r = list(W.column(ex, sec["rotations"], 4))
o = list(W.column(ex, sec["opacities"], 1))
dc = list(W.column(ex, sec["sh-dc"], 3))
rest = list(W.column(ex, sec["sh-rest"], 3))
assert (magic, ver, h["count"], h["sh_degree"], h["payload_origin"]) == ("WKGS", 1, 3, 1, 800)
assert m == [0, 0, 0, 0.5, 0.25, -0.5, -0.5, 1.0, 0.25], m
assert s == [0.25, 0.125, 0.25, 0.0625, 0.0625, 0.5, 0.5, 0.25, 0.0625], s
assert r == [1, 0, 0, 0, 0.5, 0.5, 0.5, 0.5, 0, 1, 0, 0], r
assert o == [1, 0.5, 0], o
assert dc == [1, 0, -1, 0, 0.5, 0.25, -1, -0.5, 0.25], dc
assert rest[:9] == [0.5, 0.25, 0.125, -0.5, 0.25, 0.0, 0.0, -0.25, 0.5], rest[:9]
rgb = [round(min(1, max(0, 0.5 + W.C0 * v)), 6) for v in dc]
assert rgb == [0.782095, 0.5, 0.217905, 0.5, 0.641047, 0.570524, 0.217905, 0.358953, 0.570524], rgb
print("(a) example WKGS decodes to exactly the values in gsplat.example.hex.txt")

# (b)
sp = z.read("recipe/inputs/plush.splat")
n = len(sp) // 32
assert len(sp) % 32 == 0
wk = memoryview(z.read("splats/plush.wkgs"))
_, _, gh, gsec = W.read_envelope(wk, "wkgs")
pc = memoryview(z.read("points/plush-dc.wkpc"))
_, _, ph, psec = W.read_envelope(pc, "wkpc")
means = bytes(wk[gsec["means"]["offset"]:gsec["means"]["offset"] + gsec["means"]["size"]])
cols = bytes(pc[psec["color"]["offset"]:psec["color"]["offset"] + psec["color"]["size"]])
sp_pos = b"".join(sp[32 * i:32 * i + 12] for i in range(n))
sp_rgb = b"".join(sp[32 * i + 24:32 * i + 27] for i in range(n))
print("(b) .splat records: %d; WKGS count %d" % (n, gh["count"]))
print("    WKGS means == .splat positions, byte for byte: %s" % (sp_pos == means))
print("    WKPC colour bytes == .splat r,g,b bytes, byte for byte: %s" % (sp_rgb == cols))
diff = sum(1 for a, b in zip(sp_rgb, cols) if a != b)
print("    differing colour bytes: %d of %d" % (diff, len(cols)))
alpha = [sp[32 * i + 27] for i in range(n)]
print("    .splat alpha==0: %d, alpha==255: %d (recipe alpha_clamped_count 33401)"
      % (alpha.count(0), alpha.count(255)))
