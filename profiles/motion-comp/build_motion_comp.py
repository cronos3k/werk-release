#!/usr/bin/env python3
"""build_motion_comp.py -- the motion-comp/1 release fixture, written deterministically with the
release library (profiles/tools/profilekit.py).

The project "Beacon sweep": two solids and one composition (320 x 180 px, 25 fps, 2 s) with two
layers, front first:

  layer-4 "Beacon"  shows solid item-2 (40 x 40, beacon yellow); its keyframes:
                      position  3 keys in the layer's keyframe-tracks node (WKX3), Linear, then
                                Hold (the beacon jumps at 1.5 s)
                      rotation  2 keys in the tracks node, Bezier with eases (0 -> 360 deg)
                      opacity   2 keys inline in the layer JSON, Linear (fade in over 0.4 s)
  layer-5 "Night"   shows solid item-1 (the full frame, night blue), static

plus the reference reader as a core.tool node. No poster or strip is written (optional in the
profile: this builder renders no pictures).

usage: build_motion_comp.py [--out profiles/fixtures/motion-comp-v1.werk]
"""
import argparse
import os
import struct
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import profilekit as K  # noqa: E402

TPS = 254016000000
FPS = 25
DUR = 2 * TPS


def sec(s):
    return int(round(s * TPS))


def val(t, v):
    return OrderedDict([("t", t), ("v", v)])


def prop(uid, match, name, value, **extra):
    p = OrderedDict([("match", match), ("name", name), ("node", "Prop"), ("uid", uid), ("value", value)])
    for k in sorted(extra):
        p[k] = extra[k]
    return p


SWITCHES = OrderedDict([("adjustment", False), ("audio", True), ("collapse", False), ("effects", True),
                        ("frame_blend", "Off"), ("guide", False), ("locked", False), ("motion_blur", False),
                        ("quality", "Best"), ("sampling", "Bilinear"), ("shy", False), ("solo", False),
                        ("three_d", False), ("video", True)])


def layer_payload(lid, name, item, uid0, transform, tracks=None):
    root = OrderedDict([("children", [OrderedDict([("children", transform), ("match", "transform"),
                                                   ("name", "Transform"), ("node", "Group"), ("uid", uid0 + 1)])]),
                        ("match", "layer"), ("name", name), ("uid", uid0)])
    layer = OrderedDict([("blend_mode", "Normal"), ("id", lid), ("in_point", 0), ("label", "None"), ("name", name),
                         ("out_point", DUR), ("props", root), ("source", OrderedDict([("item", item), ("type", "Solid")])),
                         ("start_time", 0), ("stretch", 100.0), ("switches", SWITCHES)])
    p = OrderedDict([("comp", 3), ("layer", layer), ("schema_version", 1)])
    if tracks:
        p["tracks"] = tracks
    return p


# keyframes of the beacon -----------------------------------------------------------------
POSITION_KEYS = [  # (time, value, in_interp, out_interp)
    (0, [40.0, 90.0, 0.0], "Linear", "Linear"),
    (sec(1.0), [280.0, 90.0, 0.0], "Linear", "Hold"),
    (sec(1.5), [160.0, 60.0, 0.0], "Linear", "Linear")]
ROTATION_KEYS = [  # (time, value, in_interp, out_interp, in_eases, out_eases)
    (0, [0.0], "Linear", "Bezier", [], [(0.0, 0.5)]),
    (DUR, [360.0], "Bezier", "Linear", [(0.0, 0.5)], [])]
INTERP = {"Linear": 0, "Bezier": 1, "Hold": 2}


def tracks_file(owner, pos_uid, rot_uid):
    at, interp, flags, label, value, spatial, ecount, ease = [], [], [], [], [], [], [], []
    for (t, v, i, o) in POSITION_KEYS:
        at.append(t); interp += [INTERP[i], INTERP[o]]; flags.append(0); label.append(0); value += v
        spatial += [0.0] * 6; ecount += [0, 0]
    for (t, v, i, o, ie, oe) in ROTATION_KEYS:
        at.append(t); interp += [INTERP[i], INTERP[o]]; flags.append(0); label.append(0); value += v
        spatial += [0.0] * 6; ecount += [len(ie), len(oe)]
        for s, inf in ie + oe:
            ease += [s, inf]
    K_, V, E = len(at), len(value), len(ease) // 2
    hdr = {"owner": owner, "ticks_per_second": TPS, "interpolations": ["Linear", "Bezier", "Hold"],
           "tracks": [{"uid": pos_uid, "kind": "vec3", "components": 3, "keys": 3, "first_key": 0,
                       "first_value": 0, "first_ease": 0},
                      {"uid": rot_uid, "kind": "scalar", "components": 1, "keys": 2, "first_key": 3,
                       "first_value": 9, "first_ease": 0}]}
    secs = [("at", "i64", [K_], 8, struct.pack("<%dq" % K_, *at)),
            ("interp", "u8", [K_, 2], 2, bytes(interp)),
            ("flags", "u8", [K_], 1, bytes(flags)),
            ("label", "u8", [K_], 1, bytes(label)),
            ("value", "f64", [V], 8, struct.pack("<%dd" % V, *value)),
            ("spatial", "f64", [K_, 6], 48, struct.pack("<%dd" % len(spatial), *spatial)),
            ("ease-count", "u8", [K_, 2], 2, bytes(ecount)),
            ("ease", "f64", [E, 2], 16, struct.pack("<%dd" % len(ease), *ease))]
    return K.envelope(b"WKX3", "core.keyframe.tracks", hdr, secs)


README = (u"Beacon sweep\n\n"
          u"This is a werk package, profile `motion-comp/1`: a motion-graphics project (two solids, "
          u"one composition, two layers, keyframes inline and in a keyframe-tracks file). It carries "
          u"its own format specification, three readers, a reference reader of this profile, and "
          u"its licence.\n\n"
          u"    python loaders/werk_read.py <this file> --verify --strict\n"
          u"    python tools/reader-motion-comp/read_motion_comp.py <this file>\n\n"
          u"Where to read next: HOW-TO-READ.md, spec/PROFILE-MOTION-COMP.md, spec/CRAFT-BASE.md, spec/SPEC.md.\n")
LICENSE = (u"CC0 1.0 Universal (public domain dedication).\n\n"
           u"This project was made by a script for the werk release fixtures; to the extent possible "
           u"under law, the author has waived all copyright and related rights to it. "
           u"https://creativecommons.org/publicdomain/zero/1.0/\n")


def build(out):
    pp = K.ProfilePackage("motion-comp", "Beacon sweep",
                          summary="motion-comp/1 release fixture: one 320 x 180 composition, 25 fps, 2 s, two "
                                  "solid layers, keyframes inline and in a tracks file (Linear, Hold, Bezier).",
                          readme_text=README, license_text=LICENSE, spdx_id="CC0-1.0")
    w = pp.w
    # ids: 1, 2 solids; 3 comp; 4, 5 layers; 6.. groups and properties
    project = OrderedDict([
        ("app_schema", 2), ("folders", []), ("fonts", []),
        ("items", [OrderedDict([("id", 1), ("kind", "solid"), ("node", "item-1")]),
                   OrderedDict([("id", 2), ("kind", "solid"), ("node", "item-2")]),
                   OrderedDict([("id", 3), ("kind", "comp"), ("node", "comp-3")])]),
        ("next_id", 20), ("schema_version", 1),
        ("settings", OrderedDict([("audio_sample_rate", 48000), ("bit_depth", "Bpc8"), ("frame_start", 0),
                                  ("linearize", False), ("time_display", "Timecode")]))])

    def solid(iid, name, colour, wpx, hpx):
        return OrderedDict([("id", iid), ("kind", OrderedDict([("Solid", OrderedDict([
            ("color", colour), ("height", hpx), ("pixel_aspect", 1.0), ("width", wpx)]))])),
            ("label", "None"), ("name", name), ("schema_version", 1)])
    item1 = solid(1, "Night", [0.0625, 0.125, 0.25], 320, 180)
    item2 = solid(2, "Beacon", [1.0, 0.8125, 0.375], 40, 40)
    comp = OrderedDict([
        ("comp", OrderedDict([("background", [0.0, 0.0, 0.0]), ("display_start", 0), ("duration", DUR),
                              ("frame_rate", OrderedDict([("den", 1), ("num", FPS)])), ("height", 180),
                              ("motion_blur_samples", 16), ("pixel_aspect", 1.0), ("shutter_angle", 180.0),
                              ("shutter_phase", -90.0), ("width", 320), ("work_area", [0, DUR])])),
        ("id", 3), ("label", "None"),
        ("layers", [OrderedDict([("id", 4), ("node", "layer-4")]), OrderedDict([("id", 5), ("node", "layer-5")])]),
        ("name", "Beacon sweep"), ("schema_version", 1)])
    # layer-4: uids 6 (root), 7 (transform), 8..12 props
    opacity_keys = [OrderedDict([("time", 0), ("value", val("Scalar", 0.0))]),
                    OrderedDict([("time", sec(0.4)), ("value", val("Scalar", 100.0))])]
    beacon = layer_payload(4, "Beacon", 2, 6, [
        prop(8, "anchor", "Anchor Point", val("Vec3", [20.0, 20.0, 0.0])),
        prop(9, "position", "Position", val("Vec3", [40.0, 90.0, 0.0]), spatial=False, track=0),
        prop(10, "scale", "Scale", val("Vec3", [100.0, 100.0, 100.0])),
        prop(11, "rotation", "Rotation", val("Scalar", 0.0), track=1),
        prop(12, "opacity", "Opacity", val("Scalar", 0.0), keys=opacity_keys)], tracks="layer-4-keys")
    night = layer_payload(5, "Night", 1, 13, [
        prop(15, "anchor", "Anchor Point", val("Vec3", [160.0, 90.0, 0.0])),
        prop(16, "position", "Position", val("Vec3", [160.0, 90.0, 0.0])),
        prop(17, "scale", "Scale", val("Vec3", [100.0, 100.0, 100.0])),
        prop(18, "rotation", "Rotation", val("Scalar", 0.0)),
        prop(19, "opacity", "Opacity", val("Scalar", 100.0))])

    def add(nid, ntype, path, data, note, edges=(), mt="application/json"):
        w.add_node(nid, ntype, [w.file(path, data, mt)], note=note, edges=list(edges))

    add("project", "core.motion.project", "project/project.json", K.cjson(project),
        "The project structure: settings and the table of items.",
        [("item-1", "enhances", "contains"), ("item-2", "enhances", "contains"), ("comp-3", "enhances", "contains")])
    add("item-1", "core.motion.item", "items/item-1.json", K.cjson(item1), "Solid item: the night-blue frame.")
    add("item-2", "core.motion.item", "items/item-2.json", K.cjson(item2), "Solid item: the beacon square.")
    add("comp-3", "core.motion.comp", "comps/comp-3/comp.json", K.cjson(comp),
        "The composition Beacon sweep: 320 x 180, 25 fps, 2 s.",
        [("layer-4", "enhances", "layer"), ("layer-5", "enhances", "layer")])
    add("layer-4", "core.motion.layer", "comps/comp-3/layer-4.json", K.cjson(beacon),
        "The beacon layer: moves, turns and fades in.",
        [("item-2", "enhances", "source"), ("layer-4-keys", "enhances", "keyframes")])
    add("layer-4-keys", "core.keyframe.tracks", "comps/comp-3/layer-4.keys.wkx", tracks_file("layer-4", 9, 11),
        "Keyframe tracks of the beacon layer: position and rotation.",
        [("layer-4", "requires", "animates")], mt="application/octet-stream")
    add("layer-5", "core.motion.layer", "comps/comp-3/layer-5.json", K.cjson(night),
        "The background layer, static.", [("item-1", "enhances", "source")])
    w.set_primary("document", "project")
    for p in ("HOW-TO-READ.md", "revisions/", "project/project.json"):
        w.preview(p)
    pp.add_reference_reader()
    data = pp.write(out, "First save of the motion-comp/1 release fixture: Beacon sweep.")
    sys.path.insert(0, HERE)
    import read_motion_comp as R
    got = R.read(out)
    assert not got["dead"] and not got["file_failures"], got["dead"]
    s = got["comps"][0]["layers"][0]["animated"]
    # ground truth at chosen frames (6.3): linear position, hold after 1 s, linear opacity
    assert s["transform/position"][0] == [40.0, 90.0, 0.0] and s["transform/position"][25] == [280.0, 90.0, 0.0]
    assert s["transform/position"][30] == [280.0, 90.0, 0.0] and s["transform/position"][40] == [160.0, 60.0, 0.0]
    assert abs(s["transform/position"][10][0] - 136.0) < 1e-9
    assert s["transform/opacity"][5] == 50.0 and s["transform/opacity"][10] == 100.0
    assert abs(s["transform/rotation"][25] - 180.0) < 1e-9  # symmetric eases: half way at half time
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "fixtures", "motion-comp-v1.werk"))
    a = ap.parse_args()
    data = build(a.out)
    print("%s %d bytes sha256 %s" % (a.out, len(data), K.sha(data)))


if __name__ == "__main__":
    main()
