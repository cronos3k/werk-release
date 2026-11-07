# `_discarded-wsl-bash/` — the self-run attempt killed by a harness defect

`qwen/qwen3-coder-30b`, ctx 65536, the adapted self-run arm. Outcome as the
driver recorded it: `model-finished`, 5 iterations, **82.3 s**. Not scored.

**The defect was ours.** `driver_selfrun.py` executed the model's script with
`subprocess.run(["bash", ...])` from a Windows Python, and "bash" resolves
against the *Windows* PATH — which on this box finds **WSL's** bash before
MSYS2's. WSL is a separate Linux userland with no `gcc`, no `cl.exe`, and no
path to either. The tell is in `run.iter4.stdout.txt`:

```
drwxrwxrwx 1 root root     4096 Aug  9 17:29 .
-rwxrwxrwx 1 root root 62525273 Aug  9 17:29 selfrun-v1.werk
```

`root root` and `drwxrwxrwx` are WSL, not MSYS2.

The model's own probe, in `solution.iter1.sh`, was correct:

```bash
elif command -v gcc &> /dev/null; then
    echo "Using GCC compiler (gcc)"
    BUILD_CMD="gcc -O3 -o run tools/llama2c/run.c -lm"
```

`gcc` **is** on this box at `/c/msys64/mingw64/bin/gcc`, and `command -v gcc`
finds it under the MSYS2 bash the harness should have used. Under WSL it does
not exist, so the script fell through to `echo "No suitable compiler found"` and
exited 1 — three iterations in a row. On the fourth the model gave up building
and emitted a script that *describes* the build and the expected digest instead
of performing it, then declared TASK COMPLETE. That is S-OW-6 ("exit code 0 is
not did-the-job") firing on top of a harness defect, and grading it would have
scored our environment as the model's capability — the S-OW-5 error.

**Fixed** in `driver_selfrun.py`: the interpreter defaults to
`C:/msys64/usr/bin/bash.exe`, is overridable with `GF_BASH`, and the resolved
path is recorded in every `run.json` as `bash`. The arm was re-run from cold.
Kept because a discarded run is part of the experimental record.
