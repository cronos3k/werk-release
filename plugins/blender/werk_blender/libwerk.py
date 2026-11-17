"""The werk release library, vendored as one file: `vendor/werk_single.py`.

`werk_single.py` is a byte-identical copy of the release library's single-file
build (`libs/python/werk_single.py`: reader + PackageWriter + the embedded
spec/loaders bundle, standard library only). The gate re-hashes it against its
source, like `vendor/werk_read.py` and `spec/`.

What the add-on uses it for:

  * the signature state: Ed25519 is verified here (the bootstrap reader the
    3D importer is built on reports every signature as `unverified`);
  * the verdict of every package it reads or writes (census, error codes,
    `spec_sha256` recomputed) -- so each export is re-read by an
    implementation that shares no writer code with `exporter.py`;
  * image/1: `primary_image()` on import, `write_image_package()` on export.
"""

from .vendor import werk_single as werk  # noqa: F401  (re-exported)


def verdict_of(path):
    """(verdict dict, None) or (None, reason) -- never raises."""
    try:
        pkg = werk.open(path)
    except werk.ContainerRefusal as e:
        return None, "container refused: %s" % getattr(e, "code", e)
    except Exception as e:  # noqa: BLE001
        return None, "%s: %s" % (type(e).__name__, e)
    return dict(pkg.verdict()), None
