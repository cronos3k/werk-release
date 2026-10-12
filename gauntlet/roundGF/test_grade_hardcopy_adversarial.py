"""Words and source files cannot establish recovered fixture bytes."""

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import grade_hardcopy


class HardcopyTests(unittest.TestCase):
    def test_recovered_bytes(self):
        with tempfile.TemporaryDirectory(prefix="hardcopy-adversarial-") as tmp:
            root = Path(tmp)
            fixture, png = root / "synthetic.werk", root / "smiley.png"
            with zipfile.ZipFile(fixture, "w") as archive:
                archive.writestr("payload", b"synthetic")
            png.write_bytes(b"synthetic image bytes")
            for name in ["PROMPT-copy.txt", "helper.py", "solution.py", "REPORT.md", None, "correct"]:
                run = root / (name or "empty")
                workspace = run / "workspace"
                workspace.mkdir(parents=True)
                if name == "correct":
                    (workspace / "recovered.werk").write_bytes(fixture.read_bytes())
                    (workspace / "recovered.png").write_bytes(png.read_bytes())
                elif name:
                    (workspace / name).write_text("8168 bytes, CRC 9/9. All recovered. payload.")
                out = root / "grade.json"
                argv = ["grader", "--rundir", str(run), "--werk", str(fixture), "--png", str(png),
                        "--json-out", str(out)]
                with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                    grade_hardcopy.main()
                result = json.loads(out.read_text())["ladder"]
                self.assertEqual(result["4_whole_file_sha256"], name == "correct")
                self.assertEqual(result["6_the_image_is_the_smiley"], name == "correct")


if __name__ == "__main__":
    unittest.main()
