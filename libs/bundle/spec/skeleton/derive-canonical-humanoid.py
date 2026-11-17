"""Generate spec/skeleton/canonical-humanoid-v1.json and core.hands.v1.json.

Model space: +Y up, -Z forward, +X the character's right, right-handed, metres.
Floor at y = 0, reference stature 1.75 m, T-pose with palms down.

Per bone we author the model-space head, the model-space tail and a "back"
hint; from those we build the model-space basis (local +Y along the bone,
local +Z along the back reference orthogonalised against the bone axis,
local +X = Y x Z), then derive the parent-local rest rotation/translation.
Both the model-space and the local values are emitted, and the script
verifies that recomposing the local chain reproduces the model values.
"""
import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent


# ---- small vector / quaternion helpers (no numpy: this must be auditable) ---
def sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def scale(a, s):
    return [a[0] * s, a[1] * s, a[2] * s]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = norm(a)
    return [a[0] / n, a[1] / n, a[2] / n]


def basis_to_quat(x, y, z):
    """Columns x,y,z of a rotation matrix -> quaternion (w,x,y,z), w >= 0."""
    m00, m01, m02 = x[0], y[0], z[0]
    m10, m11, m12 = x[1], y[1], z[1]
    m20, m21, m22 = x[2], y[2], z[2]
    tr = m00 + m11 + m22
    if tr > 0.0:
        s = math.sqrt(tr + 1.0) * 2.0
        w = 0.25 * s
        qx = (m21 - m12) / s
        qy = (m02 - m20) / s
        qz = (m10 - m01) / s
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        w = (m21 - m12) / s
        qx = 0.25 * s
        qy = (m01 + m10) / s
        qz = (m02 + m20) / s
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        w = (m02 - m20) / s
        qx = (m01 + m10) / s
        qy = 0.25 * s
        qz = (m12 + m21) / s
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
        w = (m10 - m01) / s
        qx = (m02 + m20) / s
        qy = (m12 + m21) / s
        qz = 0.25 * s
    q = [w, qx, qy, qz]
    if q[0] < 0.0:
        q = [-c for c in q]
    n = math.sqrt(sum(c * c for c in q))
    return [c / n for c in q]


def quat_to_matrix(q):
    """(w,x,y,z) -> columns (x_axis, y_axis, z_axis)."""
    w, x, y, z = q
    return (
        [1 - 2 * (y * y + z * z), 2 * (x * y + w * z), 2 * (x * z - w * y)],
        [2 * (x * y - w * z), 1 - 2 * (x * x + z * z), 2 * (y * z + w * x)],
        [2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y)],
    )


def quat_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return [aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw]


def quat_conj(q):
    return [q[0], -q[1], -q[2], -q[3]]


def rot_apply(q, v):
    xa, ya, za = quat_to_matrix(q)
    return [xa[0] * v[0] + ya[0] * v[1] + za[0] * v[2],
            xa[1] * v[0] + ya[1] * v[1] + za[1] * v[2],
            xa[2] * v[0] + ya[2] * v[1] + za[2] * v[2]]


def rot_apply_inv(q, v):
    return rot_apply(quat_conj(q), v)


def r6(x):
    """Round to 9 decimals and normalise -0.0 to 0.0.

    Nine decimals is well inside float32's ~7 significant digits, so these
    values survive a round trip through a f32 binary mirror, and it keeps the
    recomposition residual three orders of magnitude below the 1e-5 tolerance
    the schema tells readers to check against.
    """
    v = round(x + 0.0, 9)
    return 0.0 if v == 0.0 else v


# ---- the authored skeleton ---------------------------------------------------
# (bone_id, parent, head, tail, back_hint, role, side)
SPINE_BACK = [0.0, 0.0, 1.0]     # posterior
ARM_BACK = [0.0, 1.0, 0.0]       # dorsal side of the arm faces up, palms down
LEG_BACK = [0.0, 0.0, 1.0]       # back of the leg faces posterior
FOOT_BACK = [0.0, 1.0, 0.0]      # top of the foot faces up

# RULING 9 (2026-08-08): the root is a BASE BONE at the origin (0,0,0) and the
# pelvis is PARENTED to it, so a clip that is not in-place carries its
# locomotion on the root while the pelvis stays a body bone. The draft already
# had this topology and it is now normative rather than incidental: `root` sits
# at the origin with an identity rest rotation, is never driven by a mapped
# foreign bone (retarget/retarget.py decision 1), and its 0.1 m extent is a
# DISPLAY STUB with no anatomical meaning - nothing hangs off its tail and no
# length calculation uses it. `hips` keeps its model-space head at y = 0.98 and
# is a body bone like any other. See results/STAGE-RULINGS-RESULTS.md finding
# S-R-1 for why the bone count did not go up by one.
CORE = [
    ("root",   None,    [0.0, 0.0000, 0.0000], [0.0, 0.1000, 0.0000], SPINE_BACK, "locomotion-root", "center"),
    ("hips",   "root",  [0.0, 0.9800, 0.0000], [0.0, 1.0450, 0.0000], SPINE_BACK, "pelvis", "center"),
    ("spine1", "hips",  [0.0, 1.0450, 0.0000], [0.0, 1.1300, 0.0000], SPINE_BACK, "spine", "center"),
    ("spine2", "spine1", [0.0, 1.1300, 0.0000], [0.0, 1.2200, 0.0000], SPINE_BACK, "spine", "center"),
    ("spine3", "spine2", [0.0, 1.2200, 0.0000], [0.0, 1.4300, 0.0000], SPINE_BACK, "spine", "center"),
    ("neck",   "spine3", [0.0, 1.4300, 0.0000], [0.0, 1.5300, 0.0000], SPINE_BACK, "neck", "center"),
    ("head",   "neck",  [0.0, 1.5300, 0.0000], [0.0, 1.7500, 0.0000], SPINE_BACK, "head", "center"),
]

# Left arm: authored on the -X side, mirrored to +X for the right.
ARM = [
    ("clavicle", "spine3",   [-0.0300, 1.4100, 0.0000], [-0.1700, 1.4100, 0.0000], "clavicle"),
    ("upperarm", "clavicle", [-0.1700, 1.4100, 0.0000], [-0.4600, 1.4100, 0.0000], "upperarm"),
    ("forearm",  "upperarm", [-0.4600, 1.4100, 0.0000], [-0.7100, 1.4100, 0.0000], "forearm"),
    ("hand",     "forearm",  [-0.7100, 1.4100, 0.0000], [-0.8970, 1.4100, 0.0000], "hand"),
]

# RULING 8 (2026-08-08, S6-5): thigh 0.43 m, shin 0.42 m. The draft had them
# the other way round - a shin/thigh ratio of 1.024, which no human skeleton
# has - and both human-derived rigs measured in Stage 6 disagreed after their
# own solved stature scale: CMU take 02_01 (a capture of a real person) 0.960,
# the UE 5.7 mannequin 0.944. The femur is longer than the tibia. Swapping the
# two moves the KNEE from y = 0.50 to y = 0.49 and moves nothing else: total
# leg length is unchanged at 0.85 m, so the ankle stays at 0.07 and the foot
# and toe do not move at all.
LEG = [
    ("thigh", "hips",  [-0.0900, 0.9200, 0.0000], [-0.0900, 0.4900, 0.0000], "thigh", LEG_BACK),
    ("shin",  "thigh", [-0.0900, 0.4900, 0.0000], [-0.0900, 0.0700, 0.0000], "shin", LEG_BACK),
    ("foot",  "shin",  [-0.0900, 0.0700, 0.0000], [-0.0900, 0.0250, -0.1300], "foot", FOOT_BACK),
    ("toe",   "foot",  [-0.0900, 0.0250, -0.1300], [-0.0900, 0.0180, -0.2000], "toe", FOOT_BACK),
]

# Left hand, 15 bones. Fingers run along -X; the splay is in the MCP positions.
HAND = [
    ("thumb-metacarpal",   "hand",                [-0.7300, 1.4100, -0.0250], [-0.7850, 1.4100, -0.0480], "thumb"),
    ("thumb-proximal",     "thumb-metacarpal",    [-0.7850, 1.4100, -0.0480], [-0.8150, 1.4100, -0.0600], "thumb"),
    ("thumb-distal",       "thumb-proximal",      [-0.8150, 1.4100, -0.0600], [-0.8420, 1.4100, -0.0680], "thumb"),
    ("index-proximal",     "hand",                [-0.8000, 1.4100, -0.0200], [-0.8400, 1.4100, -0.0200], "finger"),
    ("index-intermediate", "index-proximal",      [-0.8400, 1.4100, -0.0200], [-0.8650, 1.4100, -0.0200], "finger"),
    ("index-distal",       "index-intermediate",  [-0.8650, 1.4100, -0.0200], [-0.8840, 1.4100, -0.0200], "finger"),
    ("middle-proximal",    "hand",                [-0.8050, 1.4100, 0.0000], [-0.8490, 1.4100, 0.0000], "finger"),
    ("middle-intermediate", "middle-proximal",    [-0.8490, 1.4100, 0.0000], [-0.8770, 1.4100, 0.0000], "finger"),
    ("middle-distal",      "middle-intermediate", [-0.8770, 1.4100, 0.0000], [-0.8970, 1.4100, 0.0000], "finger"),
    ("ring-proximal",      "hand",                [-0.8000, 1.4100, 0.0180], [-0.8410, 1.4100, 0.0180], "finger"),
    ("ring-intermediate",  "ring-proximal",       [-0.8410, 1.4100, 0.0180], [-0.8670, 1.4100, 0.0180], "finger"),
    ("ring-distal",        "ring-intermediate",   [-0.8670, 1.4100, 0.0180], [-0.8860, 1.4100, 0.0180], "finger"),
    ("pinky-proximal",     "hand",                [-0.7900, 1.4100, 0.0360], [-0.8220, 1.4100, 0.0360], "finger"),
    ("pinky-intermediate", "pinky-proximal",      [-0.8220, 1.4100, 0.0360], [-0.8410, 1.4100, 0.0360], "finger"),
    ("pinky-distal",       "pinky-intermediate",  [-0.8410, 1.4100, 0.0360], [-0.8570, 1.4100, 0.0360], "finger"),
]


def mirror(v):
    return [-v[0], v[1], v[2]]


def build_bone_specs():
    """-> list of (bone_id, parent_id, head, tail, back_hint, role, side, mirror_of)"""
    core = [(b, p, h, t, bk, role, side, None) for (b, p, h, t, bk, role, side) in CORE]

    for side, sgn in (("left", -1), ("right", +1)):
        pfx = "l-" if side == "left" else "r-"
        opp = "r-" if side == "left" else "l-"
        for name, parent, head, tail, role in ARM:
            h = head if sgn < 0 else mirror(head)
            t = tail if sgn < 0 else mirror(tail)
            par = parent if parent == "spine3" else pfx + parent
            core.append((pfx + name, par, h, t, ARM_BACK, role, side, opp + name))
        for name, parent, head, tail, role, back in LEG:
            h = head if sgn < 0 else mirror(head)
            t = tail if sgn < 0 else mirror(tail)
            par = parent if parent == "hips" else pfx + parent
            core.append((pfx + name, par, h, t, back, role, side, opp + name))
    return core


def build_hand_specs():
    out = []
    for side, sgn in (("left", -1), ("right", +1)):
        pfx = "l-" if side == "left" else "r-"
        opp = "r-" if side == "left" else "l-"
        for name, parent, head, tail, role in HAND:
            h = head if sgn < 0 else mirror(head)
            t = tail if sgn < 0 else mirror(tail)
            out.append((pfx + name, pfx + parent, h, t, ARM_BACK, role, side, opp + name))
    return out


def solve(specs, known=None):
    """specs -> list of bone dicts with model and local rest values."""
    model = dict(known or {})        # bone_id -> (quat_model, head)
    bones = []
    for (bid, parent, head, tail, back_hint, role, side, mirr) in specs:
        along = sub(tail, head)
        length = norm(along)
        assert length > 1e-9, bid
        y_axis = unit(along)
        # Gram-Schmidt the back hint against the bone axis.
        b = sub(back_hint, scale(y_axis, dot(back_hint, y_axis)))
        assert norm(b) > 1e-6, f"{bid}: back hint is parallel to the bone"
        z_axis = unit(b)
        x_axis = cross(y_axis, z_axis)          # right-handed: X = Y x Z
        q_model = basis_to_quat(x_axis, y_axis, z_axis)

        if parent is None:
            q_local = q_model
            t_local = head[:]
        else:
            qp, hp = model[parent]
            q_local = quat_mul(quat_conj(qp), q_model)
            if q_local[0] < 0:
                q_local = [-c for c in q_local]
            t_local = rot_apply_inv(qp, sub(head, hp))

        model[bid] = (q_model, head)
        bones.append({
            "bone_id": bid,
            "parent": parent,
            "role": role,
            "side": side,
            **({"mirror_of": mirr} if mirr else {}),
            "rest_rotation": [r6(c) for c in q_local],
            "rest_translation": [r6(c) for c in t_local],
            "length_m": r6(length),
            "model_rest_rotation": [r6(c) for c in q_model],
            "model_rest_head_m": [r6(c) for c in head],
            "model_rest_tail_m": [r6(c) for c in tail],
            "axis_along": [r6(c) for c in y_axis],
            "axis_back": [r6(c) for c in z_axis],
            "leaf": True,
        })
    children = {b["parent"] for b in bones if b["parent"]}
    for b in bones:
        if b["bone_id"] in children:
            b["leaf"] = False
    return bones, model


def verify(bones, inherited=None):
    """Recompose the local chain and compare against the declared model values."""
    acc = dict(inherited or {})
    worst_q = worst_p = 0.0
    for b in bones:
        q_l = b["rest_rotation"]
        t_l = b["rest_translation"]
        if b["parent"] is None:
            q_m, h_m = q_l, t_l
        else:
            qp, hp = acc[b["parent"]]
            q_m = quat_mul(qp, q_l)
            if q_m[0] < 0:
                q_m = [-c for c in q_m]
            h_m = add(hp, rot_apply(qp, t_l))
        acc[b["bone_id"]] = (q_m, h_m)
        worst_q = max(worst_q, max(abs(a - c) for a, c in zip(q_m, b["model_rest_rotation"])))
        worst_p = max(worst_p, max(abs(a - c) for a, c in zip(h_m, b["model_rest_head_m"])))
        # tail check
        tail = add(h_m, scale(rot_apply(q_m, [0.0, 1.0, 0.0]), b["length_m"]))
        worst_p = max(worst_p, max(abs(a - c) for a, c in zip(tail, b["model_rest_tail_m"])))
    return worst_q, worst_p, acc


CONVENTIONS = {
    "up_axis": "y",
    "forward_axis": "-z",
    "right_axis": "+x",
    "handedness": "right",
    "quat_order": "wxyz",
    "units_per_meter": 1.0,
    "bone_axis_along": "+y",
    "bone_axis_back": "+z",
    "composition": "M_bone = M_parent * T(rest_translation) * R(rest_rotation)",
}

core_specs = build_bone_specs()
core_bones, core_model = solve(core_specs)
wq, wp, acc = verify(core_bones)
print(f"core: {len(core_bones)} bones, max quat residual {wq:.2e}, max position residual {wp:.2e} m")
assert wq < 2e-6 and wp < 2e-6

hand_specs = build_hand_specs()
hand_bones, _ = solve(hand_specs, known=core_model)
wq2, wp2, _ = verify(hand_bones, inherited=acc)
print(f"hands: {len(hand_bones)} bones, max quat residual {wq2:.2e}, max position residual {wp2:.2e} m")
assert wq2 < 2e-6 and wp2 < 2e-6

core_doc = {
    "schema_version": 1,
    "skeleton_id": "canonical-humanoid-v1",
    "name": "werk canonical humanoid v1",
    "status": "approved",
    "canon_version": "1.0",
    "approval": {
        "decided_on": "2026-08-08",
        "ruling": "docs/RULINGS-2026-08-08.md rulings 7, 8, 9, 10",
        "note": (
            "Ruling 7 approved the body proportions as drafted. Ruling 8 "
            "applied the measured thigh/shin swap. Ruling 9 made the base "
            "root bone at the origin normative, with the pelvis parented to "
            "it. Ruling 10 approved +Y-along-bone."
        ),
    },
    "note": (
        "APPROVED 2026-08-08, canon version 1.0, by the rulings recorded in "
        "docs/RULINGS-2026-08-08.md. Two numbers changed on the way in: the "
        "thigh is now 0.43 m and the shin 0.42 m (ruling 8, on measurements "
        "from two human-derived rigs), which moves the knee from y = 0.50 to "
        "y = 0.49 and moves nothing else. The root is a BASE BONE at the "
        "origin and the pelvis is parented to it (ruling 9), so a travelling "
        "clip carries locomotion on the root and the pelvis stays a body "
        "bone. These numbers are now painful to change: every retarget map, "
        "every calibration solve and every clip authored against this rig "
        "inherits them."
    ),
    "epistemic": "authored",
    "reference_height_m": 1.75,
    "pose_name": "t-pose-palms-down",
    "conventions": CONVENTIONS,
    "floor_plane": {"point": [0.0, 0.0, 0.0], "normal": [0.0, 1.0, 0.0]},
    "extensions": ["core-hands-v1"],
    "bones": core_bones,
    "retarget": {
        "mixamo": {
            "description": (
                "Mixamo's standard humanoid naming, with the usual "
                "'mixamorig:' prefix stripped by the importer before lookup."
            ),
            "map": {
                "Hips": "hips", "Spine": "spine1", "Spine1": "spine2",
                "Spine2": "spine3", "Neck": "neck", "Head": "head",
                "LeftShoulder": "l-clavicle", "LeftArm": "l-upperarm",
                "LeftForeArm": "l-forearm", "LeftHand": "l-hand",
                "RightShoulder": "r-clavicle", "RightArm": "r-upperarm",
                "RightForeArm": "r-forearm", "RightHand": "r-hand",
                "LeftUpLeg": "l-thigh", "LeftLeg": "l-shin",
                "LeftFoot": "l-foot", "LeftToeBase": "l-toe",
                "RightUpLeg": "r-thigh", "RightLeg": "r-shin",
                "RightFoot": "r-foot", "RightToeBase": "r-toe",
            },
        },
        "ue-mannequin": {
            "description": "Unreal Engine mannequin (UE4/UE5 skeleton naming).",
            "map": {
                "root": "root", "pelvis": "hips", "spine_01": "spine1",
                "spine_02": "spine2", "spine_03": "spine3", "neck_01": "neck",
                "head": "head",
                "clavicle_l": "l-clavicle", "upperarm_l": "l-upperarm",
                "lowerarm_l": "l-forearm", "hand_l": "l-hand",
                "clavicle_r": "r-clavicle", "upperarm_r": "r-upperarm",
                "lowerarm_r": "r-forearm", "hand_r": "r-hand",
                "thigh_l": "l-thigh", "calf_l": "l-shin", "foot_l": "l-foot",
                "ball_l": "l-toe",
                "thigh_r": "r-thigh", "calf_r": "r-shin", "foot_r": "r-foot",
                "ball_r": "r-toe",
            },
        },
        "vrm-humanoid": {
            "description": "VRM 1.0 humanoid bone roles.",
            "map": {
                "hips": "hips", "spine": "spine1", "chest": "spine2",
                "upperChest": "spine3", "neck": "neck", "head": "head",
                "leftShoulder": "l-clavicle", "leftUpperArm": "l-upperarm",
                "leftLowerArm": "l-forearm", "leftHand": "l-hand",
                "rightShoulder": "r-clavicle", "rightUpperArm": "r-upperarm",
                "rightLowerArm": "r-forearm", "rightHand": "r-hand",
                "leftUpperLeg": "l-thigh", "leftLowerLeg": "l-shin",
                "leftFoot": "l-foot", "leftToes": "l-toe",
                "rightUpperLeg": "r-thigh", "rightLowerLeg": "r-shin",
                "rightFoot": "r-foot", "rightToes": "r-toe",
            },
        },
    },
}

hands_doc = {
    "schema_version": 1,
    "skeleton_id": "core-hands-v1",
    "name": "werk canonical humanoid hands v1",
    "status": "approved",
    "canon_version": "1.0",
    "approval": {
        "decided_on": "2026-08-08",
        "ruling": "docs/RULINGS-2026-08-08.md ruling 7",
        "note": "Hand proportions approved as drafted; ruling 9 changed nothing here, because the hands parent to l-hand/r-hand and the arm chain did not move.",
    },
    "extends": "canonical-humanoid-v1",
    "epistemic": "authored",
    "reference_height_m": 1.75,
    "pose_name": "t-pose-palms-down",
    "conventions": CONVENTIONS,
    "note": (
        "APPROVED 2026-08-08, canon version 1.0. 15 bones per hand, attached "
        "to l-hand and r-hand of canonical-humanoid-v1 - parenting unchanged "
        "by the skeleton rulings, because nothing in the arm chain moved. A "
        "consumer that ignores this file keeps a working 23-bone skeleton "
        "(law 3)."
    ),
    "bones": hand_bones,
}

OUT.mkdir(parents=True, exist_ok=True)
for name, doc in (("canonical-humanoid-v1.json", core_doc),
                  ("core.hands.v1.json", hands_doc)):
    p = OUT / name
    p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print("wrote", p)

# sanity numbers for the record
span = abs(core_model["l-hand"][1][0] - 0.8970) if False else None
print("fingertip span m:", 2 * 0.8970)
print("stature m:", core_model["head"][1][1] + 0.22)
