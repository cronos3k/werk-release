//! Structural validation of the two Stage 12 geometry envelopes, `WKGS`
//! (`core.geom.gsplat`) and `WKPC` (`core.geom.points`).
//!
//! `envelope::parse` already enforces the grammar every werk binary shares:
//! the magic, the declared payload origin, section alignment, file-order, the
//! stride/shape/size consistency rule, and no NaN or infinity. What it cannot
//! know is that a WKGS has exactly six sections with exactly those names, that
//! `sh_coeff_count` must be `(sh_degree+1)^2`, or that a WKPC's `fields` array
//! must line up one-to-one with its sections. Those are the per-magic layout
//! files' rules — `spec/layouts/gsplat.layout.txt` section 8 and
//! `spec/layouts/points.layout.txt` section 6 — and this module is those two
//! sections, executed.
//!
//! The two severities in those sections are kept apart here, because they are
//! a real distinction and collapsing them would throw away a hundred megabytes
//! of intact payload over a producer's slip:
//!
//!   * `check_*` returns `Err` for the checks that KILL the node — a section
//!     missing, a count that disagrees with a shape, a declared space this
//!     grammar does not have. Those mean the reader cannot say what the bytes
//!     are.
//!   * `warnings_*` returns the checks that are a producer's mistake rather
//!     than a malformed file — a non-positive scale, an opacity outside
//!     [0,1], a quaternion that is not unit or whose `w` is negative. The node
//!     still loads and the report names the first offending index, so the
//!     complaint is actionable rather than a shrug.

use crate::envelope::{Envelope, Section};
use crate::msgpack::Mp;

/// Names and order required by gsplat.layout.txt section 3.
const GSPLAT_SECTIONS: [&str; 6] = [
    "means", "scales", "rotations", "opacities", "sh-dc", "sh-rest",
];

fn u64_key(env: &Envelope, key: &str) -> Result<u64, String> {
    env.header
        .get(key)
        .and_then(Mp::as_u64)
        .ok_or_else(|| format!("header has no unsigned `{key}`"))
}

fn str_key<'a>(env: &'a Envelope, key: &str) -> Result<&'a str, String> {
    env.header
        .get(key)
        .and_then(Mp::as_str)
        .ok_or_else(|| format!("header has no string `{key}`"))
}

fn want_str(env: &Envelope, key: &str, expect: &str) -> Result<(), String> {
    let got = str_key(env, key)?;
    if got != expect {
        return Err(format!(
            "header declares {key} = `{got}`; grammar revision 1 of this layout \
             defines only `{expect}`"
        ));
    }
    Ok(())
}

fn section<'a>(env: &'a Envelope, name: &str) -> Result<&'a Section, String> {
    env.section(name)
        .ok_or_else(|| format!("no `{name}` section"))
}

/// gsplat.layout.txt section 8, checks 1-4 (check 5, finiteness, is the
/// envelope's own).
pub fn check_gsplat(env: &Envelope) -> Result<(), String> {
    let count = u64_key(env, "count")?;
    let degree = u64_key(env, "sh_degree")?;
    let k = u64_key(env, "sh_coeff_count")?;

    if degree > 3 {
        return Err(format!("sh_degree is {degree}; the layout defines 0..3"));
    }
    let expect_k = (degree + 1) * (degree + 1);
    if k != expect_k {
        return Err(format!(
            "sh_coeff_count is {k} but sh_degree {degree} requires (degree+1)^2 = {expect_k}"
        ));
    }

    want_str(env, "sh_coeff_order", "coefficient-major")?;
    want_str(env, "quat_order", "wxyz")?;
    want_str(env, "scale_space", "linear")?;
    want_str(env, "opacity_space", "linear")?;
    want_str(env, "length_unit", "metre")?;

    // All six, in order. The order is part of the grammar rather than a
    // convenience: a reader is entitled to find them by name (ENVELOPE §5a)
    // and a WRITER that emits them in another order has produced a file this
    // layout does not describe.
    let names: Vec<&str> = env.sections.iter().map(|s| s.name.as_str()).collect();
    if names != GSPLAT_SECTIONS {
        return Err(format!(
            "sections are {names:?}; gsplat.layout.txt section 3 requires exactly \
             {GSPLAT_SECTIONS:?}, in that order"
        ));
    }

    for name in ["means", "scales", "rotations", "opacities", "sh-dc"] {
        let s = section(env, name)?;
        if s.shape.first().copied() != Some(count) {
            return Err(format!(
                "section `{name}` has shape {:?}; shape[0] must be count = {count}",
                s.shape
            ));
        }
    }
    let rest = section(env, "sh-rest")?;
    if rest.shape.len() != 3 {
        return Err(format!(
            "section `sh-rest` has shape {:?}; it must be [count, sh_coeff_count-1, 3]",
            rest.shape
        ));
    }
    if rest.shape[0] != count || rest.shape[1] != k - 1 || rest.shape[2] != 3 {
        return Err(format!(
            "section `sh-rest` has shape {:?}; count {count} and sh_coeff_count {k} \
             require [{count}, {}, 3]",
            rest.shape,
            k - 1
        ));
    }
    Ok(())
}

/// gsplat.layout.txt section 8, checks 6-8: a producer's mistake, not a
/// malformed file. The node loads and the report names the first bad index.
pub fn warnings_gsplat(env: &Envelope, buf: &[u8]) -> Vec<String> {
    let mut out = Vec::new();
    let count = match u64_key(env, "count") {
        Ok(c) => c as usize,
        Err(_) => return out,
    };
    if count == 0 {
        return out;
    }

    if let Some(s) = env.section("scales") {
        if let Some(i) = first_where(buf, s, 3, |v| !(v > 0.0)) {
            out.push(format!(
                "section `scales`: entry {i} is not strictly greater than zero. A \
                 Gaussian with a zero or negative standard deviation has no \
                 covariance; the node still loads (layout section 8)"
            ));
        }
    }
    if let Some(s) = env.section("opacities") {
        if let Some(i) = first_where(buf, s, 1, |v| !(0.0..=1.0).contains(&v)) {
            out.push(format!(
                "section `opacities`: entry {i} is outside [0,1], which \
                 opacity_space `linear` requires"
            ));
        }
    }
    if let Some(s) = env.section("rotations") {
        let mut bad_norm = None;
        let mut bad_sign = None;
        for i in 0..count {
            let q = read_f32s(buf, s, i, 4);
            if q.len() != 4 {
                break;
            }
            let n = (q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]).sqrt();
            if bad_norm.is_none() && (n - 1.0).abs() > 1e-6 {
                bad_norm = Some((i, n));
            }
            if bad_sign.is_none() && q[0] < 0.0 {
                bad_sign = Some(i);
            }
            if bad_norm.is_some() && bad_sign.is_some() {
                break;
            }
        }
        if let Some((i, n)) = bad_norm {
            out.push(format!(
                "section `rotations`: entry {i} has |q| = {n}, outside 1e-6 of unit \
                 (ENVELOPE.layout.txt section 6)"
            ));
        }
        if let Some(i) = bad_sign {
            out.push(format!(
                "section `rotations`: entry {i} has w < 0. q and -q are the same \
                 rotation, so this is not wrong geometry — but writers MUST emit \
                 the w >= 0 representative, and two writers that disagree produce \
                 two byte-different files for one splat"
            ));
        }
    }
    out
}

/// points.layout.txt section 6, checks 1-4 (7, finiteness, is the envelope's).
/// Checks 5 and 6 are warnings and live in `warnings_points`.
pub fn check_points(env: &Envelope) -> Result<(), String> {
    let count = u64_key(env, "count")?;
    want_str(env, "length_unit", "metre")?;

    let fields = env
        .header
        .get("fields")
        .and_then(Mp::as_array)
        .ok_or("header has no `fields` array")?;
    if fields.is_empty() {
        return Err("`fields` is empty; a point cloud has at least a position".into());
    }
    if fields.len() != env.sections.len() {
        return Err(format!(
            "{} field(s) declared but {} payload section(s); points.layout.txt \
             section 3 pairs them one-to-one, in order",
            fields.len(),
            env.sections.len()
        ));
    }

    let mut positions = 0;
    for (i, f) in fields.iter().enumerate() {
        let name = f
            .get("name")
            .and_then(Mp::as_str)
            .ok_or_else(|| format!("fields[{i}] has no `name`"))?;
        let sec_name = f
            .get("section")
            .and_then(Mp::as_str)
            .ok_or_else(|| format!("field `{name}` has no `section`"))?;
        let semantic = f
            .get("semantic")
            .and_then(Mp::as_str)
            .ok_or_else(|| format!("field `{name}` has no `semantic`"))?;
        let dtype = f
            .get("dtype")
            .and_then(Mp::as_str)
            .ok_or_else(|| format!("field `{name}` has no `dtype`"))?;
        let comps = f
            .get("components")
            .and_then(Mp::as_u64)
            .ok_or_else(|| format!("field `{name}` has no `components`"))?;
        if comps == 0 {
            return Err(format!("field `{name}` declares 0 components"));
        }
        if dtype == "record" {
            return Err(format!(
                "field `{name}` declares dtype `record`, which a WKPC field may \
                 not use (points.layout.txt section 4)"
            ));
        }
        if env.sections[i].name != sec_name {
            return Err(format!(
                "field {i} (`{name}`) names section `{sec_name}` but section {i} is \
                 `{}`; the two lists are in the same order",
                env.sections[i].name
            ));
        }
        let s = &env.sections[i];
        if s.dtype != dtype {
            return Err(format!(
                "field `{name}` declares dtype `{dtype}` but its section declares \
                 `{}`",
                s.dtype
            ));
        }
        let want: Vec<u64> = if comps == 1 {
            vec![count]
        } else {
            vec![count, comps]
        };
        if s.shape != want {
            return Err(format!(
                "field `{name}` has {comps} component(s) over {count} point(s), so \
                 its section's shape must be {want:?}; it declares {:?}",
                s.shape
            ));
        }
        if semantic == "position" {
            positions += 1;
            if i != 0 {
                return Err(format!(
                    "the position field is fields[{i}]; points.layout.txt section 2 \
                     requires it FIRST"
                ));
            }
            if !(dtype == "f32" || dtype == "f64") || comps != 3 {
                return Err(format!(
                    "position field `{name}` is {dtype} x{comps}; it must be f32 or \
                     f64 with 3 components"
                ));
            }
        }
    }
    if positions != 1 {
        return Err(format!(
            "{positions} field(s) have semantic `position`; exactly one must"
        ));
    }
    Ok(())
}

/// points.layout.txt section 6, checks 5-6: warn, do not kill. A colour whose
/// space is undeclared is a colour a consumer may still show while saying it
/// guessed, and refusing a million points over a missing string is law 3's
/// failure mode.
pub fn warnings_points(env: &Envelope) -> Vec<String> {
    let mut out = Vec::new();
    let fields = match env.header.get("fields").and_then(Mp::as_array) {
        Some(f) => f,
        None => return out,
    };
    for f in fields {
        let name = f.get("name").and_then(Mp::as_str).unwrap_or("?");
        let semantic = f.get("semantic").and_then(Mp::as_str).unwrap_or("");
        if semantic == "color" && f.get("color_space").and_then(Mp::as_str).is_none() {
            out.push(format!(
                "field `{name}` has semantic `color` and declares no `color_space`; \
                 a consumer can only guess, and half of them will guess wrong"
            ));
        }
        if semantic == "custom" && !name.starts_with("x-") {
            out.push(format!(
                "custom field `{name}` is not named `x-...`; the prefix is what \
                 keeps the semantic registry trustworthy"
            ));
        }
        if !matches!(
            semantic,
            "position" | "color" | "normal" | "intensity" | "classification" | "custom"
        ) {
            out.push(format!(
                "field `{name}` has semantic `{semantic}`, which is not in the v1 \
                 registry; its section is skipped and the position is unaffected"
            ));
        }
    }
    out
}

// ---------------------------------------------------------------------------

fn read_f32s(buf: &[u8], s: &Section, row: usize, comps: usize) -> Vec<f32> {
    let base = s.offset as usize + row * s.stride as usize;
    let mut out = Vec::with_capacity(comps);
    for c in 0..comps {
        let o = base + c * 4;
        if o + 4 > buf.len() || (o as u64) + 4 > s.offset + s.size {
            return Vec::new();
        }
        out.push(f32::from_le_bytes(buf[o..o + 4].try_into().unwrap()));
    }
    out
}

fn first_where<F: Fn(f32) -> bool>(
    buf: &[u8],
    s: &Section,
    comps: usize,
    bad: F,
) -> Option<usize> {
    if s.dtype != "f32" {
        return None;
    }
    let rows = s.shape.first().copied().unwrap_or(0) as usize;
    for i in 0..rows {
        let v = read_f32s(buf, s, i, comps);
        if v.len() != comps {
            return None;
        }
        if v.into_iter().any(&bad) {
            return Some(i);
        }
    }
    None
}
