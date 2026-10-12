"""Evidence tests for the payload grader. It does not grade every prompt clause."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import grade


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ow-adversarial-")
        self.root = Path(self.temp.name)
        self.run = self.root / "run"
        self.run.mkdir()
        self.payloads = {"mesh.glb": b"mesh values", "sound.wav": b"sound values"}
        nodes = [{"node_id": slot, "type": typ, "active": 1,
                  "versions": [{"v": 1, "files": [{"path": name,
                  "sha256": hashlib.sha256(self.payloads[name]).hexdigest()}]}]}
                 for slot, typ, name in [("mesh", "core.geom.game", "mesh.glb"),
                                         ("sound", "core.audio.effect", "sound.wav")]]
        self.fixture = self.root / "synthetic.werk"
        with zipfile.ZipFile(self.fixture, "w") as archive:
            archive.writestr("MANIFEST.json", json.dumps({"nodes": nodes,
                              "primary": {"mesh": "mesh", "sound": "sound"}}))
            for name, data in self.payloads.items():
                archive.writestr(name, data)

    def tearDown(self):
        self.temp.cleanup()

    def verdict(self):
        argv = ["grade.py", "--fixture", str(self.fixture), "--rundir", str(self.run),
                "--require-primary", "mesh,sound"]
        output = io.StringIO()
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(output):
            grade.main()
        return output.getvalue().split("TASK (required primary payloads present by sha256): ")[1].split()[0]

    def test_no_artifact(self):
        self.assertEqual(self.verdict(), "FAIL")

    def test_prompt_copy(self):
        (self.run / "PROMPT-copy.txt").write_text("mesh.glb sound.wav")
        self.assertEqual(self.verdict(), "FAIL")

    def test_helper_source(self):
        (self.run / "helper.py").write_bytes(self.payloads["mesh.glb"])
        self.assertEqual(self.verdict(), "FAIL")

    def test_program_source(self):
        (self.run / "solution.py").write_bytes(self.payloads["mesh.glb"])
        self.assertEqual(self.verdict(), "FAIL")

    def test_missing_payload(self):
        (self.run / "mesh.glb").write_bytes(self.payloads["mesh.glb"])
        self.assertEqual(self.verdict(), "FAIL")

    def test_wrong_interior_bytes(self):
        for name, data in self.payloads.items():
            (self.run / name).write_bytes(data)
        (self.run / "mesh.glb").write_bytes(b"mesh VALUEs")
        self.assertEqual(self.verdict(), "FAIL")

    def test_complete_payloads(self):
        for name, data in self.payloads.items():
            (self.run / name).write_bytes(data)
        self.assertEqual(self.verdict(), "PASS")


if __name__ == "__main__":
    unittest.main()
