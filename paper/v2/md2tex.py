# -*- coding: utf-8 -*-
"""Convert paper/v2/PAPER.md into paper/v2/werk-paper-v2.tex.

Deliberately narrow: it handles exactly the markdown subset PAPER.md uses, so
that the prose master and the typeset paper cannot drift.  Run:

    python paper/v2/md2tex.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'PAPER.md')
DST = os.path.join(HERE, 'werk-paper-v2.tex')

PREAMBLE = r"""\documentclass[10pt,twocolumn,letterpaper]{article}

% ---------------------------------------------------------------------------
% Encoding & fonts
% ---------------------------------------------------------------------------
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{textcomp}

\IfFileExists{newtxtext.sty}{%
  \usepackage{newtxtext}%
  \usepackage{newtxmath}%
}{%
  \usepackage{mathptmx}%
}

% ---------------------------------------------------------------------------
% Layout
% ---------------------------------------------------------------------------
\usepackage[letterpaper,margin=0.7in,columnsep=0.28in]{geometry}
\usepackage{microtype}
\usepackage{booktabs}
\usepackage{array}
\usepackage{amsmath}
\usepackage{xcolor}
\usepackage{titlesec}
\usepackage{fancyhdr}
\usepackage{caption}
\usepackage{enumitem}

\definecolor{darkblue}{RGB}{0,0,139}

\usepackage[colorlinks=true,linkcolor=darkblue,citecolor=darkblue,%
            urlcolor=darkblue,breaklinks=true]{hyperref}
\usepackage{url}

% ---------------------------------------------------------------------------
% Compact section headings
% ---------------------------------------------------------------------------
\titleformat{\section}{\normalfont\large\bfseries}{\thesection}{0.6em}{}
\titleformat{\subsection}{\normalfont\normalsize\bfseries}{\thesubsection}{0.6em}{}
\titlespacing*{\section}{0pt}{2.0ex plus 0.6ex minus .2ex}{1.0ex plus .2ex}
\titlespacing*{\subsection}{0pt}{1.4ex plus 0.4ex minus .2ex}{0.7ex plus .2ex}

% ---------------------------------------------------------------------------
% Headers / footers
% ---------------------------------------------------------------------------
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0.4pt}
\fancyfoot[L]{\footnotesize Technical Report --- \texttt{werk}}
\fancyfoot[R]{\footnotesize \thepage}
\fancypagestyle{plain}{%
  \fancyhf{}%
  \renewcommand{\headrulewidth}{0pt}%
  \renewcommand{\footrulewidth}{0.4pt}%
  \fancyfoot[L]{\footnotesize Technical Report --- \texttt{werk}}%
  \fancyfoot[R]{\footnotesize \thepage}%
}

\captionsetup{font=small,labelfont=bf,skip=4pt}

% float placement: prefer many floats at the top, few float-only pages
\setcounter{topnumber}{3}
\setcounter{bottomnumber}{2}
\setcounter{totalnumber}{4}
\renewcommand{\topfraction}{0.92}
\renewcommand{\bottomfraction}{0.6}
\renewcommand{\textfraction}{0.06}
\renewcommand{\floatpagefraction}{0.75}
\renewcommand{\dbltopfraction}{0.92}
\renewcommand{\dblfloatpagefraction}{0.75}
\setlength{\textfloatsep}{8pt plus 2pt minus 2pt}
\setlength{\dblfloatsep}{8pt plus 2pt minus 2pt}
\setlength{\dbltextfloatsep}{8pt plus 2pt minus 2pt}
\setlength{\intextsep}{8pt plus 2pt minus 2pt}
\setlength{\parindent}{1em}
\frenchspacing
\raggedbottom

\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}
\newcommand{\code}[1]{\texttt{\small #1}}

% ---------------------------------------------------------------------------
% Title block
% ---------------------------------------------------------------------------
\title{%
  \vspace{-2.0em}
  {\bfseries\huge Agent-Implementability as a Format-Quality Metric}\\[0.35em]
  {\large A Measurement Protocol for Self-Contained File Formats, and \texttt{werk},
   a Container Doctrine Designed Against It}\\[0.5em]
  {\normalsize\itshape Technical Report --- version 0.2 (second edition)}%
}

\author{%
  Gregor Hubert Max Koch\\
  {\small\itshape Independent researcher}\\
  {\small\href{mailto:gregor.koch@gmail.com}{gregor.koch@gmail.com}}%
}

\date{8 August 2026}

\begin{document}
\maketitle
"""

BIBLIO_HEAD = r"""\begin{thebibliography}{99}\footnotesize
\setlength{\itemsep}{0pt}
"""

# --------------------------------------------------------------------------
# inline conversion
# --------------------------------------------------------------------------

SPECIALS = {
    '\\': r'\textbackslash{}',
    '&': r'\&',
    '%': r'\%',
    '$': r'\$',
    '#': r'\#',
    '_': r'\_',
    '{': r'\{',
    '}': r'\}',
    '~': r'\textasciitilde{}',
    '^': r'\textasciicircum{}',
}

UNICODE = [
    (u'\u2014', '---'),
    (u'\u2013', '--'),
    (u'\u00d7', r'$\times$'),
    (u'\u00b7', r'$\cdot$'),
    (u'\u00b0', r'\textdegree{}'),
    (u'\u2016', r'$\|$'),
    (u'\u27e8', r'$\langle$'),
    (u'\u27e9', r'$\rangle$'),
    (u'\u2248', r'$\approx$'),
    (u'\u2212', '$-$'),
    (u'\u00a7', r'\S'),
    (u'\u2019', "'"),
    (u'\u2018', "`"),
    (u'\u201c', '``'),
    (u'\u201d', "''"),
    (u'\u00e9', r"\'e"),
    (u'\u00fc', r'\"u'),
]

UNITS = r'(?:s|ms|m|B|KB|MB|GB|KiB|MiB|rad|v|t)\b'


def escape(text, in_code=False):
    out = []
    for ch in text:
        out.append(SPECIALS.get(ch, ch))
    text = ''.join(out)
    if not in_code:
        for a, b in UNICODE:
            text = text.replace(a, b)
    else:
        for a, b in UNICODE[:2]:
            text = text.replace(a, b)
    return text


def straight_quotes(text):
    """Turn ASCII double quotes into TeX open/close pairs."""
    out = []
    open_ = True
    for ch in text:
        if ch == '"':
            out.append('``' if open_ else "''")
            open_ = not open_
        else:
            out.append(ch)
    return ''.join(out)


def inline(text):
    # footnotes: [^fn: body ^] -> \footnote{...}; body is inline-converted
    fns = []

    def stash_fn(m):
        fns.append(m.group(1).strip())
        return '\x01%d\x01' % (len(fns) - 1)

    text = re.sub(r'\[\^fn:(.+?)\^\]', stash_fn, text, flags=re.S)

    codes = []

    def stash(m):
        codes.append(m.group(1))
        return '\x00%d\x00' % (len(codes) - 1)

    text = re.sub(r'`([^`]+)`', stash, text)
    text = straight_quotes(text)
    text = escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\\textbf{\1}', text, flags=re.S)
    text = re.sub(r'(?<![\w*])\*([^*]+?)\*(?![\w*])', r'\\emph{\1}', text, flags=re.S)
    # scientific notation
    text = re.sub(r'(?<![\w.])(\d(?:\.\d+)?)e-0*(\d+)\b',
                  r'$\1\\times10^{-\2}$', text)
    # thin spaces inside numbers and before units
    text = re.sub(r'(?<=\d) (?=\d)', r'\\,', text)
    text = re.sub(r'(?<=\d) (?=' + UNITS + ')', r'\\,', text)
    text = re.sub(r'(?<=\d) (?=\\%)', r'\\,', text)
    text = text.replace(' -- ', ' --- ')
    for i, c in enumerate(codes):
        text = text.replace('\x00%d\x00' % i, r'\code{%s}' % escape(c, in_code=True))
    for i, f in enumerate(fns):
        text = text.replace('\x01%d\x01' % i, r'\footnote{%s}' % inline(f))
    return text


# --------------------------------------------------------------------------
# block conversion
# --------------------------------------------------------------------------

def convert(md):
    lines = md.split('\n')
    # start at the abstract
    for i, ln in enumerate(lines):
        if ln.strip() == '## Abstract':
            lines = lines[i:]
            break
    out = []
    i = 0
    n = len(lines)
    pending_caption = None   # (kind, text)
    pending_cols = None
    pending_star = False
    in_abstract = False
    in_biblio = False

    def flush_para(buf):
        if not buf:
            return
        txt = inline(' '.join(buf).strip())
        if txt:
            out.append(txt)
            out.append('')

    para = []
    while i < n:
        ln = lines[i]
        st = ln.strip()

        # ---- directives -------------------------------------------------
        if st.startswith('<!--tex cols='):
            m = re.match(r'<!--tex cols=(.*?)(\s+star)?-->', st)
            pending_cols = m.group(1).strip()
            pending_star = bool(m.group(2))
            i += 1
            continue
        if st == '<!--tex-bibliography-->':
            in_biblio = True
            out.append(BIBLIO_HEAD)
            i += 1
            continue

        # ---- headings ---------------------------------------------------
        if st.startswith('## ') or st.startswith('### '):
            flush_para(para)
            para = []
            level = 2 if st.startswith('## ') else 3
            title = st.lstrip('#').strip()
            if title == 'Abstract':
                out.append(r'\begin{abstract}')
                out.append(r'\noindent')
                in_abstract = True
                i += 1
                continue
            if in_abstract:
                out.append(r'\end{abstract}')
                in_abstract = False
            if in_biblio:
                out.append(r'\end{thebibliography}')
                in_biblio = False
            title = re.sub(r'^\d+(\.\d+)*\.?\s*', '', title)
            cmd = 'section' if level == 2 else 'subsection'
            if title == 'References':
                # thebibliography emits its own heading
                i += 1
                continue
            if title.lower().startswith('availability'):
                out.append('\\%s*{%s}' % (cmd, inline(title)))
            else:
                out.append('\\%s{%s}' % (cmd, inline(title)))
            out.append('')
            i += 1
            continue

        # ---- horizontal rule -------------------------------------------
        if st == '---':
            flush_para(para)
            para = []
            i += 1
            continue

        # ---- fenced code -----------------------------------------------
        if st.startswith('```'):
            flush_para(para)
            para = []
            i += 1
            body = []
            while i < n and not lines[i].strip().startswith('```'):
                body.append(lines[i])
                i += 1
            i += 1
            if pending_caption and pending_caption[0] == 'figure':
                out.append(r'\begin{figure}[t]\centering\small')
                out.append(r'\begin{minipage}{\columnwidth}\footnotesize\begin{verbatim}')
                out.extend(body)
                out.append(r'\end{verbatim}\end{minipage}')
                out.append(r'\caption{%s}' % pending_caption[1])
                out.append(r'\end{figure}')
                out.append('')
                pending_caption = None
            else:
                out.append(r'\begin{quote}\footnotesize\begin{verbatim}')
                out.extend(body)
                out.append(r'\end{verbatim}\end{quote}')
                out.append('')
            continue

        # ---- block quote -----------------------------------------------
        if st.startswith('> '):
            flush_para(para)
            para = []
            body = []
            while i < n and lines[i].strip().startswith('>'):
                body.append(lines[i].strip().lstrip('>').strip())
                i += 1
            out.append(r'\begin{quote}\small\itshape')
            out.append(inline(' '.join(body)))
            out.append(r'\end{quote}')
            out.append('')
            continue

        # ---- table ------------------------------------------------------
        if st.startswith('|'):
            flush_para(para)
            para = []
            rows = []
            while i < n and lines[i].strip().startswith('|'):
                rows.append(lines[i].strip())
                i += 1

            def cells(r):
                parts = r.strip().strip('|').split('|')
                return [c.strip() for c in parts]

            header = cells(rows[0])
            body = [cells(r) for r in rows[2:]]
            ncol = len(header)
            cols = pending_cols or ('l' * ncol)
            star = pending_star
            env = 'table*' if star else 'table'
            out.append('\\begin{%s}[t]\\centering\\footnotesize' % env)
            if pending_caption and pending_caption[0] == 'table':
                out.append(r'\caption{%s}' % pending_caption[1])
            out.append(r'\begin{tabular}{%s}' % cols)
            out.append(r'\toprule')
            out.append(' & '.join(inline(c) for c in header) + r' \\')
            out.append(r'\midrule')
            for r in body:
                r = (r + [''] * ncol)[:ncol]
                out.append(' & '.join(inline(c) for c in r) + r' \\')
            out.append(r'\bottomrule')
            out.append(r'\end{tabular}')
            out.append('\\end{%s}' % env)
            out.append('')
            pending_caption = None
            pending_cols = None
            pending_star = False
            continue

        # ---- numbered / bulleted lists ----------------------------------
        if re.match(r'^\d+\.\s', st) or st.startswith('* '):
            flush_para(para)
            para = []
            ordered = bool(re.match(r'^\d+\.\s', st))
            items = []
            cur = None
            while i < n:
                s2 = lines[i].strip()
                if not s2:
                    # blank line ends the list unless the next line is indented
                    if i + 1 < n and (lines[i + 1].startswith('   ') or
                                      re.match(r'^\d+\.\s|^\* ', lines[i + 1].strip())):
                        i += 1
                        continue
                    break
                m = re.match(r'^(?:\d+\.|\*)\s+(.*)$', s2)
                if m:
                    if cur is not None:
                        items.append(cur)
                    cur = m.group(1)
                elif cur is not None:
                    cur += ' ' + s2
                else:
                    break
                i += 1
            if cur is not None:
                items.append(cur)
            if in_biblio:
                for it in items:
                    out.append("\\bibitem{r%d}" % (len(out),) + inline(it))
            else:
                env = 'enumerate' if ordered else 'itemize'
                out.append('\\begin{%s}[leftmargin=1.2em,itemsep=1pt,topsep=2pt]' % env)
                for it in items:
                    out.append(r'\item ' + inline(it))
                out.append('\\end{%s}' % env)
                out.append('')
            continue

        # ---- blank ------------------------------------------------------
        if not st:
            flush_para(para)
            para = []
            i += 1
            continue

        # ---- caption paragraph ------------------------------------------
        m = re.match(r'^\*\*(Table|Figure) \d+ (?:\u2014|-{1,3}) (.*)\*\*$', st)
        if m:
            flush_para(para)
            para = []
            pending_caption = (m.group(1).lower(), inline(m.group(2)))
            i += 1
            continue

        para.append(st)
        i += 1

    flush_para(para)
    if in_biblio:
        out.append(r'\end{thebibliography}')
    return '\n'.join(out)


def main():
    md = io.open(SRC, encoding='utf-8').read()
    body = convert(md)
    tex = PREAMBLE + '\n' + body + '\n\n\\end{document}\n'
    io.open(DST, 'w', encoding='utf-8').write(tex)
    sys.stdout.write('wrote %s (%d bytes)\n' % (DST, len(tex)))


if __name__ == '__main__':
    main()
