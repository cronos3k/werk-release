#include "werk_basis.h"

#include <cmath>
#include <cstdio>

namespace werk
{

namespace
{
    const std::array<std::array<double, 3>, 3> kM = { {
        { { 0.0,  0.0, -1.0 } },
        { { 1.0,  0.0,  0.0 } },
        { { 0.0,  1.0,  0.0 } },
    } };

    inline Vec3 MulM(const Vec3& V)
    {
        return { -V[2], V[0], V[1] };
    }

    inline Vec3 MulMT(const Vec3& V)
    {
        // M is orthogonal, so the inverse is the transpose:
        //   x = Y, y = Z, z = -X
        return { V[1], V[2], -V[0] };
    }
}

const std::array<std::array<double, 3>, 3>& BasisMatrixWerkToUe()
{
    return kM;
}

double BasisDeterminant()
{
    const auto& M = kM;
    return M[0][0] * (M[1][1] * M[2][2] - M[1][2] * M[2][1])
         - M[0][1] * (M[1][0] * M[2][2] - M[1][2] * M[2][0])
         + M[0][2] * (M[1][0] * M[2][1] - M[1][1] * M[2][0]);
}

// --- vectors ---------------------------------------------------------------

Vec3 DirectionWerkToUe(const Vec3& V) { return MulM(V); }
Vec3 DirectionUeToWerk(const Vec3& V) { return MulMT(V); }

Vec3 PositionWerkToUe(const Vec3& V)
{
    const Vec3 R = MulM(V);
    return { R[0] * UeUnitsPerWerkUnit, R[1] * UeUnitsPerWerkUnit, R[2] * UeUnitsPerWerkUnit };
}

Vec3 PositionUeToWerk(const Vec3& V)
{
    const Vec3 R = MulMT(V);
    return { R[0] * WerkUnitsPerUeUnit, R[1] * WerkUnitsPerUeUnit, R[2] * WerkUnitsPerUeUnit };
}

Vec3 ScaleWerkToUe(const Vec3& S)
{
    // diag(sx, sy, sz) conjugated by M is diag(sz, sx, sy): the axes permute
    // exactly as the vectors do, and the sign flip squares away.
    return { S[2], S[0], S[1] };
}

Vec3 ScaleUeToWerk(const Vec3& S)
{
    return { S[1], S[2], S[0] };
}

// --- quaternions -----------------------------------------------------------

Quat QuatMul(const Quat& A, const Quat& B)
{
    const double aw = A[0], ax = A[1], ay = A[2], az = A[3];
    const double bw = B[0], bx = B[1], by = B[2], bz = B[3];
    return {
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    };
}

Quat QuatFromAxisAngle(const Vec3& Axis, double AngleRadians)
{
    double N = std::sqrt(Axis[0] * Axis[0] + Axis[1] * Axis[1] + Axis[2] * Axis[2]);
    if (N < 1e-12)
    {
        N = 1.0;
    }
    const double S = std::sin(AngleRadians * 0.5);
    return { std::cos(AngleRadians * 0.5), Axis[0] / N * S, Axis[1] / N * S, Axis[2] / N * S };
}

Vec3 QuatRotate(const Quat& Q, const Vec3& V)
{
    const Quat QV = { 0.0, V[0], V[1], V[2] };
    const Quat Conj = { Q[0], -Q[1], -Q[2], -Q[3] };
    const Quat R = QuatMul(QuatMul(Q, QV), Conj);
    return { R[1], R[2], R[3] };
}

static Quat NormalizeQ(const Quat& Q)
{
    const double N = std::sqrt(Q[0] * Q[0] + Q[1] * Q[1] + Q[2] * Q[2] + Q[3] * Q[3]);
    if (N < 1e-12)
    {
        return { 1.0, 0.0, 0.0, 0.0 };
    }
    return { Q[0] / N, Q[1] / N, Q[2] / N, Q[3] / N };
}

Quat QuatCanonicalWxyz(const Quat& Q)
{
    const Quat N = NormalizeQ(Q);
    if (N[0] < 0.0)
    {
        return { -N[0], -N[1], -N[2], -N[3] };
    }
    return N;
}

Quat QuatCanonicalXyzw(const Quat& Q)
{
    const Quat N = NormalizeQ(Q);
    if (N[3] < 0.0)
    {
        return { -N[0], -N[1], -N[2], -N[3] };
    }
    return N;
}

Quat QuatWerkToUe(const Quat& QWxyz)
{
    // Axis is a pseudovector under an orientation-reversing map: a -> -M a,
    // angle unchanged. With M a = (-z, x, y), the negation gives (z, -x, -y).
    const Quat C = QuatCanonicalWxyz(QWxyz);
    const double w = C[0], x = C[1], y = C[2], z = C[3];
    return QuatCanonicalXyzw({ z, -x, -y, w });
}

Quat QuatUeToWerk(const Quat& QXyzw)
{
    const Quat C = QuatCanonicalXyzw(QXyzw);
    const double X = C[0], Y = C[1], Z = C[2], W = C[3];
    return QuatCanonicalWxyz({ W, -Y, -Z, X });
}

// --- AABB ------------------------------------------------------------------

static void AabbConvert(const Vec3& InMin, const Vec3& InMax, Vec3& OutMin, Vec3& OutMax,
                        Vec3 (*Fn)(const Vec3&))
{
    const Vec3 A = Fn(InMin);
    const Vec3 B = Fn(InMax);
    for (int i = 0; i < 3; ++i)
    {
        OutMin[i] = A[i] < B[i] ? A[i] : B[i];
        OutMax[i] = A[i] < B[i] ? B[i] : A[i];
    }
}

void AabbWerkToUe(const Vec3& InMin, const Vec3& InMax, Vec3& OutMin, Vec3& OutMax)
{
    AabbConvert(InMin, InMax, OutMin, OutMax, &PositionWerkToUe);
}

void AabbUeToWerk(const Vec3& InMin, const Vec3& InMax, Vec3& OutMin, Vec3& OutMax)
{
    AabbConvert(InMin, InMax, OutMin, OutMax, &PositionUeToWerk);
}

// --- winding ---------------------------------------------------------------

bool ReverseWinding(std::vector<unsigned int>& Indices)
{
    if (Indices.size() % 3 != 0)
    {
        return false;
    }
    for (size_t i = 0; i + 2 < Indices.size(); i += 3)
    {
        const unsigned int Tmp = Indices[i + 1];
        Indices[i + 1] = Indices[i + 2];
        Indices[i + 2] = Tmp;
    }
    return true;
}

// --- selftest --------------------------------------------------------------

namespace
{
    struct Checker
    {
        std::vector<std::string> Bad;
        bool bVerbose = false;

        void Near(const Vec3& Got, const Vec3& Want, const char* What, double Tol = 1e-9)
        {
            bool bOk = true;
            for (int i = 0; i < 3; ++i)
            {
                if (std::fabs(Got[i] - Want[i]) > Tol)
                {
                    bOk = false;
                }
            }
            Emit(bOk, What, Got.data(), Want.data(), 3);
        }

        void Near4(const Quat& Got, const Quat& Want, const char* What, double Tol = 1e-9)
        {
            bool bOk = true;
            for (int i = 0; i < 4; ++i)
            {
                if (std::fabs(Got[i] - Want[i]) > Tol)
                {
                    bOk = false;
                }
            }
            Emit(bOk, What, Got.data(), Want.data(), 4);
        }

        void Scalar(double Got, double Want, const char* What, double Tol = 1e-12)
        {
            const bool bOk = std::fabs(Got - Want) <= Tol;
            Emit(bOk, What, &Got, &Want, 1);
        }

        void Boolean(bool bGot, const char* What)
        {
            if (!bGot)
            {
                Bad.push_back(std::string(What) + ": false");
            }
            else if (bVerbose)
            {
                std::printf("  OK %s\n", What);
            }
        }

        void Emit(bool bOk, const char* What, const double* Got, const double* Want, int N)
        {
            char Buf[256];
            if (!bOk)
            {
                std::string S = std::string(What) + ": got (";
                for (int i = 0; i < N; ++i)
                {
                    std::snprintf(Buf, sizeof(Buf), "%s%.12g", i ? ", " : "", Got[i]);
                    S += Buf;
                }
                S += ") want (";
                for (int i = 0; i < N; ++i)
                {
                    std::snprintf(Buf, sizeof(Buf), "%s%.12g", i ? ", " : "", Want[i]);
                    S += Buf;
                }
                S += ")";
                Bad.push_back(S);
            }
            else if (bVerbose)
            {
                std::string S;
                for (int i = 0; i < N; ++i)
                {
                    std::snprintf(Buf, sizeof(Buf), "%s%.12g", i ? ", " : "", Got[i]);
                    S += Buf;
                }
                std::printf("  OK %s -> (%s)\n", What, S.c_str());
            }
        }
    };

    Vec3 Cross(const Vec3& A, const Vec3& B)
    {
        return { A[1] * B[2] - A[2] * B[1],
                 A[2] * B[0] - A[0] * B[2],
                 A[0] * B[1] - A[1] * B[0] };
    }

    Vec3 Sub(const Vec3& A, const Vec3& B)
    {
        return { A[0] - B[0], A[1] - B[1], A[2] - B[2] };
    }

    Vec3 NormalizeV(const Vec3& V)
    {
        const double N = std::sqrt(V[0] * V[0] + V[1] * V[1] + V[2] * V[2]);
        if (N < 1e-12)
        {
            return { 0.0, 0.0, 0.0 };
        }
        return { V[0] / N, V[1] / N, V[2] / N };
    }

    // Independent route: quaternion -> 3x3 -> conjugate by M -> quaternion.
    // Deliberately does NOT reuse QuatWerkToUe, so that agreeing with it means
    // something.
    Quat ConjugateThroughMatrix(const Quat& QWxyz)
    {
        const Quat Q = QuatCanonicalWxyz(QWxyz);
        const double w = Q[0], x = Q[1], y = Q[2], z = Q[3];
        const double R[3][3] = {
            { 1 - 2 * (y * y + z * z), 2 * (x * y - w * z),     2 * (x * z + w * y) },
            { 2 * (x * y + w * z),     1 - 2 * (x * x + z * z), 2 * (y * z - w * x) },
            { 2 * (x * z - w * y),     2 * (y * z + w * x),     1 - 2 * (x * x + y * y) },
        };

        const auto& M = kM;
        double MR[3][3] = {};
        for (int i = 0; i < 3; ++i)
        {
            for (int j = 0; j < 3; ++j)
            {
                double S = 0.0;
                for (int k = 0; k < 3; ++k)
                {
                    S += M[i][k] * R[k][j];
                }
                MR[i][j] = S;
            }
        }
        double O[3][3] = {};
        for (int i = 0; i < 3; ++i)
        {
            for (int j = 0; j < 3; ++j)
            {
                double S = 0.0;
                for (int k = 0; k < 3; ++k)
                {
                    S += MR[i][k] * M[j][k]; // times M transpose
                }
                O[i][j] = S;
            }
        }

        // Shepperd: pick the largest denominator so no branch loses precision.
        const double Tr = O[0][0] + O[1][1] + O[2][2];
        double qw, qx, qy, qz;
        if (Tr > 0.0)
        {
            const double S = std::sqrt(Tr + 1.0) * 2.0;
            qw = 0.25 * S;
            qx = (O[2][1] - O[1][2]) / S;
            qy = (O[0][2] - O[2][0]) / S;
            qz = (O[1][0] - O[0][1]) / S;
        }
        else if (O[0][0] > O[1][1] && O[0][0] > O[2][2])
        {
            const double S = std::sqrt(1.0 + O[0][0] - O[1][1] - O[2][2]) * 2.0;
            qw = (O[2][1] - O[1][2]) / S;
            qx = 0.25 * S;
            qy = (O[0][1] + O[1][0]) / S;
            qz = (O[0][2] + O[2][0]) / S;
        }
        else if (O[1][1] > O[2][2])
        {
            const double S = std::sqrt(1.0 + O[1][1] - O[0][0] - O[2][2]) * 2.0;
            qw = (O[0][2] - O[2][0]) / S;
            qx = (O[0][1] + O[1][0]) / S;
            qy = 0.25 * S;
            qz = (O[1][2] + O[2][1]) / S;
        }
        else
        {
            const double S = std::sqrt(1.0 + O[2][2] - O[0][0] - O[1][1]) * 2.0;
            qw = (O[1][0] - O[0][1]) / S;
            qx = (O[0][2] + O[2][0]) / S;
            qy = (O[1][2] + O[2][1]) / S;
            qz = 0.25 * S;
        }
        // Result is a UE-space rotation; return it in UE xyzw order.
        return QuatCanonicalXyzw({ qx, qy, qz, qw });
    }
}

std::vector<std::string> BasisSelftest(bool bVerbose)
{
    Checker C;
    C.bVerbose = bVerbose;

    const double Deg = 3.14159265358979323846 / 180.0;

    // 1. The determinant. Everything else in this file is a consequence.
    C.Scalar(BasisDeterminant(), -1.0, "det(M) == -1 (handedness flips)");

    // 2. The three named axes.
    C.Near(DirectionWerkToUe({ 0, 1, 0 }), { 0, 0, 1 }, "werk up -> UE up (+Z)");
    C.Near(DirectionWerkToUe({ 0, 0, -1 }), { 1, 0, 0 }, "werk forward -> UE forward (+X)");
    C.Near(DirectionWerkToUe({ 1, 0, 0 }), { 0, 1, 0 }, "werk right -> UE right (+Y)");
    C.Near(DirectionUeToWerk({ 0, 0, 1 }), { 0, 1, 0 }, "UE up -> werk up");
    C.Near(DirectionUeToWerk({ 1, 0, 0 }), { 0, 0, -1 }, "UE forward -> werk forward");
    C.Near(DirectionUeToWerk({ 0, 1, 0 }), { 1, 0, 0 }, "UE right -> werk right");

    // 3. Units. One metre up in werk is 100 cm up in UE.
    C.Near(PositionWerkToUe({ 0, 1, 0 }), { 0, 0, 100 }, "1 m up -> 100 cm up");
    C.Near(PositionUeToWerk({ 0, 0, 100 }), { 0, 1, 0 }, "100 cm up -> 1 m up");

    // 4. Round trips on an asymmetric vector, so no sign error can cancel.
    const Vec3 V = { 0.25, -1.5, 3.75 };
    C.Near(PositionUeToWerk(PositionWerkToUe(V)), V, "position round trip", 1e-12);
    C.Near(DirectionUeToWerk(DirectionWerkToUe(V)), V, "direction round trip", 1e-12);

    // 5. Scale permutes and never negates.
    C.Near(ScaleWerkToUe({ 2.0, 3.0, 5.0 }), { 5.0, 2.0, 3.0 }, "scale permutes");
    C.Near(ScaleUeToWerk(ScaleWerkToUe({ 2.0, 3.0, 5.0 })), { 2.0, 3.0, 5.0 }, "scale round trip");

    // 6. AABB corners must be re-min/re-maxed, not carried across positionally.
    //    Uses the golden fixture's own numbers (physics/bounds.json).
    {
        Vec3 Mn, Mx;
        AabbWerkToUe({ -0.5, -0.5, -0.5 }, { 0.54, 0.54, 0.5 }, Mn, Mx);
        // X = -z, so the werk max z (0.5) becomes the UE min X (-50).
        C.Near(Mn, { -50.0, -50.0, -50.0 }, "fixture AABB min");
        C.Near(Mx, { 50.0, 54.0, 54.0 }, "fixture AABB max");
        C.Boolean(Mn[0] <= Mx[0] && Mn[1] <= Mx[1] && Mn[2] <= Mx[2], "AABB stays ordered");
    }

    // 7. Identity is identity in both frames, in both component orders.
    C.Near4(QuatWerkToUe({ 1, 0, 0, 0 }), { 0, 0, 0, 1 }, "identity quaternion (wxyz -> xyzw)");

    // 8. Named rotations. A yaw about werk up must be a yaw about UE up; this
    //    is the check a round trip cannot make.
    {
        const Quat YawW = QuatFromAxisAngle({ 0, 1, 0 }, 90 * Deg);
        // det(M) < 0 flips the sense: +90 about werk up is -90 about UE up.
        const Quat WantXyzw = QuatCanonicalXyzw({ 0, 0, -std::sin(45 * Deg), std::cos(45 * Deg) });
        C.Near4(QuatWerkToUe(YawW), WantXyzw, "90 deg yaw about up becomes -90 about UE up");
    }

    // 9. The closed form must agree with an independently computed M R M^T.
    {
        const Quat Cases[4] = {
            QuatFromAxisAngle({ 0, 1, 0 }, 90 * Deg),
            QuatFromAxisAngle({ 1, 0, 0 }, 30 * Deg),
            QuatFromAxisAngle({ 0, 0, -1 }, 45 * Deg),
            QuatCanonicalWxyz(QuatMul(QuatFromAxisAngle({ 0, 1, 0 }, 90 * Deg),
                                      QuatFromAxisAngle({ 0.3, -0.7, 0.64 }, 117 * Deg))),
        };
        const char* Names[4] = { "closed form == M R M^T (yaw)",
                                 "closed form == M R M^T (pitch)",
                                 "closed form == M R M^T (roll)",
                                 "closed form == M R M^T (compound)" };
        for (int i = 0; i < 4; ++i)
        {
            C.Near4(QuatWerkToUe(Cases[i]), ConjugateThroughMatrix(Cases[i]), Names[i], 1e-9);
            C.Near4(QuatUeToWerk(QuatWerkToUe(Cases[i])), QuatCanonicalWxyz(Cases[i]),
                    "quaternion round trip", 1e-12);
        }

        // 10. The property that makes a mesh and a skeleton line up:
        //     convert(rotate(q, v)) == rotate(convert(q), convert(v)).
        for (int i = 0; i < 4; ++i)
        {
            const Vec3 Lhs = PositionWerkToUe(QuatRotate(Cases[i], V));
            const Quat QUe = QuatWerkToUe(Cases[i]);
            // QuatRotate takes wxyz; QUe is xyzw, so re-order for the call.
            const Quat QUeWxyz = { QUe[3], QUe[0], QUe[1], QUe[2] };
            const Vec3 Rhs = QuatRotate(QUeWxyz, PositionWerkToUe(V));
            C.Near(Lhs, Rhs, "rotate-then-convert == convert-then-rotate", 1e-9);
        }
    }

    // 11. Winding, as the theorem det(M) < 0 makes it. A werk triangle wound
    //     counter-clockwise about werk up, mapped and reversed, must be wound
    //     counter-clockwise about M * (werk up) = UE up.
    {
        const Vec3 P0 = { 0, 0, 0 }, P1 = { 1, 0, 0 }, P2 = { 0, 0, -1 };
        const Vec3 NWerk = NormalizeV(Cross(Sub(P1, P0), Sub(P2, P0)));
        C.Near(NWerk, { 0, 1, 0 }, "source triangle normal is werk up");

        const Vec3 Q0 = PositionWerkToUe(P0);
        const Vec3 Q1 = PositionWerkToUe(P1);
        const Vec3 Q2 = PositionWerkToUe(P2);

        const Vec3 NKept = NormalizeV(Cross(Sub(Q1, Q0), Sub(Q2, Q0)));
        C.Near(NKept, { 0, 0, -1 }, "keeping the winding INVERTS the normal (this is the bug)");

        const Vec3 NRev = NormalizeV(Cross(Sub(Q2, Q0), Sub(Q1, Q0)));
        C.Near(NRev, DirectionWerkToUe(NWerk), "reversed winding restores M * n");

        std::vector<unsigned int> Idx = { 0, 1, 2, 3, 4, 5 };
        C.Boolean(ReverseWinding(Idx), "ReverseWinding accepts a multiple of 3");
        C.Boolean(Idx[0] == 0 && Idx[1] == 2 && Idx[2] == 1 &&
                  Idx[3] == 3 && Idx[4] == 5 && Idx[5] == 4, "ReverseWinding swaps b and c");
        std::vector<unsigned int> Odd = { 0, 1 };
        C.Boolean(!ReverseWinding(Odd), "ReverseWinding refuses a non-multiple of 3");
    }

    // 12. Canonical sign, both orders.
    {
        const Quat Q = QuatCanonicalWxyz(QuatFromAxisAngle({ 0.2, 0.5, -0.3 }, 200 * Deg));
        const Quat Neg = { -Q[0], -Q[1], -Q[2], -Q[3] };
        C.Near4(QuatCanonicalWxyz(Neg), Q, "canonical wxyz picks w >= 0");
        C.Boolean(QuatCanonicalWxyz(Neg)[0] >= 0.0, "canonical wxyz w >= 0");
        C.Boolean(QuatCanonicalXyzw(QuatWerkToUe(Q))[3] >= 0.0, "canonical xyzw w >= 0");
    }

    return C.Bad;
}

} // namespace werk
