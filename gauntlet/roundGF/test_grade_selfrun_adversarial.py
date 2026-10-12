"""An echoed vector cannot substitute for a successful executable."""

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

import grade_selfrun


class SelfrunTests(unittest.TestCase):
    def test_evidence_and_exit_status(self):
        with tempfile.TemporaryDirectory(prefix="selfrun-adversarial-") as tmp:
            root = Path(tmp)
            fixture = root / "synthetic.werk"
            want = b"vector output\n"
            digest = hashlib.sha256(want).hexdigest()
            vector = {"vector_id": "synthetic", "steps": 1, "temperature": 1,
                      "stdout_sha256_lf": digest, "stdout_file": "expected.txt",
                      "argv": ["tool", "model/stories15M.bin", "-z", "model/tokenizer.bin"]}
            with zipfile.ZipFile(fixture, "w") as archive:
                archive.writestr("testvectors/vectors.json", json.dumps({"vectors": [vector]}))
                archive.writestr("testvectors/expected.txt", want)
                archive.writestr("model/stories15M.bin", b"synthetic model")
                archive.writestr("model/tokenizer.bin", b"synthetic tokenizer")
            for name in ["PROMPT-copy.txt", "helper.py", "solution.py", "REPORT.md", None]:
                run = root / (name or "empty")
                run.mkdir()
                if name:
                    (run / name).write_bytes(want)
                out = root / "grade.json"
                argv = ["grader", "--fixture", str(fixture), "--rundir", str(run), "--json-out", str(out)]
                with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                    grade_selfrun.main()
                self.assertEqual(json.loads(out.read_text())["verdict"], "FAIL", name)
            run = root / "binary"
            run.mkdir()
            (run / "tool.exe").write_bytes(b"synthetic stub; never executed")
            argv = ["grader", "--fixture", str(fixture), "--rundir", str(run), "--json-out", str(out)]
            for status, exit_code, verdict in [("completed", 0, "PASS"), ("completed", 1, "FAIL"),
                                                ("host-error", None, "HOST-ERROR")]:
                result = {"status": status, "exit": exit_code, "error": None,
                          "stdout_sha256_lf": digest, "stdout_bytes_lf": len(want)}
                def invoke(command, scratch):
                    data = Path(scratch)
                    self.assertEqual((data / "model/stories15M.bin").read_bytes(), b"synthetic model")
                    self.assertEqual((data / "model/tokenizer.bin").read_bytes(), b"synthetic tokenizer")
                    self.assertFalse((data / "testvectors").exists())
                    return result
                with patch.object(sys, "argv", argv), patch.object(grade_selfrun, "run_command", side_effect=invoke), \
                        contextlib.redirect_stdout(io.StringIO()):
                    grade_selfrun.main()
                self.assertEqual(json.loads(out.read_text())["verdict"], verdict)


if __name__ == "__main__":
    unittest.main()
