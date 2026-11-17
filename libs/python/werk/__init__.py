"""werk -- read and write werk packages, Python standard library only.

All code lives in `_core.py`; `werk_single.py` (next to this package) is the
same code with the vendored spec/ + loaders/ bundle embedded, for hosts that
vendor one file. See libs/README.md for the API.
"""
from ._core import *  # noqa: F401,F403
from ._core import (open, Package, PackageWriter, LocalFile, Node, WerkError,  # noqa: F401
                    ContainerRefusal, payload_path, write_image_package, write_mesh_package,
                    append_version, sign_package, json_pretty, json_canonical, json_loads,
                    spec_sha256_of, input_hash_of, ed25519_sign, ed25519_verify,
                    ed25519_public_key, verify_chain, png_info, glb_info, main, LIB_VERSION,
                    default_bundle, read_envelope, physical_order)

__version__ = LIB_VERSION
