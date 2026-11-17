#!/usr/bin/env python3
"""werk-office -- Word, Excel and PowerPoint documents to werk packages and back.

    py -3.12 werk_office.py export <in.docx|.xlsx|.pptx> <out.werk> [--no-pdf] [--name N]
                                   [--created RFC3339] [--uuid UUID]
    py -3.12 werk_office.py import <in.werk> <out.docx|.xlsx|.pptx> [--rebuild]
    py -3.12 werk_office.py info   <in.werk>

export  writes rich-document/1 (.docx), spreadsheet/1 (.xlsx) or presentation/1 (.pptx),
        as the profile definitions say (they travel in every package, under spec/):
          * the ORIGINAL Office file, byte for byte:
              .docx -> core.package.binary (meta.payload_format "opc")
              .pptx -> core.media.asset    (encoding "zip")
              .xlsx -> x.werk-office.source (spreadsheet/1 has no core node type that
                       carries a whole package, so this one is an extension node)
          * a PDF rendition made by the Office application itself (ExportAsFixedFormat /
            SaveAs PDF, a private COM instance): x.werk-office.rendition for .docx and
            .xlsx, a core.media.asset (encoding "pdf") for .pptx; stamped `measured`
            with the original file as its one input
          * the profile's structured nodes where the Office data maps (body text with
            bold / italic / underline / strike / size runs and tables; sheets with
            constants, formulas and error values; slides with positioned text shapes),
            decoded from the original file by this tool with the standard library and
            stamped `measured` (their input is the original file)
import  writes an Office file from a package: the carried original, byte for byte and
        hash-checked, when the package has one; otherwise (or with --rebuild) a new
        document built from the structured nodes through the Office application.

Office is driven ONLY through COM DispatchEx (a private instance). This tool never
attaches to an Office window the user has open, and it ends exactly the process it
started (PowerPoint is single-instance: when one is already running, PowerPoint work is
refused). Python 3.8+, pywin32 for the COM part; the werk part is the vendored release
library (vendor/werk_single.py).
"""

import argparse
import datetime
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
import zipfile
import zlib
from collections import OrderedDict
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "vendor"))
import werk_single as werk  # noqa: E402

VERSION = "0.1.0"
TOOL = OrderedDict([("tool", "werk-office"), ("version", VERSION)])
PROFILES = os.path.join(HERE, "profiles")

KIND = {".docx": "rich-document", ".xlsx": "spreadsheet", ".pptx": "presentation"}
MIME = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
X_SOURCE, X_RENDITION = "x.werk-office.source", "x.werk-office.rendition"
OOXML_METHOD = {"method": "werk-office-ooxml-1", "tool": "werk-office %s" % VERSION}


class OfficeError(Exception):
    pass


def sha(b):
    return hashlib.sha256(b).hexdigest()


def now_utc():
    return datetime.datetime.utcnow().replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def compact(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"


def load_example(profile, name):
    """Import one of the profile's own example scripts (they travel in spec/examples/)."""
    path = os.path.join(PROFILES, profile, "spec", "examples", profile, name)
    spec = importlib.util.spec_from_file_location("werk_office_%s_%s" % (profile.replace("-", "_"),
                                                                         name[:-3]), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# =============================================================================================
# COM: one private Office instance, and only that one is ever ended
# =============================================================================================

EXE = {"Word.Application": "WINWORD.EXE", "Excel.Application": "EXCEL.EXE",
       "PowerPoint.Application": "POWERPNT.EXE"}


def _pids(image):
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + image, "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    return {int(l.split('","')[1]) for l in out.splitlines() if l.startswith('"')}


class Office(object):
    """with Office("Word.Application") as o: o.app ...  -- DispatchEx, never GetObject."""

    log = []      # (progid, pid, how it ended) for every instance this process started

    def __init__(self, progid, quit_timeout=30):
        self.progid, self.quit_timeout = progid, quit_timeout
        self.app, self.pid, self.version = None, None, None

    def __enter__(self):
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        image = EXE[self.progid]
        before = _pids(image)
        if self.progid == "PowerPoint.Application" and before:
            raise OfficeError("PowerPoint is already running (pid %s); PowerPoint is single-instance, "
                              "so DispatchEx would attach to it. Refused: close it first."
                              % sorted(before))
        self.app = win32com.client.DispatchEx(self.progid)
        new = _pids(image) - before
        if len(new) != 1:
            # cannot tell which process is ours: never kill, and say so
            self.pid = None
            Office.log.append((self.progid, None, "pid unknown: %d new process(es)" % len(new)))
        else:
            self.pid = new.pop()
        self.version = str(self.app.Version)
        if self.progid != "PowerPoint.Application":
            self.app.Visible = False
        try:
            self.app.DisplayAlerts = 0 if self.progid != "Excel.Application" else False
        except Exception:
            pass
        return self

    def __exit__(self, *exc):
        app, self.app = self.app, None
        ended = "quit"
        if self.progid != "PowerPoint.Application":
            t = threading.Thread(target=self._quit, args=(app,), daemon=True)
            t.start()
            t.join(self.quit_timeout)
        del app
        time.sleep(2)
        if self.pid and self.pid in _pids(EXE[self.progid]):
            subprocess.run(["taskkill", "/PID", str(self.pid), "/F"], capture_output=True)
            ended = "killed (pid %d; Quit %s)" % (self.pid, "not called: PowerPoint Close/Quit hangs"
                                                  if self.progid == "PowerPoint.Application"
                                                  else "did not end the process")
        Office.log.append((self.progid, self.pid, ended))
        return False

    @staticmethod
    def _quit(app):
        import pythoncom
        try:
            app.Quit()
        except Exception:
            pass


STEPS = []   # (seconds, progid, step) -- where a hang happened, when one does


def com_job(progid, fn, timeout=None):
    """Run fn(office) on a worker thread that owns its own private instance. fn may call
    office.done(value) as soon as its work is on disk; for PowerPoint, whose Close / Quit /
    even the release of a presentation reference can block for ever, the instance is then
    killed at once. If nothing comes back within `timeout` seconds, the instance THIS job
    started (and only it) is killed and OfficeError names the last step reached."""
    timeout = timeout or float(os.environ.get("WERK_OFFICE_TIMEOUT", "420"))
    box = {}

    def work():
        try:
            with Office(progid) as o:
                box["pid"] = o.pid
                o.done = lambda value: box.setdefault("result", value)
                value = fn(o)
                box.setdefault("result", value)
        except Exception as exc:          # reported to the caller
            box.setdefault("error", exc)

    t0 = time.time()
    th = threading.Thread(target=work, daemon=True)
    th.start()
    while time.time() - t0 < timeout and "result" not in box and "error" not in box:
        time.sleep(0.5)
    pid = box.get("pid")
    if "result" in box or "error" in box:
        if progid == "PowerPoint.Application":
            th.join(3)
        else:
            th.join(90)                   # Quit, then Office.__exit__ kills if Quit left it
        if th.is_alive() and pid:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            Office.log.append((progid, pid, "work done; instance did not end -> killed"))
        if "error" in box:
            raise OfficeError("%s: %r" % (progid, box["error"]))
        return box["result"]
    if pid:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    Office.log.append((progid, pid, "HUNG after %.0f s -> killed" % (time.time() - t0)))
    last = [x for x in STEPS if x[1] == progid]
    raise OfficeError("%s did not finish in %.0f s (last step: %s); its instance (pid %s) was killed"
                      % (progid, timeout, last[-1][2] if last else "starting", pid))


def step(progid, what):
    STEPS.append((round(time.time(), 1), progid, what))


PROGID = {".docx": "Word.Application", ".xlsx": "Excel.Application", ".pptx": "PowerPoint.Application"}


def isolated(kind, args, progid, timeout=None, attempts=2):
    """Run one COM job in a child process (its main thread owns the Office instance). The
    child records the pid of the instance it started in a pid file the moment it has one;
    on a hang the parent kills exactly that pid and the child, and tries once more. Word
    2016 on the gate machine blocks in Documents.Open now and then with no dialog to be seen
    (COM add-ins: Dragon, Acrobat PDFMaker, 3Dconnexion load into every instance)."""
    timeout = timeout or float(os.environ.get("WERK_OFFICE_TIMEOUT", "420"))
    work = os.path.join(os.path.dirname(os.path.abspath(args[-1])), ".werk-office-job")
    os.makedirs(work, exist_ok=True)
    last = None
    for attempt in range(1, attempts + 1):
        pf, rf = os.path.join(work, "pid.txt"), os.path.join(work, "result.json")
        for f in (pf, rf):
            if os.path.isfile(f):
                os.remove(f)
        cmd = [sys.executable, os.path.abspath(__file__), "_job", kind, pf, rf] + list(args)
        t0 = time.time()
        child = subprocess.Popen(cmd)
        try:
            child.wait(timeout)
        except subprocess.TimeoutExpired:
            pid = int(open(pf).read().strip()) if os.path.isfile(pf) and open(pf).read().strip() else None
            if pid:
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            child.kill()
            child.wait()
            Office.log.append((progid, pid, "attempt %d HUNG after %.0f s -> killed" % (attempt, time.time() - t0)))
            last = "%s did not finish in %.0f s (attempt %d); its instance (pid %s) was killed" % (
                progid, timeout, attempt, pid)
            continue
        if os.path.isfile(rf):
            r = json.load(open(rf, encoding="utf-8"))
            for f in (pf, rf):
                if os.path.isfile(f):
                    os.remove(f)
            try:
                os.rmdir(work)
            except OSError:
                pass
            for x in r.get("log", []):
                Office.log.append(tuple(x))
            if "error" in r:
                raise OfficeError(r["error"])
            return r["result"]
        last = "%s job exited %s without a result" % (progid, child.returncode)
    raise OfficeError(last)


def _job_main(argv):
    """werk_office.py _job <pdf|rebuild> <pidfile> <resultfile> args...  (internal)"""
    kind, pf, rf, args = argv[0], argv[1], argv[2], argv[3:]
    out = {}
    try:
        if kind == "pdf":
            ext, src, dst = args
            progid = PROGID[ext]
            fn = lambda o: _office_pdf(o, ext, src, dst)
        elif kind == "reopen":
            src, dst = args            # dst: unused marker path (its folder holds the job files)
            ext = os.path.splitext(src)[1].lower()
            progid = PROGID[ext]
            fn = lambda o: _reopen(o, ext, os.path.abspath(src))
        else:
            src, dst = args
            ext = os.path.splitext(dst)[1].lower()
            progid = PROGID[ext]
            pkg = werk.open(src)
            rb = {".docx": rebuild_docx, ".xlsx": rebuild_xlsx, ".pptx": rebuild_pptx}[ext]
            fn = lambda o: rb(pkg, dst, o)
        o = Office(progid)
        o.__enter__()
        open(pf, "w").write(str(o.pid or ""))
        o.done = lambda value: None
        try:
            out["result"] = fn(o)
        finally:
            if progid == "PowerPoint.Application":
                if o.pid:
                    subprocess.run(["taskkill", "/PID", str(o.pid), "/F"], capture_output=True)
                Office.log.append((progid, o.pid, "killed after the work (PowerPoint Close/Quit hangs)"))
            else:
                o.__exit__(None, None, None)
    except Exception as exc:
        out["error"] = "%s: %r" % (kind, exc)
    out["log"] = [list(x) for x in Office.log]
    with open(rf, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    sys.stdout.flush()
    os._exit(0)          # never let a COM release block the exit


def word_load(o, src):
    """Open a .docx read-only in the private Word instance, after a warm-up.

    Measured on the gate machine (Word 2016 16.0.4393; the Dragon, Acrobat PDFMaker and
    3Dconnexion COM add-ins load into every instance): a Documents.Open issued as the
    instance's FIRST document operation blocked for good in 4 of 5 attempts (no dialog window
    in the process; killed after 150-600 s); issued after one document had been created and
    closed in the same instance it returned at once in 2 of 2. So: create and close an empty
    document first. isolated() still kills and retries a job that hangs."""
    step(o.progid, "warm-up: Documents.Add + Close")
    d = o.app.Documents.Add()
    d.Close(0)
    step(o.progid, "Documents.Open")
    return o.app.Documents.Open(FileName=src, ConfirmConversions=False, ReadOnly=True,
                                AddToRecentFiles=False, Visible=False, NoEncodingDialog=True)


def _reopen(o, ext, src):
    """Open a file read-only in the Office application and say what it holds."""
    p = o.progid
    step(p, "reopen " + ext)
    if ext == ".docx":
        doc = word_load(o, src)
        r = {"paragraphs": doc.Paragraphs.Count, "tables": doc.Tables.Count,
             "text": doc.Content.Text, "pages": doc.ComputeStatistics(2)}
        doc.Close(0)
    elif ext == ".xlsx":
        wb = o.app.Workbooks.Open(src, 0, True)
        r = {"sheets": []}
        for i in range(wb.Worksheets.Count):
            ws = wb.Worksheets(i + 1)
            cells = {}
            used = ws.UsedRange
            for c in used.Cells:
                if c.Formula not in (None, ""):
                    v2 = c.Value2
                    cells[c.Address.replace("$", "")] = {"formula": c.Formula, "value": c.Text,
                                                         "value2": v2 if isinstance(v2, (str, float, int, bool)) else repr(v2)}
            r["sheets"].append({"name": ws.Name, "used": used.Address, "cells": cells})
        wb.Close(False)
    else:
        pres = o.app.Presentations.Open(src, True, False, False)
        texts = []
        for i in range(pres.Slides.Count):
            sl = pres.Slides(i + 1)
            t = []
            for j in range(sl.Shapes.Count):
                sh = sl.Shapes(j + 1)
                if sh.HasTextFrame:
                    t.append(sh.TextFrame.TextRange.Text)
            texts.append(t)
        r = {"slides": pres.Slides.Count, "texts": texts,
             "size": [pres.PageSetup.SlideWidth, pres.PageSetup.SlideHeight]}
    r["host"] = "%s %s" % (p.split(".")[0], o.version)
    return r


def reopen(path):
    marker = os.path.abspath(path) + ".reopen"
    return isolated("reopen", [os.path.abspath(path), marker], PROGID[os.path.splitext(path)[1].lower()])


def office_pdf(ext, src, pdf_out):
    return isolated("pdf", [ext, os.path.abspath(src), os.path.abspath(pdf_out)], PROGID[ext])


def _office_pdf(o, ext, src, pdf_out):
    """The host application's own PDF of `src`. Returns the host version string."""
    src, pdf_out = os.path.abspath(src), os.path.abspath(pdf_out)
    if os.path.isfile(pdf_out):
        os.remove(pdf_out)
    p = o.progid
    if ext == ".docx":
        doc = word_load(o, src)
        step(p, "ExportAsFixedFormat")
        doc.ExportAsFixedFormat(pdf_out, 17)                   # wdExportFormatPDF
        step(p, "Close")
        doc.Close(0)
        return "Microsoft Word %s" % o.version
    if ext == ".xlsx":
        step(p, "Workbooks.Open")
        wb = o.app.Workbooks.Open(src, 0, True)               # UpdateLinks=0, ReadOnly
        step(p, "ExportAsFixedFormat")
        wb.ExportAsFixedFormat(0, pdf_out)                    # xlTypePDF
        step(p, "Close")
        wb.Close(False)
        return "Microsoft Excel %s" % o.version
    if ext == ".pptx":
        step(p, "Presentations.Open")
        pres = o.app.Presentations.Open(src, True, False, False)   # ReadOnly, Untitled, WithWindow
        step(p, "SaveAs PDF")
        pres.SaveAs(pdf_out, 32)                                   # ppSaveAsPDF
        step(p, "saved")
        o.done("Microsoft PowerPoint %s" % o.version)
        return "Microsoft PowerPoint %s" % o.version
    raise OfficeError("no PDF route for %s" % ext)


# =============================================================================================
# OOXML -> structured data (standard library only)
# =============================================================================================

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
}


def q(prefix, tag):
    return "{%s}%s" % (NS[prefix], tag)


def _rels(z, part):
    d, f = part.rsplit("/", 1) if "/" in part else ("", part)
    rp = (d + "/" if d else "") + "_rels/" + f + ".rels"
    out = {}
    if rp in z.namelist():
        for r in ET.fromstring(z.read(rp)).findall(q("rel", "Relationship")):
            t = r.get("Target")
            if r.get("TargetMode") == "External":
                continue
            if t.startswith("/"):
                full = t[1:]
            else:
                parts = (d.split("/") if d else []) + t.split("/")
                stack = []
                for s in parts:
                    if s == "..":
                        stack.pop()
                    elif s and s != ".":
                        stack.append(s)
                full = "/".join(stack)
            out[r.get("Id")] = full
    return out


def core_props(z):
    if "docProps/core.xml" not in z.namelist():
        return {}
    root = ET.fromstring(z.read("docProps/core.xml"))
    get = lambda p, t: (root.findtext(q(p, t)) or "")
    return {"title": get("dc", "title"), "subject": get("dc", "subject"), "creator": get("dc", "creator"),
            "keywords": get("cp", "keywords"), "description": get("dc", "description"),
            "lastModifiedBy": get("cp", "lastModifiedBy"), "created": get("dcterms", "created"),
            "modified": get("dcterms", "modified")}


# ---- Word -----------------------------------------------------------------------------------

def _wbool(el):
    if el is None:
        return None
    v = el.get(q("w", "val"))
    return not (v in ("0", "false", "off"))


def _run_props(rpr):
    props = OrderedDict()
    if rpr is None:
        return props
    for tag, key in (("b", "bold"), ("i", "italic"), ("strike", "strike")):
        v = _wbool(rpr.find(q("w", tag)))
        if v is not None:
            props[key] = v
    u = rpr.find(q("w", "u"))
    if u is not None:
        val = u.get(q("w", "val")) or "single"
        props["underline"] = val if val in ("none", "single", "words", "double", "thick", "dotted",
                                             "dash", "dotDash", "dotDotDash", "wave") else "single"
    sz = rpr.find(q("w", "sz"))
    if sz is not None and (sz.get(q("w", "val")) or "").isdigit():
        props["size"] = int(sz.get(q("w", "val"))) / 2.0
    return props


def _para(p):
    """w:p -> a rich-document paragraph block (text + runs by UTF-8 byte length)."""
    pieces = []           # (text, props)
    for r in p.iter(q("w", "r")):
        props = _run_props(r.find(q("w", "rPr")))
        buf = []
        for ch in r:
            if ch.tag == q("w", "t"):
                buf.append(ch.text or "")
            elif ch.tag == q("w", "tab"):
                buf.append("\t")
            elif ch.tag in (q("w", "br"), q("w", "cr")):
                buf.append("\f" if ch.get(q("w", "type")) == "page" else "\n")
        if buf:
            pieces.append(("".join(buf), props))
    text = "".join(t for t, _ in pieces)
    runs = []
    for t, props in pieces:
        n = len(t.encode("utf-8"))
        if not n:
            continue
        if runs and runs[-1].get("props", {}) == props:
            runs[-1]["len"] += n
            continue
        run = OrderedDict([("len", n)])
        if props:
            run["props"] = props
        runs.append(run)
    if not runs:
        runs = [OrderedDict([("len", 0)])] if not text else [OrderedDict([("len", len(text.encode("utf-8")))])]
        if not text:
            runs = []
    block = OrderedDict([("kind", "para"), ("text", text), ("runs", runs)])
    ppr = p.find(q("w", "pPr"))
    if ppr is not None:
        jc = ppr.find(q("w", "jc"))
        ol = ppr.find(q("w", "outlineLvl"))
        props = OrderedDict()
        if jc is not None and jc.get(q("w", "val")) in ("left", "center", "right", "both"):
            props["align"] = {"both": "justify"}.get(jc.get(q("w", "val")), jc.get(q("w", "val")))
        if ol is not None and (ol.get(q("w", "val")) or "").isdigit():
            props["outlineLevel"] = int(ol.get(q("w", "val")))
        if props:
            block["props"] = props
    return block


def _blocks(parent):
    out = []
    for el in parent:
        if el.tag == q("w", "p"):
            out.append(_para(el))
        elif el.tag == q("w", "tbl"):
            grid = [int(g.get(q("w", "w")) or 0) / 20.0 for g in el.iter(q("w", "gridCol"))]
            rows = []
            for tr in el.findall(q("w", "tr")):
                cells = []
                for tc in tr.findall(q("w", "tc")):
                    cell = OrderedDict([("blocks", _blocks(tc))])
                    span = tc.find(q("w", "tcPr") + "/" + q("w", "gridSpan"))
                    if span is not None and (span.get(q("w", "val")) or "1") != "1":
                        cell["props"] = {"span": int(span.get(q("w", "val")))}
                    cells.append(cell)
                rows.append(OrderedDict([("cells", cells)]))
            out.append(OrderedDict([("kind", "table"), ("grid", grid), ("rows", rows)]))
        elif el.tag == q("w", "sdt"):
            content = el.find(q("w", "sdtContent"))
            if content is not None:
                out.extend(_blocks(content))
    return out


def read_docx(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    body = ET.fromstring(z.read("word/document.xml")).find(q("w", "body"))
    return {"blocks": _blocks(body), "props": core_props(z)}


# ---- Excel ----------------------------------------------------------------------------------

def _col_row(ref):
    m = re.match(r"^([A-Z]+)(\d+)$", ref)
    col = 0
    for ch in m.group(1):
        col = col * 26 + (ord(ch) - 64)
    return int(m.group(2)) - 1, col - 1


ERROR_CODES = {"#NULL!": 1, "#DIV/0!": 2, "#VALUE!": 3, "#REF!": 4, "#NAME?": 5, "#NUM!": 6, "#N/A": 7,
               "#GETTING_DATA": 8, "#SPILL!": 9, "#CALC!": 14, "#CIRC!": 15}


def read_xlsx(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    wbx = ET.fromstring(z.read("xl/workbook.xml"))
    rels = _rels(z, "xl/workbook.xml")
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(q("s", "si")):
            shared.append("".join(t.text or "" for t in si.iter(q("s", "t"))))
    sheets, notes = [], []
    for sh in wbx.find(q("s", "sheets")).findall(q("s", "sheet")):
        part = rels[sh.get(q("r", "id"))]
        root = ET.fromstring(z.read(part))
        cells = {}
        shared_as_value = 0
        for c in root.iter(q("s", "c")):
            r, col = _col_row(c.get("r"))
            t = c.get("t") or "n"
            f = c.find(q("s", "f"))
            v = c.findtext(q("s", "v"))
            if f is not None and (f.text or "").strip():
                cells[(r, col)] = ("=", f.text)
                continue
            if f is not None:
                shared_as_value += 1          # a shared-formula follower: kept as its cached value
            if t == "s" and v is not None:
                cells[(r, col)] = shared[int(v)]
            elif t == "inlineStr":
                cells[(r, col)] = "".join(x.text or "" for x in c.iter(q("s", "t")))
            elif t == "str" and v is not None:
                cells[(r, col)] = v
            elif t == "b" and v is not None:
                cells[(r, col)] = v == "1"
            elif t == "e" and v is not None:
                cells[(r, col)] = ("#", v)
            elif v is not None:
                fv = float(v)
                cells[(r, col)] = int(fv) if fv.is_integer() and abs(fv) < 2 ** 53 else fv
        if shared_as_value:
            notes.append("%s: %d shared-formula cell(s) stored as their cached values"
                         % (sh.get("name"), shared_as_value))
        sheets.append({"name": sh.get("name"), "cells": cells})
    return {"sheets": sheets, "props": core_props(z), "notes": notes}


# ---- PowerPoint -----------------------------------------------------------------------------

EMU_PER_PT = 12700.0
PLACEHOLDER_BOX = {"title": (48, 30, 864, 90), "ctrTitle": (72, 160, 816, 120),
                   "subTitle": (144, 300, 672, 90)}


def _shape_text(tx):
    paras = []
    for ap in tx.findall(q("a", "p")):
        runs = []
        for r in ap:
            if r.tag == q("a", "r"):
                props = OrderedDict()
                rpr = r.find(q("a", "rPr"))
                if rpr is not None:
                    for k, key in (("b", "bold"), ("i", "italic")):
                        if rpr.get(k) is not None:
                            props[key] = rpr.get(k) in ("1", "true")
                    if (rpr.get("sz") or "").isdigit():
                        props["size"] = int(rpr.get("sz")) / 100.0
                run = OrderedDict([("text", r.findtext(q("a", "t")) or "")])
                if props:
                    run["props"] = props
                runs.append(run)
            elif r.tag == q("a", "br"):
                runs.append(OrderedDict([("kind", "break")]))
        para = OrderedDict([("runs", runs)])
        ppr = ap.find(q("a", "pPr"))
        if ppr is not None and (ppr.get("lvl") or "0") != "0":
            para["level"] = int(ppr.get("lvl"))
        paras.append(para)
    return paras


def read_pptx(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    pres = ET.fromstring(z.read("ppt/presentation.xml"))
    rels = _rels(z, "ppt/presentation.xml")
    sz = pres.find(q("p", "sldSz"))
    size = (int(sz.get("cx")) / EMU_PER_PT, int(sz.get("cy")) / EMU_PER_PT)
    slides, notes = [], []
    lst = pres.find(q("p", "sldIdLst"))
    for i, sid in enumerate(lst.findall(q("p", "sldId")) if lst is not None else []):
        part = rels[sid.get(q("r", "id"))]
        root = ET.fromstring(z.read(part))
        shapes, skipped = [], 0
        for sp in root.iter():
            if sp.tag == q("p", "pic") or sp.tag == q("p", "graphicFrame"):
                skipped += 1
                continue
            if sp.tag != q("p", "sp"):
                continue
            nv = sp.find(q("p", "nvSpPr") + "/" + q("p", "cNvPr"))
            ph = sp.find(q("p", "nvSpPr") + "/" + q("p", "nvPr") + "/" + q("p", "ph"))
            off = sp.find(q("p", "spPr") + "/" + q("a", "xfrm") + "/" + q("a", "off"))
            ext = sp.find(q("p", "spPr") + "/" + q("a", "xfrm") + "/" + q("a", "ext"))
            if off is not None and ext is not None:
                box = (int(off.get("x")) / EMU_PER_PT, int(off.get("y")) / EMU_PER_PT,
                       int(ext.get("cx")) / EMU_PER_PT, int(ext.get("cy")) / EMU_PER_PT)
                inherited = False
            else:
                kind = ph.get("type", "body") if ph is not None else "body"
                box = PLACEHOLDER_BOX.get(kind, (72, 140, size[0] - 144, size[1] - 200))
                inherited = True
            geom = sp.find(q("p", "spPr") + "/" + q("a", "prstGeom"))
            tx = sp.find(q("p", "txBody"))
            shapes.append({"id": int(nv.get("id")), "name": nv.get("name") or "",
                           "box": box, "inherited_box": inherited,
                           "preset": geom.get("prst") if geom is not None else "rect",
                           "paragraphs": _shape_text(tx) if tx is not None else []})
        if skipped:
            notes.append("slide %d: %d picture / table / chart frame(s) not mapped (they are in the "
                         "original file)" % (i + 1, skipped))
        slides.append({"shapes": shapes})
    return {"size": size, "slides": slides, "props": core_props(z), "notes": notes}


# =============================================================================================
# the package writer: the vendored release PackageWriter, plus what the Office profiles need
# =============================================================================================

class Capsule(werk.PackageWriter):
    """A PackageWriter for one of the three Office profiles: the release library's documented
    API (`conventions_map=`, `add_readme_file`, `add_spec_file`, `set_format`) plus format
    definitions with their core.tool nodes, and the loader-capability intersection below."""

    def __init__(self, profile, name, summary, created, uuid):
        d = os.path.join(PROFILES, profile)
        self.pdir = d
        self.facts = json.load(open(os.path.join(d, "profile.json"), encoding="utf-8"))
        self.vendored = json.load(open(os.path.join(PROFILES, "VENDORED.json"), encoding="utf-8"))
        spec_files = {}
        for root, _dirs, names in os.walk(os.path.join(d, "spec")):
            for n in names:
                full = os.path.join(root, n)
                rel = "/".join(os.path.relpath(full, d).split(os.sep))
                spec_files[rel] = open(full, "rb").read()
        readme = ("This file is a werk package (profile %s) written by werk-office %s from a "
                  "Microsoft Office document.\n\nStart with HOW-TO-READ.md, then %s. Everything "
                  "a reader needs is inside this file: the specification under spec/ and three "
                  "dependency-free readers under loaders/.\n\nThe original Office file is carried "
                  "byte for byte; a PDF made by the Office application sits beside it.\n"
                  % (self.facts["profile"], VERSION, self.facts["profile_spec"]))
        super(Capsule, self).__init__(
            self.facts["profile"], name, summary=summary, uuid=uuid, created=created,
            conventions=self.facts["conventions"], generator=TOOL, producer=TOOL,
            readme_text=readme, manifest_schema=self.facts["manifest_schema"],
            profile_spec=self.facts["profile_spec"], spec_files=spec_files,
            conventions_map=self.facts["conventions_map"])
        # readme: README.txt (payload) + HOW-TO-READ.md, CRAFT-BASE section 1
        self.add_readme_file("HOW-TO-READ.md", open(os.path.join(d, "HOW-TO-READ.md"), "rb").read(),
                             "text/markdown")
        self.preview("HOW-TO-READ.md")
        self.formats_added = set()
        # The release loaders declare capabilities (summarize-points, summarize-gsplat) that the
        # Office profiles' manifest schemas, written before them, do not list: werkc kills the
        # loader node as schema-invalid. Declared here at the profile's permitted set -- an
        # under-claim, never an over-claim (reported to W2 as a library/profile mismatch).
        ms = json.load(open(os.path.join(d, self.facts["manifest_schema"]), encoding="utf-8"))
        allowed = ms["$defs"]["loaderMeta"]["properties"]["capabilities"]["items"]["enum"]
        self.dropped_capabilities = {}
        for n in self.nodes.values():
            if n["type"] == "core.loader":
                meta = OrderedDict(n["meta"])
                caps = meta.get("capabilities", [])
                meta["capabilities"] = [c for c in caps if c in allowed]
                gone = [c for c in caps if c not in allowed]
                if gone:
                    self.dropped_capabilities[n["node_id"]] = gone
                n["meta"] = meta

    def use_format(self, fid):
        if fid in self.formats_added:
            return
        self.formats_added.add(fid)
        rec = self.vendored["formats"][fid]
        for req in rec["requires"]:
            self.use_format(req)
        fd = os.path.join(PROFILES, "_formats")
        path = "spec/formats/%s.md" % fid
        self.add_spec_file(path, open(os.path.join(fd, path), "rb").read())
        self.set_format(fid, path)
        for t in rec["tools"]:
            files = [self.file(f["path"], open(os.path.join(fd, f["path"]), "rb").read(),
                               f.get("media_type"), f.get("role")) for f in t["files"]]
            self.add_node(t["node_id"], "core.tool", files, note=t["note"],
                          payload_file=t["payload_file"], meta=t.get("meta"))
            self.set_schema("core.tool", "spec/schemas/core.tool.schema.json")

    def typed(self, node_type):
        """Declare the schema / layout the profile names for this type, when it names one."""
        if node_type in self.facts["schemas"]:
            self.set_schema(node_type, self.facts["schemas"][node_type])
        if node_type in self.facts["layouts"]:
            self.set_layout(node_type, self.facts["layouts"][node_type])

    def node(self, node_id, node_type, files, note, **kw):
        self.typed(node_type)
        return self.add_node(node_id, node_type, files, note, **kw)

    def x_layout(self):
        path = "spec/layouts/x.werk-office.layout.txt"
        if path not in self.blobs:
            self.add_spec_file(path, X_LAYOUT.encode("utf-8"))
        for t in (X_SOURCE, X_RENDITION):
            self.set_layout(t, path)

    def finish_revisions(self, note):
        uses = OrderedDict((nid, 1) for nid in self.nodes)
        rec = OrderedDict([("schema_version", 1), ("revision", 1), ("kind", "save"), ("note", note),
                           ("created", self.created), ("producer", dict(TOOL)), ("nodes", uses)])
        data = (json.dumps(rec, indent=2, sort_keys=True) + "\n").encode("utf-8")
        self.node("revisions", "core.revisions",
                  [self.file("revisions/revision.json", data, "application/json")], note=note)



X_LAYOUT = """x.werk-office.source / x.werk-office.rendition -- extension node layouts (werk-office)
=========================================================================================

Written by werk-office (the werk release's Microsoft Office plug-in). A reader that does not
know these types skips them; nothing core requires them (law 12).

x.werk-office.source
    One file, the original Office document exactly as the application saved it (an OPC
    package, i.e. a ZIP: .docx / .xlsx / .pptx; spec/formats/opc.md and zip.md define the
    container when this package carries them). meta.original_name is the file name it had;
    meta.media_type its declared type. Used where the profile has no core node type that
    carries a whole package (spreadsheet/1). Epistemic: authored.

x.werk-office.rendition
    One file, a PDF (ISO 32000) the Office application itself exported from the
    x.werk-office.source / core original of this package (Word/Excel ExportAsFixedFormat,
    PowerPoint SaveAs PDF). meta.payload_format is "pdf" (spec/formats/pdf.md when carried).
    Epistemic: measured; input_files is the original file, input_params names the host
    application and its version. A rendition is a convenience: nothing may be measured from it.
"""


# =============================================================================================
# export
# =============================================================================================

def _blocks_files(node_id, blocks, story=None):
    text = b"[\n" + b",\n".join(json.dumps(b, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                               for b in blocks) + b"\n]\n"
    stored = zlib.compress(text, 6)
    header = OrderedDict([("schema_version", 1), ("story", story or {"kind": "body"}),
                          ("blocks", OrderedDict([("count", len(blocks)), ("role", "blocks"),
                                                  ("format", "zlib-deflate"),
                                                  ("stored_size", len(stored)), ("stored_sha256", sha(stored)),
                                                  ("inflated_size", len(text)),
                                                  ("inflated_sha256", sha(text))]))])
    return compact(header), stored


def _attach_original(c, ext, data, original_name, as_core):
    """Returns the package path of the original file."""
    if as_core == "package-binary":
        c.use_format("opc")
        path = "package/package-original.zip"
        c.node("package-original", "core.package.binary",
               [c.file(path, data, MIME[ext])],
               note="The original %s file, byte for byte, as Microsoft Office saved it. Writing a "
                    ".docx again from this package returns these bytes." % ext,
               meta=OrderedDict([("payload_format", "opc")]))
        return path, "package-original"
    c.x_layout()
    path = "x/werk-office/original" + ext
    c.node("x-original", X_SOURCE, [c.file(path, data, MIME[ext])],
           note="The original %s file, byte for byte, as Microsoft Office saved it (an extension "
                "node: this profile has no core node type for a whole package)." % ext,
           meta=OrderedDict([("original_name", original_name), ("media_type", MIME[ext])]))
    return path, "x-original"


def _attach_pdf_x(c, pdf, host, orig_path, orig_node):
    c.x_layout()
    path = "x/werk-office/rendition.pdf"
    c.node("x-rendition-pdf", X_RENDITION, [c.file(path, pdf, "application/pdf")],
           note="A PDF of the document exported by %s itself from the original file." % host,
           epistemic="measured", input_files=[orig_path],
           input_params=OrderedDict([("method", "office-export-pdf"), ("host", host)]),
           meta=OrderedDict([("payload_format", "pdf")]),
           edges=[{"to": orig_node, "kind": "requires", "role": "rendered-from"}])


def export_docx(c, data, pdf, host, original_name, notes):
    orig_path, orig_node = _attach_original(c, ".docx", data, original_name, "package-binary")
    doc = read_docx(data)
    c.use_format("zlib-deflate")
    header, stored = _blocks_files("body-000001", doc["blocks"])
    measured = dict(epistemic="measured", input_files=[orig_path], input_params=dict(OOXML_METHOD))
    c.node("body-000001", "core.text.blocks",
           [c.file("text/body-000001.json", header, "application/json", "payload"),
            c.file("text/body-000001.blocks.zlib", stored, "application/zlib", "blocks")],
           note="The body text (%d block(s)) decoded from the original .docx by werk-office."
                % len(doc["blocks"]),
           payload_file="text/body-000001.json",
           meta=OrderedDict([("file_formats", {"blocks": "zlib-deflate"})]), **measured)
    rd = load_example("rich-document", "read_document.py")
    plain = rd.plain_text(doc["blocks"])
    plain_b = plain.encode("utf-8")
    edges = [{"to": "body-000001", "kind": "enhances", "role": "body"}]
    plain_nodes = [None]
    if plain.strip():
        c.node("text-000001", "core.preview.text",
               [c.file("preview/text/body-000001.txt.zlib", zlib.compress(plain_b, 6), "application/zlib")],
               note="The plain text of the body, derived from its blocks (rich-document-plain-text-1).",
               epistemic="measured", input_files=["text/body-000001.json"],
               input_params={"method": "rich-document-plain-text-1"},
               edges=[{"to": "body-000001", "kind": "requires", "role": "extracted-from"}],
               meta=OrderedDict([("payload_format", "zlib-deflate")]))
        edges.append({"to": "text-000001", "kind": "enhances", "role": "plain-text"})
        plain_nodes = ["text-000001"]
    p = doc["props"]
    props = OrderedDict([("schema_version", 1),
                         ("core", OrderedDict((k, p.get(k, "")) for k in
                                              ("title", "subject", "creator", "keywords", "description",
                                               "lastModifiedBy", "created", "modified"))),
                         ("custom", [])])
    c.node("properties", "core.text.properties",
           [c.file("document/properties.json", compact(props), "application/json")],
           note="Title, author and dates from the original's docProps/core.xml.", **measured)
    edges.append({"to": "properties", "kind": "enhances", "role": "properties"})
    edges.append({"to": orig_node, "kind": "enhances", "role": "package-part"})
    structure = OrderedDict([("schema_version", 1), ("body", ["body-000001"]), ("bodyNextId", 2),
                             ("finalSection", {}), ("stories", []), ("noteSeparators", []), ("media", []),
                             ("plainText", plain_nodes), ("properties", "properties")])
    if pdf is not None:
        _attach_pdf_x(c, pdf, host, orig_path, orig_node)
    c.node("document", "core.text.document",
           [c.file("document/document.json", compact(structure), "application/json")],
           note="The structure of the document: one run of the body. Headers, footers, notes, "
                "comments, pictures and styles are not mapped by werk-office %s; they are in the "
                "original .docx this package carries." % VERSION,
           edges=edges, **measured)
    c.preview("document/document.json")
    c.set_primary("document", "document")
    notes.append("%d block(s), %d byte(s) of plain text" % (len(doc["blocks"]), len(plain_b)))
    return doc["props"].get("title") or ""


def _cells_band(uid, cells, first_row, band_rows):
    """One band's envelope (spec/layouts/core.sheet.cells.layout.txt), after the profile's
    own example writer, with error values (kind 4) added."""
    wm = load_example("spreadsheet", "write_minimal.py")
    NONE = wm.NONE
    rows, cols, kinds, numbers, refs, styles, formula_of = [], [], [], [], [], [], []
    texts, formulas = [], []
    for (row, col) in sorted(cells):
        value = cells[(row, col)]
        kind, number, ref, formula = 0, 0.0, 0, NONE
        if isinstance(value, tuple) and value[0] == "=":
            if value[1] not in formulas:
                formulas.append(value[1])
            formula = formulas.index(value[1])
        elif isinstance(value, tuple) and value[0] == "#":
            kind, ref = 4, ERROR_CODES.get(value[1], 3)
        elif isinstance(value, bool):
            kind, ref = 3, int(value)
        elif isinstance(value, (int, float)):
            kind, number = 1, float(value)
        elif isinstance(value, str):
            if value not in texts:
                texts.append(value)
            kind, ref = 2, texts.index(value)
        rows.append(row)
        cols.append(col)
        kinds.append(kind)
        numbers.append(number)
        refs.append(ref)
        styles.append(0)
        formula_of.append(formula)
    import struct
    n = len(rows)
    u32 = lambda values: struct.pack("<%dI" % len(values), *values)
    text_offsets, text_bytes = wm.string_table(texts)
    formula_offsets, formula_bytes = wm.string_table(formulas)
    sections = [
        ("row", "u32", [n], 4, u32(rows)), ("col", "u32", [n], 4, u32(cols)),
        ("kind", "u8", [n], 1, bytes(kinds)), ("number", "f64", [n], 8, struct.pack("<%dd" % n, *numbers)),
        ("ref", "u32", [n], 4, u32(refs)), ("style", "u32", [n], 4, u32(styles)),
        ("formula", "u32", [n], 4, u32(formula_of)),
        ("text-offsets", "u64", [len(texts) + 1], 8, text_offsets),
        ("text-bytes", "u8", [len(text_bytes)], 1, text_bytes),
        ("array-dims", "u32", [0, 4], 16, b""), ("elem-kind", "u8", [0], 1, b""),
        ("elem-number", "f64", [0], 8, b""), ("elem-ref", "u32", [0], 4, b""),
        ("formula-offsets", "u64", [len(formulas) + 1], 8, formula_offsets),
        ("formula-bytes", "u8", [len(formula_bytes)], 1, formula_bytes),
        ("formula-array", "u32", [len(formulas), 5], 20, bytes(20 * len(formulas))),
    ]
    header = {"sheet_uid": uid, "cell_count": n, "text_count": len(texts), "formula_count": len(formulas),
              "array_count": 0, "element_count": 0}
    return wm.envelope(b"WKX0", "core.sheet.cells", header, sections)


def export_xlsx(c, data, pdf, host, original_name, notes):
    orig_path, orig_node = _attach_original(c, ".xlsx", data, original_name, "x")
    book = read_xlsx(data)
    wm = load_example("spreadsheet", "write_minimal.py")
    c.use_format("zlib-deflate")
    measured = dict(epistemic="measured", input_files=[orig_path], input_params=dict(OOXML_METHOD))
    sheet_ids, wb_edges = [], []
    band_rows = 4096
    for i, sh in enumerate(book["sheets"]):
        uid = i + 1
        sid = "sheet-%d" % uid
        sheet_ids.append(sid)
        cells = sh["cells"]
        bands_by = OrderedDict()
        for key in sorted(cells):
            bands_by.setdefault(key[0] // band_rows, {})[key] = cells[key]
        band_files, band_recs = [], []
        for b, bc in bands_by.items():
            env = _cells_band(uid, bc, b * band_rows, band_rows)
            stored = zlib.compress(env, 6)
            path = "sheets/%s/cells/rows-%07d.wkx.zlib" % (sid, b * band_rows)
            band_files.append(c.file(path, stored, "application/zlib", "band"))
            band_recs.append(OrderedDict([("path", path), ("first_row", b * band_rows),
                                          ("row_count", band_rows), ("entry_count", len(bc)),
                                          ("stored_size", len(stored)), ("stored_sha256", sha(stored)),
                                          ("inflated_size", len(env)), ("inflated_sha256", sha(env))]))
        index = OrderedDict([("schema_version", 1), ("store", "cells"), ("sheet_uid", uid),
                             ("band_rows", band_rows), ("band_format", "zlib-deflate"),
                             ("inflated_layout", "spec/layouts/core.sheet.cells.layout.txt"),
                             ("entry_count", len(cells)), ("bands", band_recs)])
        cpath = "sheets/%s/cells.json" % sid
        c.node(sid + "-cells", "core.sheet.cells",
               [c.file(cpath, compact(index), "application/json", "payload")] + band_files,
               note="The stored cells of sheet '%s' (%d: constants, formula text, error values), "
                    "decoded from the original .xlsx." % (sh["name"], len(cells)),
               payload_file=cpath, meta=OrderedDict([("file_formats", {"band": "zlib-deflate"})]),
               **measured)
        sp = wm.sheet_payload(uid, sh["name"])
        c.node(sid, "core.sheet.sheet",
               [c.file("sheets/%s/sheet.json" % sid, compact(sp), "application/json")],
               note="Sheet '%s'. Column widths, formats, merges and drawings are not mapped by "
                    "werk-office %s (they are in the original .xlsx)." % (sh["name"], VERSION),
               edges=[{"to": sid + "-cells", "kind": "enhances", "role": "cells"}], **measured)
        wb_edges.append({"to": sid, "kind": "enhances", "role": "sheet"})
    c.node("styles", "core.sheet.styles",
           [c.file("workbook/styles.json", compact(wm.styles_payload()), "application/json")],
           note="One cell format, the default: werk-office %s does not map cell formats." % VERSION)
    c.node("names", "core.sheet.names",
           [c.file("workbook/names.json", compact({"schema_version": 1, "names": []}), "application/json")],
           note="No defined names are mapped by werk-office %s." % VERSION)
    wbp = wm.workbook_payload(sheet_ids)
    p = book["props"]
    wbp["props"] = OrderedDict([("title", p.get("title", "")), ("subject", p.get("subject", "")),
                                ("author", p.get("creator", "")), ("company", ""),
                                ("keywords", p.get("keywords", "")), ("description", p.get("description", ""))])
    if pdf is not None:
        _attach_pdf_x(c, pdf, host, orig_path, orig_node)
    c.node("workbook", "core.sheet.workbook",
           [c.file("workbook/workbook.json", compact(wbp), "application/json")],
           note="The workbook: %d sheet(s) in tab order, decoded from the original .xlsx." % len(sheet_ids),
           edges=wb_edges + [{"to": "styles", "kind": "enhances", "role": "styles"},
                             {"to": "names", "kind": "enhances", "role": "names"}], **measured)
    c.preview("workbook/workbook.json")
    c.set_primary("document", "workbook")
    notes.extend(book["notes"])
    notes.append("%d sheet(s), %d cell(s); no core.sheet.computed node (cached formula results "
                 "are in the original)" % (len(sheet_ids), sum(len(s["cells"]) for s in book["sheets"])))
    return p.get("title") or ""


def export_pptx(c, data, pdf, host, original_name, notes):
    deck = read_pptx(data)
    wm = load_example("presentation", "write_minimal.py")
    c.use_format("zip")
    measured = dict(epistemic="measured", input_files=["media/media-1/media.zip"],
                    input_params=dict(OOXML_METHOD))
    next_id = 1
    media = []

    def asset(mid, name, ctype, encoding, blob, ext, note, **kw):
        node_id = "media-%d" % mid
        desc = OrderedDict([("content_type", ctype), ("definition", "formats"), ("embedded", True),
                            ("encoding", encoding), ("id", mid), ("link", None), ("name", name),
                            ("schema_version", 1)])
        c.node(node_id, "core.media.asset",
               [c.file("media/%s/asset.json" % node_id, compact(desc), "application/json", "payload"),
                c.file("media/%s/media.%s" % (node_id, ext), blob, ctype, "media")],
               note=note, payload_file="media/%s/asset.json" % node_id,
               meta=OrderedDict([("file_formats", {"media": encoding})]), **kw)
        media.append(OrderedDict([("id", mid), ("node", node_id)]))
        return node_id

    asset(1, original_name, MIME[".pptx"], "zip", data, "zip",
          "The original .pptx file, byte for byte, as Microsoft PowerPoint saved it (an embedded "
          "file of the deck; no slide names it).")
    if pdf is not None:
        c.use_format("pdf")
        asset(2, os.path.splitext(original_name)[0] + ".pdf", "application/pdf", "pdf", pdf, "pdf",
              "A PDF of the deck exported by %s itself from the original file." % host,
              epistemic="measured", input_files=["media/media-1/media.zip"],
              input_params=OrderedDict([("method", "office-export-pdf"), ("host", host)]),
              edges=[{"to": "media-1", "kind": "requires", "role": "rendered-from"}])
    next_id = 10
    master_id, layout_id = next_id, next_id + 1
    next_id += 2
    mp = wm.master_payload()
    mp["master"]["id"] = master_id
    mp["master"]["name"] = "werk-office master"
    c.node("master-%d" % master_id, "core.slide.master",
           [c.file("deck/masters/master-%d.json" % master_id, compact(mp), "application/json")],
           note="A plain master: werk-office %s does not map the original's masters, themes or "
                "layouts (they are in the original .pptx)." % VERSION)
    lp = {"schema_version": 1, "master": "master-%d" % master_id,
          "layout": {"id": layout_id, "name": "Blank", "kind": "blank"}}
    c.node("layout-%d" % layout_id, "core.slide.layout",
           [c.file("deck/layouts/layout-%d.json" % layout_id, compact(lp), "application/json")],
           note="One blank layout under the plain master.",
           edges=[{"to": "master-%d" % master_id, "kind": "requires", "role": "master"}])
    slides, doc_edges = [], []
    shape_count = 0
    for s in deck["slides"]:
        sid = next_id
        next_id += 1
        shapes = []
        for sh in s["shapes"]:
            x, y, w, h = sh["box"]
            shape = OrderedDict([("id", sh["id"]), ("name", sh["name"]),
                                 ("xfrm", OrderedDict([("x", round(x, 3)), ("y", round(y, 3)),
                                                       ("w", round(w, 3)), ("h", round(h, 3))])),
                                 ("kind", {"type": "shape"}),
                                 ("geom", {"kind": "preset", "name": sh["preset"]}),
                                 ("fill", {"kind": "none"}), ("line", {"fill": {"kind": "none"}})])
            if sh["paragraphs"]:
                shape["text"] = {"paragraphs": sh["paragraphs"]}
            shapes.append(shape)
        shape_count += len(shapes)
        payload = {"schema_version": 1, "slide": {"id": sid, "layout": layout_id, "shapes": shapes}}
        nid = "slide-%d" % sid
        inherited = sum(1 for sh in s["shapes"] if sh["inherited_box"])
        c.node(nid, "core.slide.slide",
               [c.file("deck/slides/%s.json" % nid, compact(payload), "application/json")],
               note="Slide %d: %d text shape(s) decoded from the original .pptx%s." % (
                   len(slides) + 1, len(shapes),
                   "; %d placeholder box(es) inherited from a layout the original carries were given "
                   "a default box" % inherited if inherited else ""),
               edges=[{"to": "layout-%d" % layout_id, "kind": "enhances", "role": "layout"}], **measured)
        slides.append(OrderedDict([("id", sid), ("node", nid)]))
        doc_edges.append({"to": nid, "kind": "enhances", "role": "contains"})
    for nid in ("master-%d" % master_id, "layout-%d" % layout_id):
        doc_edges.append({"to": nid, "kind": "enhances", "role": "contains"})
    for m in media:
        doc_edges.append({"to": m["node"], "kind": "enhances", "role": "media"})
    p = deck["props"]
    docp = OrderedDict([("schema_version", 1),
                        ("slide_size", {"width": round(deck["size"][0], 3), "height": round(deck["size"][1], 3)}),
                        ("notes_size", {"width": 540, "height": 720}), ("first_slide_number", 1),
                        ("next_id", next_id), ("slides", slides),
                        ("masters", [{"id": master_id, "node": "master-%d" % master_id,
                                      "layouts": [{"id": layout_id, "node": "layout-%d" % layout_id}]}]),
                        ("media", media), ("props", {"title": p.get("title", "")})])
    c.node("document", "core.slide.document",
           [c.file("deck/document.json", compact(docp), "application/json")],
           note="The deck: %d slide(s) in show order, its size, and the two embedded files "
                "(the original .pptx and its PDF)." % len(slides),
           edges=doc_edges, **measured)
    c.preview("deck/document.json")
    c.set_primary("document", "document")
    notes.extend(deck["notes"])
    notes.append("%d slide(s), %d text shape(s)" % (len(slides), shape_count))
    return p.get("title") or ""


def export(src, out, pdf=True, name=None, created=None, uuid=None):
    ext = os.path.splitext(src)[1].lower()
    if ext not in KIND:
        raise OfficeError("unsupported input %s (want .docx, .xlsx or .pptx)" % ext)
    data = open(src, "rb").read()
    if data[:4] != b"PK\x03\x04":
        raise OfficeError("%s is not an OOXML package (no ZIP signature)" % src)
    pdf_bytes, host = None, None
    if pdf:
        tmp = os.path.splitext(os.path.abspath(out))[0] + ".rendition.pdf"
        host = office_pdf(ext, src, tmp)
        pdf_bytes = open(tmp, "rb").read()
        os.remove(tmp)
    base = os.path.basename(src)
    c = Capsule(KIND[ext], name or os.path.splitext(base)[0][:200] or "document",
                summary="A Microsoft Office %s document exported by werk-office %s." % (ext, VERSION),
                created=created or now_utc(), uuid=uuid)
    notes = []
    fn = {".docx": export_docx, ".xlsx": export_xlsx, ".pptx": export_pptx}[ext]
    fn(c, data, pdf_bytes, host, base, notes)
    c.finish_revisions("Exported from %s by werk-office %s." % (base, VERSION))
    msha = c.write(out)
    return {"out": out, "profile": c.profile, "manifest_sha256": msha, "nodes": len(c.nodes),
            "files": len(c.blobs), "host": host, "notes": notes}


# =============================================================================================
# import
# =============================================================================================

def _node(pkg, node_id):
    try:
        return pkg.node(node_id)
    except werk.WerkError:
        return None


def find_original(pkg):
    """(node_id, bytes) of the carried original Office file, or (None, None)."""
    for n in pkg.nodes:
        meta = n.meta or {}
        if n.status == "dead":
            continue
        if n.type == "core.package.binary" and meta.get("payload_format") == "opc" and "part_name" not in meta:
            return n.node_id, pkg.read_payload(n.node_id)
        if n.type == X_SOURCE:
            return n.node_id, pkg.read_payload(n.node_id)
    if pkg.profile != "presentation/1":
        return None, None
    doc_id = pkg.primary("document")[0]
    doc = _node(pkg, doc_id) if doc_id else None
    if doc is not None and doc.status != "dead":
        d = json.loads(pkg.read_payload(doc_id))
        for m in d.get("media", []):
            node = _node(pkg, m["node"])
            if node is None or node.status == "dead":
                continue
            desc = json.loads(pkg.read_payload(m["node"]))
            if desc.get("encoding") == "zip" and desc.get("content_type") == MIME[".pptx"]:
                ver = [v for v in node.versions if v["v"] == node.resolved][0]
                path = [f["path"] for f in ver["files"] if f.get("role") == "media"][0]
                return m["node"], pkg.read_file(path)
    return None, None


def _doc_blocks(pkg):
    d = json.loads(pkg.read_payload(pkg.primary("document")[0]))
    blocks = []
    for nid in d["body"]:
        node = _node(pkg, nid)
        if node is None or node.status == "dead":
            blocks.append({"kind": "para", "text": "[node %s could not be read]" % nid, "runs": []})
            continue
        header = json.loads(pkg.read_payload(nid))
        ver = [v for v in node.versions if v["v"] == node.resolved][0]
        path = [f["path"] for f in ver["files"] if f.get("role") == header["blocks"]["role"]][0]
        blocks.extend(json.loads(zlib.decompress(pkg.read_file(path)).decode("utf-8")))
    return blocks


def _utf16_offsets(text):
    """byte offset (UTF-8) -> character offset (UTF-16 code units, what Word counts)."""
    out, b, u = {0: 0}, 0, 0
    for ch in text:
        b += len(ch.encode("utf-8"))
        u += 2 if ord(ch) > 0xFFFF else 1
        out[b] = u
    return out


def rebuild_docx(pkg, out, o):
    blocks = _doc_blocks(pkg)
    doc = o.app.Documents.Add()
    rng = doc.Content
    first = True

    def para(block, target):
        text = block.get("text", "").replace("\n", "\x0b")
        start = target.End - 1 if not first else 0
        target.InsertAfter(text)
        target.InsertParagraphAfter()
        offs = _utf16_offsets(block.get("text", ""))
        pos = 0
        for run in block.get("runs", []):
            props = run.get("props") or {}
            a, b = offs.get(pos, 0), offs.get(pos + run["len"], 0)
            pos += run["len"]
            if props and b > a:
                r = doc.Range(start + a, start + b)
                if props.get("bold"):
                    r.Bold = True
                if props.get("italic"):
                    r.Italic = True
                if props.get("underline") and props["underline"] != "none":
                    r.Underline = 1
                if props.get("strike"):
                    r.Font.StrikeThrough = True
                if props.get("size"):
                    r.Font.Size = props["size"]

    for block in blocks:
        if block["kind"] == "para":
            para(block, doc.Content)
        else:
            rows = block["rows"]
            ncols = max(len(r["cells"]) for r in rows) if rows else 1
            end = doc.Content.End - 1
            t = doc.Tables.Add(doc.Range(end, end), len(rows), ncols)
            for i, row in enumerate(rows):
                for j, cell in enumerate(row["cells"]):
                    rd = load_example("rich-document", "read_document.py")
                    t.Cell(i + 1, j + 1).Range.Text = rd.plain_text(cell["blocks"]).rstrip("\n")
            doc.Content.InsertParagraphAfter()
        first = False
    doc.SaveAs2(os.path.abspath(out), 16)    # wdFormatDocumentDefault (.docx)
    doc.Close(0)
    return o.version


def rebuild_xlsx(pkg, out, o):
    rs = load_example("spreadsheet", "read_spreadsheet.py")
    wbp = json.loads(pkg.read_payload(pkg.primary("document")[0]))
    sheets = []
    for sid in wbp["sheets"]:
        sp = json.loads(pkg.read_payload(sid))
        idx_node = sp["cells"]
        index = json.loads(pkg.read_payload(idx_node))
        node = _node(pkg, idx_node)
        ver = [v for v in node.versions if v["v"] == node.resolved][0]
        by_sha = {f["sha256"]: f["path"] for f in ver["files"]}
        cells = {}
        for band in index["bands"]:
            env = zlib.decompress(pkg.read_file(by_sha[band["stored_sha256"]]))
            cells.update(rs.read_cells(env, sp["uid"]))
        sheets.append((sp["name"], cells))
    refused = []
    wb = o.app.Workbooks.Add()
    while wb.Worksheets.Count < len(sheets):
        wb.Worksheets.Add(None, wb.Worksheets(wb.Worksheets.Count))
    for i, (name, cells) in enumerate(sheets):
        ws = wb.Worksheets(i + 1)
        ws.Name = name[:31]
        for (r, c), cell in sorted(cells.items()):
            target = ws.Cells(r + 1, c + 1)
            if cell["formula"] is not None:
                try:
                    target.Formula = "=" + cell["formula"]
                except Exception:
                    # e.g. a structured reference to a table (Sales[Q1]): sheet tables are
                    # not rebuilt, so Excel refuses the formula; it is kept as text, counted
                    target.Value = "'=" + cell["formula"]
                    refused.append("%s!%s" % (name, rs.a1(r, c)))
            elif isinstance(cell["value"], dict) and "error" in cell["value"]:
                target.Formula = "=" + {"#N/A": "NA()"}.get(cell["value"]["error"], "1/0")
            elif cell["value"] is not None:
                target.Value = cell["value"]
    wb.SaveAs(os.path.abspath(out), 51)       # xlOpenXMLWorkbook
    wb.Close(False)
    if refused:
        return "%s; %d formula(s) refused by Excel and kept as text: %s" % (
            o.version, len(refused), ", ".join(refused[:8]) + (" ..." if len(refused) > 8 else ""))
    return o.version


def rebuild_pptx(pkg, out, o):
    d = json.loads(pkg.read_payload(pkg.primary("document")[0]))
    pres = o.app.Presentations.Add(False)
    pres.PageSetup.SlideWidth = d["slide_size"]["width"]
    pres.PageSetup.SlideHeight = d["slide_size"]["height"]
    for i, s in enumerate(d["slides"]):
        node = _node(pkg, s["node"])
        slide = pres.Slides.Add(i + 1, 12)                  # ppLayoutBlank
        if node is None or node.status == "dead":
            continue
        payload = json.loads(pkg.read_payload(s["node"]))
        for sh in payload["slide"].get("shapes", []):
            x = sh.get("xfrm") or {"x": 0, "y": 0, "w": 100, "h": 40}
            box = slide.Shapes.AddTextbox(1, x.get("x", 0), x.get("y", 0), max(x.get("w", 1), 1),
                                          max(x.get("h", 1), 1))
            paras = (sh.get("text") or {}).get("paragraphs", [])
            lines = ["".join(r.get("text", "") for r in p.get("runs", [])) for p in paras]
            box.TextFrame.TextRange.Text = "\r".join(lines)
    pres.SaveAs(os.path.abspath(out), 24)                   # ppSaveAsOpenXMLPresentation
    o.done(o.version)
    return o.version


def import_(src, out, rebuild=False):
    pkg = werk.open(src)
    verdict = pkg.verdict()
    ext = os.path.splitext(out)[1].lower()
    want = {"rich-document/1": ".docx", "spreadsheet/1": ".xlsx", "presentation/1": ".pptx"}.get(pkg.profile)
    if want is None:
        raise OfficeError("profile %s is not an Office profile" % pkg.profile)
    if ext != want:
        raise OfficeError("a %s package becomes a %s file, not %s" % (pkg.profile, want, ext))
    if not rebuild:
        nid, data = find_original(pkg)
        if data is not None:
            with open(out, "wb") as fh:
                fh.write(data)
            return {"out": out, "route": "original", "node": nid, "sha256": sha(data),
                    "verdict_exit": verdict["exit"]}
    fn = {".docx": rebuild_docx, ".xlsx": rebuild_xlsx, ".pptx": rebuild_pptx}[ext]
    progid = {".docx": "Word.Application", ".xlsx": "Excel.Application", ".pptx": "PowerPoint.Application"}[ext]
    if os.path.isfile(out):
        os.remove(out)
    host = isolated("rebuild", [os.path.abspath(src), os.path.abspath(out)], progid)
    return {"out": out, "route": "rebuilt", "host": host, "sha256": sha(open(out, "rb").read()),
            "verdict_exit": verdict["exit"]}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "_job":
        return _job_main(argv[1:])
    ap = argparse.ArgumentParser(prog="werk-office", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    e = sub.add_parser("export")
    e.add_argument("src")
    e.add_argument("out")
    e.add_argument("--no-pdf", action="store_true")
    e.add_argument("--name")
    e.add_argument("--created")
    e.add_argument("--uuid")
    i = sub.add_parser("import")
    i.add_argument("src")
    i.add_argument("out")
    i.add_argument("--rebuild", action="store_true")
    f = sub.add_parser("info")
    f.add_argument("src")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "export":
            r = export(a.src, a.out, pdf=not a.no_pdf, name=a.name, created=a.created, uuid=a.uuid)
        elif a.cmd == "import":
            r = import_(a.src, a.out, rebuild=a.rebuild)
        elif a.cmd == "info":
            pkg = werk.open(a.src)
            r = pkg.verdict()
        else:
            ap.print_help()
            return 2
    except (OfficeError, werk.WerkError) as exc:
        print("werk-office: %s" % exc, file=sys.stderr)
        return 1
    r["office_instances"] = [list(x) for x in Office.log]
    print(json.dumps(r, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
