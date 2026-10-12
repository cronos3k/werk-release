"""Post-hoc rerun support. Never delete an existing output directory."""

import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time


def program_args(args):
    """Keep shell-string compatibility and append verbatim arguments."""
    return shlex.split(args.prog_args or "") + list(args.prog_arg)


def prepare_output(path, protected=()):
    """Require a new or empty directory outside every Git checkout."""
    if not path:
        raise ValueError("--out must name a scratch directory")
    out = Path(path).resolve()
    for source in protected:
        src = Path(source).resolve()
        if out == src or out in src.parents:
            raise ValueError("output contains a protected input")
    if any((p / ".git").exists() for p in (out, *out.parents)):
        raise ValueError("output must be outside a Git checkout")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("output must be new or empty; existing files are never removed")
    out.mkdir(parents=True, exist_ok=True)
    return str(out)


def run_command(argv, cwd, timeout=1800):
    """Separate launch failures, timeouts, and a completed program's exit."""
    started = time.monotonic()
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    result = {"argv": list(argv), "exit": None, "status": "completed", "error": None}
    try:
        process = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=timeout, env=env)
        result["exit"] = process.returncode
        stdout, stderr = process.stdout, process.stderr
    except OSError as exc:
        result.update(status="host-error", error=str(exc))
        stdout, stderr = b"", b""
    except subprocess.TimeoutExpired as exc:
        result.update(status="program-timeout", error="program exceeded %s seconds" % timeout)
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
    normalized = stdout.replace(b"\r\n", b"\n")
    result.update(stdout_sha256_lf=hashlib.sha256(normalized).hexdigest(),
                  stdout_bytes_lf=len(normalized))
    result.update(stdout=stdout.decode("utf-8", "replace"),
                  stderr=stderr.decode("utf-8", "replace"),
                  secs=round(time.monotonic() - started, 3))
    return result


def run_python(program, args, cwd, timeout=1800):
    """Run a copied script without user site packages or user Python settings."""
    return run_command([sys.executable, "-I", "-X", "utf8", program] + list(args), cwd, timeout)
