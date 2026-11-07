#!/usr/bin/env python3
"""
driver.py -- the open-weights gauntlet harness.

One minimal agentic loop for small local models served by LM Studio's
OpenAI-compatible API at http://127.0.0.1:1234/v1. Standard library only
(urllib + subprocess + json); no pip, no SDK, no framework.

It exists because the cross-vendor round (results/STAGE-CROSSVENDOR-RESULTS.md)
tested two *vendors* but only one *class* of implementer: frontier commercial
models inside their own agentic CLIs. Small open-weights models have no such
CLI. This is the smallest thing that gives them one, so that the difference
measured is the model and not the harness.

Design rules, each of which is part of the experimental record:

* FOUR TOOLS ONLY -- run_shell, write_file, read_file, list_dir. Nothing that
  reaches the network. No web search, no fetch, no git.
* THE DRIVER MEASURES TIME. S-XV-5's companion finding was that every agent in
  the cross-vendor round overestimated its own elapsed time by 2.2x to 11x.
  Nothing self-reported is timed here; `wall_s` is `time.monotonic()` around
  the whole run, measured by this process.
* THE SANDBOX IS ENFORCED HERE, NOT REQUESTED IN THE PROMPT. Every path
  argument and every absolute-looking path inside a shell command is resolved
  and refused unless it lies under the run directory. The isolation rules in
  the task prompt are the *agent's* instructions; this is the *harness's*
  guarantee. Refusals are logged and count as tool results, not as crashes.
* EVERY COMMAND IS LOGGED, refused or not, to commands.log.
* HARD CAPS: 45 min wall, 80 turns. Hitting either is a RESULT, recorded as
  the failure mode, not an error.
* TWO MODES. `native` uses the OpenAI tools/tool_calls wire format. `react`
  is a documented text protocol for models whose served template has no tool
  support. `auto` probes once with a trivial forced tool call and picks.
  The mode used is recorded per run.

Usage:
  python driver.py --model <id> --task <round1|gsplat> --rundir <dir>
                   [--mode auto|native|react] [--label <tag>]
                   [--max-turns 80] [--max-wall 2700]

Outputs, all inside <rundir>/_harness/:
  transcript.json   full message list, every request and response
  commands.log      every shell command with cwd, exit code, timing
  run.json          the machine-readable result row
  stdout.log        human-readable running log
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = "http://127.0.0.1:1234/v1"
SHELL_TIMEOUT = 300          # per command
TOOL_OUT_CAP = 8000          # chars of tool output handed back to the model
REQ_TIMEOUT = 900            # per HTTP request to LM Studio

# --------------------------------------------------------------------------
# tool schemas (native mode)
# --------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": (
                "Run a shell command and return its stdout, stderr and exit code. "
                "Runs in your working directory unless cwd is given. Times out."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string", "description": "the command line to run"},
                    "cwd": {"type": "string", "description": "directory to run in, relative to the workspace. Optional."},
                },
                "required": ["cmd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write text to a file, creating parent directories. Overwrites.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file and return its contents (truncated if very large).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_chars": {"type": "integer"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List the entries of a directory with sizes.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
]

REACT_PROTOCOL = """\
You do not have a tool-call channel, so use this text protocol instead.

To use a tool, emit EXACTLY ONE fenced block, on its own, like this:

```action
{"tool": "run_shell", "args": {"cmd": "python reader.py"}}
```

Valid tools and args:
  {"tool": "run_shell",  "args": {"cmd": "...", "cwd": "."}}
  {"tool": "write_file", "args": {"path": "reader.py", "content": "..."}}
  {"tool": "read_file",  "args": {"path": "notes.txt"}}
  {"tool": "list_dir",   "args": {"path": "."}}

Rules:
  - One action block per message. Stop generating after the block; the result
    comes back in the next message.
  - The block must be valid JSON. Newlines inside "content" must be escaped
    as \\n.
  - When the whole task is finished, emit the single line: TASK COMPLETE
"""

SYS_TEMPLATE = """\
You are a software engineer working alone at a command line. You complete the \
task below by writing and running programs.

Your workspace is the directory:
  {rundir}
It is your current directory. You may create, read and write files anywhere \
inside it. You cannot reach anything outside it: the harness refuses any path \
outside this directory, and there is no network of any kind.

Environment: Windows, but run_shell executes commands through {shellname}, so \
POSIX commands (ls, cat, head, wc, xxd, grep) work as well as `python`. \
Python {pyver} is on PATH as `python`. No third-party Python packages are \
installed; the standard library only.

Work in steps. Prefer many small commands over one large one. Print things and \
look at what you printed. When you have finished the whole task, say so.

{protocol}
"""


# --------------------------------------------------------------------------
# sandbox
# --------------------------------------------------------------------------

class Refused(Exception):
    pass


ABS_PAT = re.compile(r"""(?:[A-Za-z]:[\\/][^\s"';|)>]*)|(?:(?<![\w.])/(?:[a-zA-Z]|mnt|usr|etc|home|tmp|c|d|f)/[^\s"';|)>]*)""")
NET_PAT = re.compile(r"\b(curl|wget|pip|pip3|git|ssh|scp|nc|ncat|telnet|Invoke-WebRequest|iwr)\b", re.I)
DOTDOT_PAT = re.compile(r"(?:^|[\s\"'=(])\.\.(?:[\\/]|\s|$)")


class Sandbox:
    def __init__(self, rundir):
        self.root = os.path.realpath(rundir)

    def resolve(self, path, must_exist=False):
        if path is None or path == "":
            path = "."
        p = os.path.realpath(os.path.join(self.root, path)) if not os.path.isabs(path) \
            else os.path.realpath(path)
        if not (p == self.root or p.startswith(self.root + os.sep)):
            raise Refused(
                "REFUSED by the harness: %r is outside your workspace. "
                "The only permitted directory is %s and its subdirectories." % (path, self.root))
        if must_exist and not os.path.exists(p):
            raise Refused("No such path: %s" % path)
        return p

    def check_command(self, cmd):
        if NET_PAT.search(cmd):
            raise Refused(
                "REFUSED by the harness: that command uses a network or package tool. "
                "There is no network. Everything you need must come from inside your workspace.")
        if DOTDOT_PAT.search(cmd):
            raise Refused(
                "REFUSED by the harness: that command walks out of your workspace with '..'. "
                "Your workspace is %s; stay inside it." % self.root)
        for m in ABS_PAT.finditer(cmd):
            cand = m.group(0).strip().rstrip('\\/')
            # normalise git-bash style /x/... to X:\...
            probe = cand
            mm = re.match(r"^/([a-zA-Z])/(.*)$", probe)
            if mm:
                probe = mm.group(1).upper() + ":\\" + mm.group(2).replace("/", "\\")
            try:
                rp = os.path.realpath(probe)
            except Exception:
                continue
            if not (rp == self.root or rp.startswith(self.root + os.sep)):
                # allow paths that do not look like they exist on any drive we care about
                raise Refused(
                    "REFUSED by the harness: the command references %r, which is outside "
                    "your workspace (%s). Use relative paths inside your workspace only."
                    % (cand, self.root))


# --------------------------------------------------------------------------
# tools
# --------------------------------------------------------------------------

class Tools:
    def __init__(self, sandbox, cmdlog, shell):
        self.sb = sandbox
        self.cmdlog = cmdlog
        self.shell = shell
        self.n_shell = 0
        self.n_refused = 0

    def _log(self, line):
        with open(self.cmdlog, "a", encoding="utf-8") as f:
            f.write(line.rstrip("\n") + "\n")

    def run_shell(self, cmd, cwd=None, **_):
        self.n_shell += 1
        t0 = time.monotonic()
        try:
            wd = self.sb.resolve(cwd or ".", must_exist=True)
            self.sb.check_command(cmd)
        except Refused as e:
            self.n_refused += 1
            self._log("[%d] REFUSED cwd=%r cmd=%r :: %s" % (self.n_shell, cwd, cmd, e))
            return str(e)
        self._log("[%d] cwd=%s cmd=%s" % (self.n_shell, wd, cmd))
        try:
            if self.shell == "bash":
                argv = [BASH, "-lc", cmd]
            else:
                argv = ["cmd.exe", "/c", cmd]
            p = subprocess.run(argv, cwd=wd, capture_output=True, timeout=SHELL_TIMEOUT)
            out = p.stdout.decode("utf-8", "replace")
            err = p.stderr.decode("utf-8", "replace")
            rc = p.returncode
        except subprocess.TimeoutExpired:
            self._log("    -> TIMEOUT after %ds" % SHELL_TIMEOUT)
            return "TIMEOUT: the command was killed after %d seconds." % SHELL_TIMEOUT
        except Exception as e:
            self._log("    -> HARNESS ERROR %s" % e)
            return "harness error running command: %s" % e
        dt = time.monotonic() - t0
        self._log("    -> rc=%d in %.2fs (%d B out, %d B err)" % (rc, dt, len(out), len(err)))
        body = "exit code: %d\n--- stdout ---\n%s\n--- stderr ---\n%s" % (rc, out, err)
        return clip(body)

    def write_file(self, path, content, **_):
        try:
            p = self.sb.resolve(path)
        except Refused as e:
            self.n_refused += 1
            self._log("WRITE REFUSED %r :: %s" % (path, e))
            return str(e)
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        if content is None:
            content = ""
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        self._log("WRITE %s (%d chars)" % (p, len(content)))
        return "wrote %d characters to %s" % (len(content), path)

    def read_file(self, path, max_chars=None, **_):
        try:
            p = self.sb.resolve(path, must_exist=True)
        except Refused as e:
            self.n_refused += 1
            self._log("READ REFUSED %r :: %s" % (path, e))
            return str(e)
        cap = int(max_chars) if max_chars else TOOL_OUT_CAP
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                data = f.read(cap + 1)
        except Exception as e:
            return "could not read %s: %s" % (path, e)
        self._log("READ %s" % p)
        if len(data) > cap:
            return data[:cap] + "\n...[truncated at %d chars]" % cap
        return data

    def list_dir(self, path=".", **_):
        try:
            p = self.sb.resolve(path, must_exist=True)
        except Refused as e:
            self.n_refused += 1
            self._log("LIST REFUSED %r :: %s" % (path, e))
            return str(e)
        self._log("LIST %s" % p)
        rows = []
        for name in sorted(os.listdir(p)):
            fp = os.path.join(p, name)
            if os.path.isdir(fp):
                rows.append("%-40s <DIR>" % name)
            else:
                rows.append("%-40s %d" % (name, os.path.getsize(fp)))
        return "\n".join(rows) if rows else "(empty directory)"


def clip(s, cap=TOOL_OUT_CAP):
    if len(s) > cap:
        return s[:cap] + "\n...[output truncated by the harness at %d chars]" % cap
    return s


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

def chat(model, messages, tools=None, temperature=0.2, max_tokens=4096):
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API + "/chat/completions", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=REQ_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def probe_native(model):
    """Return True if the served model accepts tools and can emit a tool_call."""
    try:
        r = chat(model, [
            {"role": "system", "content": "You have tools. Use them."},
            {"role": "user", "content": "List the entries of the current directory. Use the list_dir tool with path \".\"."},
        ], tools=TOOLS, max_tokens=512)
    except urllib.error.HTTPError as e:
        return False, "HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:400])
    except Exception as e:
        return False, "error: %s" % e
    msg = r["choices"][0]["message"]
    if msg.get("tool_calls"):
        return True, "emitted %d tool_call(s)" % len(msg["tool_calls"])
    return False, "accepted tools but emitted no tool_call: %r" % (msg.get("content") or "")[:300]


# --------------------------------------------------------------------------
# ReAct parsing
# --------------------------------------------------------------------------

ACTION_RE = re.compile(r"```(?:action|json|tool)?\s*\n(.*?)```", re.S)


def parse_action(text):
    for m in ACTION_RE.finditer(text or ""):
        blob = m.group(1).strip()
        try:
            obj = json.loads(blob)
        except Exception:
            # tolerate a trailing prose line after the JSON object
            try:
                dec = json.JSONDecoder()
                obj, _ = dec.raw_decode(blob)
            except Exception:
                continue
        if isinstance(obj, dict) and obj.get("tool"):
            args = obj.get("args") or {k: v for k, v in obj.items() if k != "tool"}
            return obj["tool"], (args if isinstance(args, dict) else {})
    return None, None


# --------------------------------------------------------------------------
# main loop
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--task", required=True, help="path to the verbatim task prompt file")
    ap.add_argument("--rundir", required=True)
    ap.add_argument("--mode", default="auto", choices=["auto", "native", "react"])
    ap.add_argument("--label", default="")
    ap.add_argument("--max-turns", type=int, default=80)
    ap.add_argument("--max-wall", type=int, default=2700)
    ap.add_argument("--context", default="", help="loaded context length, recorded only")
    ap.add_argument("--quant", default="", help="quantisation, recorded only")
    ap.add_argument("--shell", default="bash", choices=["bash", "cmd"])
    args = ap.parse_args()

    global BASH
    BASH = os.environ.get("WERK_BASH", r"C:\Program Files\Git\bin\bash.exe")

    rundir = os.path.realpath(args.rundir)
    hdir = os.path.join(rundir, "_harness")
    os.makedirs(hdir, exist_ok=True)
    cmdlog = os.path.join(hdir, "commands.log")
    logf = open(os.path.join(hdir, "stdout.log"), "w", encoding="utf-8")

    def say(s):
        print(s, flush=True)
        logf.write(s + "\n")
        logf.flush()

    task_prompt = open(args.task, "r", encoding="utf-8").read()

    mode = args.mode
    probe_note = ""
    if mode == "auto":
        ok, probe_note = probe_native(args.model)
        mode = "native" if ok else "react"
    say("model=%s task=%s mode=%s (%s)" % (args.model, os.path.basename(args.task), mode, probe_note))

    sb = Sandbox(rundir)
    tools = Tools(sb, cmdlog, args.shell)
    dispatch = {"run_shell": tools.run_shell, "write_file": tools.write_file,
                "read_file": tools.read_file, "list_dir": tools.list_dir}

    sysmsg = SYS_TEMPLATE.format(
        rundir=rundir,
        shellname=("Git Bash" if args.shell == "bash" else "cmd.exe"),
        pyver="%d.%d" % sys.version_info[:2],
        protocol=(REACT_PROTOCOL if mode == "react" else
                  "Call tools through the tool-call channel. You have run_shell, "
                  "write_file, read_file and list_dir."),
    )
    messages = [{"role": "system", "content": sysmsg},
                {"role": "user", "content": task_prompt}]

    t0 = time.monotonic()
    turns = 0
    tool_calls = 0
    outcome = "unknown"
    detail = ""
    api_errors = 0
    empty_streak = 0

    while True:
        if turns >= args.max_turns:
            outcome, detail = "turn-cap", "hit the %d-turn cap" % args.max_turns
            break
        if time.monotonic() - t0 > args.max_wall:
            outcome, detail = "wall-cap", "hit the %d s wall cap" % args.max_wall
            break
        turns += 1
        try:
            r = chat(args.model, messages, tools=(TOOLS if mode == "native" else None))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:600]
            api_errors += 1
            say("!! HTTP %s: %s" % (e.code, body))
            if api_errors >= 3:
                outcome, detail = "api-error", "HTTP %s: %s" % (e.code, body)
                break
            messages.append({"role": "user", "content": "The previous message could not be processed. Continue with a smaller step."})
            continue
        except Exception as e:
            api_errors += 1
            say("!! %s" % e)
            if api_errors >= 3:
                outcome, detail = "api-error", str(e)
                break
            continue

        msg = r["choices"][0]["message"]
        content = msg.get("content") or ""
        say("\n--- turn %d (%.0fs) ---\n%s" % (turns, time.monotonic() - t0, content[:1500]))

        if mode == "native":
            tcs = msg.get("tool_calls") or []
            messages.append({"role": "assistant", "content": content,
                             **({"tool_calls": tcs} if tcs else {})})
            if not tcs:
                empty_streak += 1
                # a native-mode model that stops calling tools is either done or stuck
                if is_done(content):
                    outcome, detail = "model-finished", "declared completion"
                    break
                if empty_streak >= 3:
                    outcome, detail = "no-tool-calls", "3 consecutive turns with no tool call"
                    break
                messages.append({"role": "user", "content":
                                 "Continue. Use a tool to make progress, or say TASK COMPLETE if you are done."})
                continue
            empty_streak = 0
            for tc in tcs:
                fn = tc["function"]["name"]
                raw = tc["function"].get("arguments") or "{}"
                try:
                    a = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    a = {}
                tool_calls += 1
                say("  >> %s %s" % (fn, json.dumps(a)[:300]))
                if fn not in dispatch:
                    res = "no such tool: %s. You have run_shell, write_file, read_file, list_dir." % fn
                else:
                    try:
                        res = dispatch[fn](**a)
                    except TypeError as e:
                        res = "bad arguments for %s: %s" % (fn, e)
                say("  << %s" % res[:600].replace("\n", "\n     "))
                messages.append({"role": "tool", "tool_call_id": tc.get("id", "call_%d" % tool_calls),
                                 "name": fn, "content": clip(res)})
        else:
            messages.append({"role": "assistant", "content": content})
            fn, a = parse_action(content)
            if fn is None:
                empty_streak += 1
                if is_done(content):
                    outcome, detail = "model-finished", "declared completion"
                    break
                if empty_streak >= 4:
                    outcome, detail = "no-action-blocks", "4 consecutive turns with no parseable ```action block"
                    break
                messages.append({"role": "user", "content":
                                 "I saw no ```action block. Emit exactly one ```action block with valid JSON, "
                                 "or the line TASK COMPLETE if you are finished."})
                continue
            empty_streak = 0
            tool_calls += 1
            say("  >> %s %s" % (fn, json.dumps(a)[:300]))
            if fn not in dispatch:
                res = "no such tool: %s" % fn
            else:
                try:
                    res = dispatch[fn](**a)
                except TypeError as e:
                    res = "bad arguments for %s: %s" % (fn, e)
            say("  << %s" % res[:600].replace("\n", "\n     "))
            messages.append({"role": "user", "content": "TOOL RESULT (%s):\n%s" % (fn, clip(res))})

    wall = time.monotonic() - t0
    say("\n=== outcome=%s (%s) turns=%d tool_calls=%d wall=%.1fs ===" % (outcome, detail, turns, tool_calls, wall))

    with open(os.path.join(hdir, "transcript.json"), "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=1)
    row = {
        "model": args.model, "quant": args.quant, "context": args.context,
        "task": os.path.basename(args.task), "label": args.label, "mode": mode,
        "probe": probe_note, "outcome": outcome, "detail": detail,
        "turns": turns, "tool_calls": tool_calls, "shell_cmds": tools.n_shell,
        "refusals": tools.n_refused, "wall_s": round(wall, 1),
        "rundir": rundir, "shell": args.shell,
    }
    with open(os.path.join(hdir, "run.json"), "w", encoding="utf-8") as f:
        json.dump(row, f, indent=1)
    say(json.dumps(row))
    logf.close()


DONE_RE = re.compile(r"\b(TASK COMPLETE|task is complete|i (?:have|'ve) (?:now )?(?:finished|completed)|"
                     r"all (?:three )?tasks? (?:are )?(?:now )?complete|the task is (?:now )?(?:done|finished)|"
                     r"REPORT\.md (?:has been|is) written)\b", re.I)


def is_done(content):
    return bool(DONE_RE.search(content or ""))


if __name__ == "__main__":
    main()
