"""Tests for destructive paths, exact arguments, and distinct failures."""

import argparse
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from rerun_support import prepare_output, program_args, run_python


class RerunTests(unittest.TestCase):
    def test_argument_array(self):
        args = argparse.Namespace(prog_args='"input file.werk" out',
                                  prog_arg=[r"C:\some path\out", "--flag"])
        self.assertEqual(program_args(args), ["input file.werk", "out", r"C:\some path\out", "--flag"])

    def test_existing_files_survive(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / "keep.txt"
            marker.write_text("keep")
            with self.assertRaises(ValueError):
                prepare_output(root)
            self.assertEqual(marker.read_text(), "keep")

    def test_protected_parent(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                prepare_output(root, [Path(root) / "trial"])

    def test_git_checkout(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / ".git").write_text("gitdir: elsewhere")
            with self.assertRaises(ValueError):
                prepare_output(Path(root) / "scratch")

    def test_empty_path(self):
        with self.assertRaises(ValueError):
            prepare_output("")

    def test_host_error(self):
        with patch("rerun_support.subprocess.run", side_effect=OSError(4551, "blocked")):
            result = run_python("reader.py", [], ".")
        self.assertEqual(result["status"], "host-error")
        self.assertIsNone(result["exit"])

    def test_timeout(self):
        with patch("rerun_support.subprocess.run", side_effect=subprocess.TimeoutExpired([], 1, b"partial")):
            result = run_python("reader.py", [], ".", 1)
        self.assertEqual(result["status"], "program-timeout")
        self.assertEqual(result["stdout"], "partial")

    def test_program_failure(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "reader.py").write_text("import sys\nprint(sys.argv[1])\nsys.exit(7)\n")
            result = run_python("reader.py", ["an argument with spaces"], root)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["exit"], 7)
        self.assertEqual(result["stdout"].strip(), "an argument with spaces")


if __name__ == "__main__":
    unittest.main()
