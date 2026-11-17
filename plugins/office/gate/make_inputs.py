#!/usr/bin/env python3
"""make_inputs.py -- write the gate's three test documents with Office itself (private COM).

    py -3.12 gate/make_inputs.py <out-dir>

  test.docx  a heading, a paragraph with bold / italic / underlined / struck runs and a
             12-point and a 20-point run, non-ASCII text, a 3x2 table, a page break, a
             final paragraph
  test.xlsx  two sheets: text, integers, a decimal, a boolean, =SUM / =A2*2 formulas, a
             #DIV/0! error, a cell in row 5000 (a second band of 4096 rows)
  test.pptx  two slides: a title slide and a slide with a text box of three paragraphs

Writes `<out-dir>/inputs.json` with the sha256 of each file and the Office versions.
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from werk_office import Office  # noqa: E402


def word(path):
    with Office("Word.Application") as o:
        doc = o.app.Documents.Add()
        sel = doc.Content
        sel.Text = "werk-office gate document"
        doc.Paragraphs(1).Range.Font.Size = 20
        doc.Paragraphs(1).Range.Font.Bold = True
        doc.Content.InsertParagraphAfter()
        p = doc.Content
        p.InsertAfter("Plain text, bold, italic, underlined and struck runs. Grüße – ünïcødé 日本語.")
        doc.Content.InsertParagraphAfter()
        r2 = doc.Paragraphs(2).Range
        r2.Font.Bold = False
        r2.Font.Size = 12
        text = r2.Text
        for word_, attr in (("bold", "Bold"), ("italic", "Italic"), ("underlined", "Underline"),
                            ("struck", "StrikeThrough")):
            i = text.index(word_)
            rr = doc.Range(r2.Start + i, r2.Start + i + len(word_))
            if attr == "StrikeThrough":
                rr.Font.StrikeThrough = True
            else:
                setattr(rr, attr, 1 if attr == "Underline" else True)
        end = doc.Content.End - 1
        t = doc.Tables.Add(doc.Range(end, end), 3, 2)
        for i, row in enumerate((("Item", "Count"), ("Apples", "3"), ("Pears", "5"))):
            for j, v in enumerate(row):
                t.Cell(i + 1, j + 1).Range.Text = v
        doc.Content.InsertParagraphAfter()
        doc.Content.InsertAfter("After the table, before a page break.")
        doc.Content.InsertParagraphAfter()
        end = doc.Content.End - 1
        doc.Range(end, end).InsertBreak(7)  # wdPageBreak, at the end (a collapsed range)
        doc.Content.InsertAfter("The last paragraph, on page two.")
        doc.BuiltInDocumentProperties("Title").Value = "werk-office gate document"
        doc.BuiltInDocumentProperties("Author").Value = "werk-office gate"
        doc.SaveAs2(os.path.abspath(path), 16)
        doc.Close(0)
        return o.version


def excel(path):
    with Office("Excel.Application") as o:
        wb = o.app.Workbooks.Add()
        while wb.Worksheets.Count < 2:
            wb.Worksheets.Add(None, wb.Worksheets(wb.Worksheets.Count))
        a = wb.Worksheets(1)
        a.Name = "Prices"
        a.Range("A1:B1").Value = (("Item", "Price"),)
        a.Range("A2:B4").Value = (("Tea", 4.5), ("Coffee", 3), ("Water", 1))
        a.Range("A5").Value = "Total"
        a.Range("B5").Formula = "=SUM(B2:B4)"
        a.Range("C2").Formula = "=B2*2"
        a.Range("D1").Value = True
        a.Range("D2").Formula = "=1/0"
        a.Range("A5000").Value = "far down"
        b = wb.Worksheets(2)
        b.Name = "Notes"
        b.Range("A1").Value = "Grüße – 日本語"
        b.Range("B2").Value = 1234567.25
        wb.BuiltinDocumentProperties("Title").Value = "werk-office gate workbook"
        wb.SaveAs(os.path.abspath(path), 51)
        wb.Close(False)
        return o.version


def powerpoint(path):
    with Office("PowerPoint.Application") as o:
        pres = o.app.Presentations.Add(False)
        s1 = pres.Slides.Add(1, 1)                       # ppLayoutTitle
        s1.Shapes(1).TextFrame.TextRange.Text = "werk-office gate deck"
        s1.Shapes(2).TextFrame.TextRange.Text = "Slide one subtitle"
        s2 = pres.Slides.Add(2, 12)                      # ppLayoutBlank
        box = s2.Shapes.AddTextbox(1, 72, 72, 400, 200)
        box.TextFrame.TextRange.Text = "First point\rSecond point\rGrüße – 日本語"
        box.TextFrame.TextRange.Paragraphs(1).Font.Bold = True
        pres.BuiltInDocumentProperties("Title").Value = "werk-office gate deck"
        pres.SaveAs(os.path.abspath(path), 24)
        return o.version


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    rec = {}
    only = sys.argv[2:]
    old = os.path.join(out, "inputs.json")
    if only and os.path.isfile(old):
        rec = json.load(open(old, encoding="utf-8"))
    for name, fn in (("test.docx", word), ("test.xlsx", excel), ("test.pptx", powerpoint)):
        if only and name not in only:
            continue
        p = os.path.join(out, name)
        if os.path.isfile(p):
            os.remove(p)
        ver = fn(p)
        rec[name] = {"sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(),
                     "size": os.path.getsize(p), "office": ver}
        print(name, rec[name])
    rec["office_instances"] = [list(x) for x in Office.log]
    json.dump(rec, open(os.path.join(out, "inputs.json"), "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
