import os
import sys

# The store is tooling, run from a checkout. Put the package on the path
# rather than requiring an install, so `pytest` works in a bare clone.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

import mkwerk  # noqa: E402
from werkstore import WerkStore  # noqa: E402


@pytest.fixture
def store(tmp_path):
    return WerkStore(str(tmp_path / "store"))


@pytest.fixture
def werk_v1(tmp_path):
    dest = str(tmp_path / "pkg-v1")
    digest = mkwerk.make_synthetic(dest, "v1")
    return dest, digest


@pytest.fixture
def werk_v2(tmp_path):
    dest = str(tmp_path / "pkg-v2")
    digest = mkwerk.make_synthetic(dest, "v2")
    return dest, digest
