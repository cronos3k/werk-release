"""Errors for werk-store.

Every failure mode that can mean "the store lied to you" gets its own class
and carries an exact report. The store is a cache, never the truth
(MANIFESTO, The Companion, constraint 1): when it cannot prove what it
returns, it must refuse loudly rather than hand back plausible bytes.
"""

from __future__ import annotations


class WerkStoreError(Exception):
    """Base class for every werk-store failure."""


class HashMismatch(WerkStoreError):
    """Content did not hash to the name it was filed under or claimed.

    Carries the exact report the brief demands: what was expected, what was
    found, how many bytes were read, and where they came from.
    """

    def __init__(self, expected: str, actual: str, size: int, source: str) -> None:
        self.expected = expected
        self.actual = actual
        self.size = size
        self.source = source
        super().__init__(
            "hash mismatch for {src}: manifest declares sha256={exp} but "
            "{n} bytes hash to sha256={act}".format(
                src=source, exp=expected, n=size, act=actual
            )
        )


class SizeMismatch(WerkStoreError):
    """A file's byte length disagreed with the manifest's declared size."""

    def __init__(self, path: str, expected: int, actual: int) -> None:
        self.path = path
        self.expected = expected
        self.actual = actual
        super().__init__(
            "size mismatch for {p}: manifest declares {exp} bytes, found "
            "{act}".format(p=path, exp=expected, act=actual)
        )


class MissingObject(WerkStoreError):
    """An object the store was asked for is not present."""

    def __init__(self, digest: str, context: str = "") -> None:
        self.digest = digest
        self.context = context
        msg = "object {h} not in store".format(h=digest)
        if context:
            msg += " (needed for {c})".format(c=context)
        super().__init__(msg)


class ManifestError(WerkStoreError):
    """The manifest is absent, unparseable, or structurally unusable."""


class PackageError(WerkStoreError):
    """The .werk source (directory or zip) is not a usable package."""


class UnsafePath(WerkStoreError):
    """A manifest path would escape the package root or is otherwise unsafe."""


class MaterializeError(WerkStoreError):
    """Materialization could not prove byte-identity, so it failed."""


class SignatureError(WerkStoreError):
    """The signature chain is present and does not stand."""
