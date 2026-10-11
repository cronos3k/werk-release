# Independent check: does each control OBJ's vertex list equal the body sub-mesh (Cube.020)
# of the frozen Tier 2 dump, value by value at float32, in order?
import struct
D = r"D:\werk\nc-grading\frozen-504a9ac\gauntlet\roundNC\expectations-data"
def dump(n): b = open(D + "\\" + n, "rb").read(); return struct.unpack("<%df" % (len(b)//4), b)
f32 = lambda x: struct.unpack("<f", struct.pack("<f", x))[0]
body = {"fbx": dump("fbx-mesh-dump.f32")[596*3:(596+3706)*3], "usdz": dump("usdz-mesh-dump.f32")[596*3:(596+3706)*3],
        "gltf": dump("gltf-mesh-dump.f32")[622*3:(622+3731)*3]}
S = r"D:\werk\nc-grading\scratch"
objs = {"fbx-t1": r"fbx-t1\extracted\wooden_crate_01.obj", "fbx-t2": r"fbx-t2\out\wooden_crate_01.obj",
        "fbx-t3": r"fbx-t3\extracted\wooden_crate_01.obj", "gltf-t1": r"gltf-t1\extracted\primary_mesh.obj",
        "gltf-t2": r"gltf-t2\out\primary_mesh_wooden_crate_01.obj", "gltf-t3": r"gltf-t3\out\wooden_crate_01.obj",
        "usdz-t2": r"usdz-t2\extracted\root_wooden_crate_01_Cube_020.obj"}
for t, rel in objs.items():
    v = []
    for line in open(S + "\\" + rel, encoding="utf-8", errors="replace"):
        if line.startswith("v "):
            v += [f32(float(x)) for x in line.split()[1:4]]
    exp = body[t.split("-")[0]]
    diff = sum(1 for a, b in zip(v, exp) if a != b)
    maxd = max((abs(a - b) for a, b in zip(v, exp)), default=None)
    print(t, "verts", len(v)//3, "expected", len(exp)//3, "values differing at f32:", diff, "max abs diff", maxd)
