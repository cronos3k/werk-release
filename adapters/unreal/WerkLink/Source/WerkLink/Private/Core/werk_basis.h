// The one basis change, written once, with known vectors.
//
// werk model space (MANIFEST.json `conventions`):
//     up +Y, forward -Z, right +X, RIGHT-handed, metres, quaternions wxyz,
//     winding ccw
// Unreal Engine world space:
//     up +Z, forward +X, right +Y, LEFT-handed, centimetres, quaternions xyzw
//
// Unlike the Blender adapter (adapters/blender/werk_blender/axes.py), where the
// only difference is the up axis and quaternion order already agrees, EVERY
// axis of this one differs and the HANDEDNESS FLIPS. That last part is what
// makes this module worth its own file and its own selftest: an orientation-
// reversing map is not a rotation, it cannot be written as a quaternion
// conjugation, and it inverts triangle winding as a matter of arithmetic
// rather than as a matter of taste.
//
// THE MATRIX, stated so it can be checked rather than believed. M maps a werk
// vector (x, y, z) to an Unreal vector (X, Y, Z), before the unit scale:
//
//     M = [[ 0,  0, -1],        X = -z
//          [ 1,  0,  0]   i.e.  Y =  x
//          [ 0,  1,  0]]        Z =  y
//
//     M * (0, 1, 0)  = (0, 0, 1)   werk up      -> UE up      (+Z)
//     M * (0, 0, -1) = (1, 0, 0)   werk forward -> UE forward (+X)
//     M * (1, 0, 0)  = (0, 1, 0)   werk right   -> UE right   (+Y)
//
//     det(M) = -1
//
// All three named axes land on their named counterparts — which is only
// possible because the determinant is negative, since no rotation can carry a
// right-handed frame onto a left-handed one. The determinant is asserted
// numerically in Selftest(); it is the single fact everything else follows
// from.
//
// WINDING, as a theorem and not a preference. det(M) < 0 means M reverses
// orientation, so a triangle wound counter-clockwise about its outward normal
// in werk space comes out wound clockwise about the SAME transformed normal in
// UE space. Restoring the convention means reversing the index order of every
// triangle, on import and on export alike. Selftest() checks this on a real
// triangle rather than asserting it in a comment: it builds a werk triangle
// whose right-hand-rule normal is werk up, maps the positions, reverses the
// winding, recomputes the right-hand-rule normal in UE space, and requires
// that it equals M * (werk up). Normals themselves are transformed by M
// directly, because M is orthogonal and so its inverse transpose is itself.
//
// QUATERNIONS. A rotation R in werk space is the rotation M R M^-1 in UE
// space. Because M reverses orientation, the rotation AXIS is a pseudovector:
// it transforms as det(M) * M * a = -M * a, while the angle is unchanged.
// Hence, for q = (w, x, y, z) in werk wxyz order:
//
//     q_ue(xyzw) = ( z, -x, -y, w )
//
// and back, for (X, Y, Z, W) in UE xyzw order:
//
//     q_werk(wxyz) = ( W, -Y, -Z, X )
//
// Selftest() proves this closed form three ways: against the matrix
// conjugation M R M^T computed independently, against named rotations (a yaw
// about werk up must become a yaw about UE up), and against the property that
// actually matters for a mesh and a skeleton agreeing --
//
//     ConvertVector(Rotate(q, v)) == Rotate(ConvertQuat(q), ConvertVector(v))
//
// -- which a round-trip test alone cannot catch, because a conjugation written
// the wrong way round round-trips perfectly.
//
// UNITS. werk is metres (conventions.units_per_meter = 1.0), UE is
// centimetres. Positions are multiplied by 100 on import and divided by 100 on
// export. A non-uniform scale triple is dimensionless but is still per-axis, so
// it permutes with the axes: diag(sx, sy, sz) conjugates to diag(sz, sx, sy).
// The negations square away, which is why a scale triple has no sign flip and
// a position does.
//
// WHAT CONVERTS WHERE, so nothing is converted twice or not at all:
//
// | data                                      | converted by |
// |-------------------------------------------|--------------|
// | core.geom.* positions / normals / tangents | this module, in the GLB reader |
// | core.geom.* triangle winding              | this module (ReverseWinding)   |
// | core.phys.bounds AABB + sphere centre     | this module (AABB needs remin/remax) |
// | core.phys.colliders centres + rotations   | this module  |
// | manifest parts[] TRS                      | this module  |
// | core.skeleton rest translations + rots    | this module  |
// | UVs, colours, audio, semantics            | nobody -- no axes in them |
//
// UV origin is top-left on both sides (conventions.uv_origin), so UVs are NOT
// flipped. That is a deliberate non-conversion and it is listed above as one.

#pragma once

#include <array>
#include <string>
#include <vector>

namespace werk
{

using Vec3 = std::array<double, 3>;
using Quat = std::array<double, 4>; // storage order is stated at every use site

// werk uses metres; Unreal uses centimetres.
inline constexpr double WerkUnitsPerUeUnit = 0.01;
inline constexpr double UeUnitsPerWerkUnit = 100.0;

// --- vectors ---------------------------------------------------------------

// werk model space -> Unreal world space, including the metre -> centimetre
// scale. This is the function for POSITIONS.
Vec3 PositionWerkToUe(const Vec3& V);
Vec3 PositionUeToWerk(const Vec3& V);

// The same basis change WITHOUT the unit scale. This is the function for
// directions: normals, tangents, axes -- anything whose length is either
// meaningless or already normalised.
Vec3 DirectionWerkToUe(const Vec3& V);
Vec3 DirectionUeToWerk(const Vec3& V);

// A per-axis scale triple. Dimensionless, so no unit factor; permuted, because
// the axes permute.
Vec3 ScaleWerkToUe(const Vec3& S);
Vec3 ScaleUeToWerk(const Vec3& S);

// --- quaternions -----------------------------------------------------------
// werk quaternions are wxyz (conventions.quat_order). Unreal's FQuat is xyzw.
// The order swap is folded into these functions so no call site ever has to
// remember it -- MINI-SPECS.md 10.2 calls the equivalent glTF mismatch "the
// single most dangerous mismatch in the whole format".

// In: werk wxyz. Out: UE xyzw.
Quat QuatWerkToUe(const Quat& QWxyz);
// In: UE xyzw. Out: werk wxyz.
Quat QuatUeToWerk(const Quat& QXyzw);

// --- axis-aligned boxes ----------------------------------------------------
// An AABB does not survive a basis change by transforming its corners and
// keeping them as min and max: the axes permute and one of them negates, so
// the transformed "min" can hold the larger value. Both corners are
// transformed and then re-min/re-maxed componentwise.
void AabbWerkToUe(const Vec3& InMin, const Vec3& InMax, Vec3& OutMin, Vec3& OutMax);
void AabbUeToWerk(const Vec3& InMin, const Vec3& InMax, Vec3& OutMin, Vec3& OutMax);

// --- winding ---------------------------------------------------------------
// det(M) < 0, so triangle index order reverses in both directions. Indices are
// a flat triangle list, three per face; the count must be a multiple of three.
bool ReverseWinding(std::vector<unsigned int>& Indices);

// --- helpers used by the selftest and by callers ---------------------------

Quat QuatMul(const Quat& AWxyz, const Quat& BWxyz);            // wxyz in, wxyz out
Quat QuatFromAxisAngle(const Vec3& Axis, double AngleRadians);  // wxyz out
Vec3 QuatRotate(const Quat& QWxyz, const Vec3& V);              // wxyz
// ENVELOPE.layout.txt section 6: writers MUST emit the w >= 0 representative,
// so that two encoders of the same pose produce the same bytes.
Quat QuatCanonicalWxyz(const Quat& QWxyz);
// UE's xyzw with the same doctrine applied to the w component.
Quat QuatCanonicalXyzw(const Quat& QXyzw);

// The 3x3 basis matrix M, row-major, for callers that want it explicitly and
// for the selftest's independent conjugation route.
const std::array<std::array<double, 3>, 3>& BasisMatrixWerkToUe();
double BasisDeterminant();

// --- selftest --------------------------------------------------------------
// Every claim in this file's comment block, as a numeric check. Returns the
// list of failures; empty means everything held. This is a GATE input, not a
// debug aid: the standalone target runs it and prints the count.
std::vector<std::string> BasisSelftest(bool bVerbose = false);

} // namespace werk
