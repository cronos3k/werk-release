"""Ed25519, pure stdlib.

RFC 8032 reference algorithm, transcribed. It is here for one reason: law 1
forbids a promise about other files, and a store that could only check a
signature when a wheel happened to be installed would be making exactly that
promise about itself. `hashlib` ships with Python; nothing else is needed.

This implementation is NOT constant-time and must not be used to sign with a
key whose secrecy matters against an attacker who can measure this process.
Verification - the store's actual job - has no secret to leak. Signing is
provided so tests can build a genuinely signed fixture rather than assert
against a mock.

Correctness is proven, not claimed: tests/test_signature.py runs the RFC 8032
section 7.1 test vectors before any werk-specific test is allowed to trust
this module.
"""

from __future__ import annotations

import hashlib

# Curve parameters (RFC 8032, section 5.1)
P = 2 ** 255 - 19
Q = 2 ** 252 + 27742317777372353535851937790883648493

_D = -121665 * pow(121666, P - 2, P) % P
_SQRT_M1 = pow(2, (P - 1) // 4, P)


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _sha512_modq(data: bytes) -> int:
    return int.from_bytes(_sha512(data), "little") % Q


def _inv(x: int) -> int:
    return pow(x, P - 2, P)


# Points are (X, Y, Z, T) in extended homogeneous coordinates: x = X/Z,
# y = Y/Z, x*y = T/Z.


def _point_add(p1, p2):
    a = (p1[1] - p1[0]) * (p2[1] - p2[0]) % P
    b = (p1[1] + p1[0]) * (p2[1] + p2[0]) % P
    c = 2 * p1[3] * p2[3] * _D % P
    d = 2 * p1[2] * p2[2] % P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % P, g * h % P, f * g % P, e * h % P)


def _point_mul(s: int, point):
    out = (0, 1, 1, 0)  # neutral element
    while s > 0:
        if s & 1:
            out = _point_add(out, point)
        point = _point_add(point, point)
        s >>= 1
    return out


def _point_equal(p1, p2) -> bool:
    if (p1[0] * p2[2] - p2[0] * p1[2]) % P != 0:
        return False
    if (p1[1] * p2[2] - p2[1] * p1[2]) % P != 0:
        return False
    return True


def _recover_x(y: int, sign: int):
    if y >= P:
        return None
    x2 = (y * y - 1) * _inv(_D * y * y + 1) % P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (P + 3) // 8, P)
    if (x * x - x2) % P != 0:
        x = x * _SQRT_M1 % P
    if (x * x - x2) % P != 0:
        return None
    if (x & 1) != sign:
        x = P - x
    return x


_G_Y = 4 * _inv(5) % P
_G_X = _recover_x(_G_Y, 0)
G = (_G_X, _G_Y, 1, _G_X * _G_Y % P)


def _compress(point) -> bytes:
    zinv = _inv(point[2])
    x = point[0] * zinv % P
    y = point[1] * zinv % P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(data: bytes):
    if len(data) != 32:
        return None
    y = int.from_bytes(data, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % P)


def _secret_expand(secret: bytes):
    if len(secret) != 32:
        raise ValueError("ed25519 secret key must be 32 bytes")
    h = _sha512(secret)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def public_key(secret: bytes) -> bytes:
    """32-byte public key for a 32-byte secret seed."""
    a, _prefix = _secret_expand(secret)
    return _compress(_point_mul(a, G))


def sign(secret: bytes, message: bytes) -> bytes:
    """64-byte pure-Ed25519 signature over *message*."""
    a, prefix = _secret_expand(secret)
    pub = _compress(_point_mul(a, G))
    r = _sha512_modq(prefix + message)
    big_r = _compress(_point_mul(r, G))
    h = _sha512_modq(big_r + pub + message)
    s = (r + h * a) % Q
    return big_r + int.to_bytes(s, 32, "little")


def verify(pub: bytes, message: bytes, signature: bytes) -> bool:
    """True iff *signature* is a valid pure-Ed25519 signature.

    Returns False rather than raising for every malformed input: a bad
    signature and a bad key are the same verdict to a caller, and the
    three-state doctrine wants a verdict, not an exception.
    """
    if len(pub) != 32 or len(signature) != 64:
        return False
    point_a = _decompress(pub)
    if point_a is None:
        return False
    rs = signature[:32]
    point_r = _decompress(rs)
    if point_r is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= Q:
        return False
    h = _sha512_modq(rs + pub + message)
    return _point_equal(_point_mul(s, G), _point_add(point_r, _point_mul(h, point_a)))
