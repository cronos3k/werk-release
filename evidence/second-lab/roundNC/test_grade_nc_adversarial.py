"""Synthetic cases for evidence, missing clauses, and wrong interior values."""

import argparse
import contextlib
import io
from pathlib import Path
import tempfile
import unittest

import grade_nc
import nc_mesh


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nc-artifact-test-")
        self.root = Path(self.temp.name)
        self.positions = [(float(i), float(i) / 2, -float(i)) for i in range(10)]
        self.expected = {"status": "COMPLETE", "fixture_files": [], "payloads": [],
                         "absent_classes": ["texture"], "tier1_declared_all": {},
                         "tier2_mesh": nc_mesh.mesh_record(self.positions, 3),
                         "integrity_declared_by_file": {"declares": "none"}}
        self.args = argparse.Namespace(payload="texture", format="gltf", human=[], rundir=str(self.root))

    def tearDown(self):
        self.temp.cleanup()

    def write_positions(self, name, values=None):
        values = self.positions if values is None else values
        (self.root / name).write_text("\n".join("%s %s %s" % p for p in values))

    def grade(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return grade_nc.grade(self.args, {}, self.expected, self.positions,
                                  str(self.root), None, None)

    def test_no_artifact(self):
        self.assertEqual(self.grade()["verdict"], "FAIL")

    def test_prompt_copy(self):
        self.write_positions("PROMPT-copy.txt")
        self.assertEqual(self.grade()["clauses"]["C5"]["result"], "FAIL")

    def test_helper_source(self):
        self.write_positions("helper.py")
        self.assertEqual(self.grade()["verdict"], "FAIL")

    def test_program_source(self):
        self.write_positions("solution.py")
        self.assertEqual(self.grade()["verdict"], "FAIL")

    def test_wrong_interior_correct_bounds(self):
        changed = self.positions.copy()
        changed[3], changed[6] = changed[6], changed[3]
        self.write_positions("positions.xyz", changed)
        self.assertEqual(self.grade()["clauses"]["C5"]["result"], "FAIL")

    def test_correct_first_point_only(self):
        self.write_positions("positions.xyz", self.positions[:1])
        self.assertEqual(self.grade()["clauses"]["C5"]["result"], "FAIL")

    def test_missing_human_clauses(self):
        self.write_positions("positions.xyz")
        result = self.grade()
        self.assertEqual(result["clauses"]["C5"]["result"], "PASS")
        self.assertEqual(result["verdict"], "PENDING")

    def test_host_error_not_program_failure(self):
        self.args.run_status = "host-error"
        self.assertEqual(self.grade()["verdict"], "HOST-ERROR")

    def test_timeout_is_program_failure(self):
        self.args.run_status = "program-timeout"
        self.assertEqual(self.grade()["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()
