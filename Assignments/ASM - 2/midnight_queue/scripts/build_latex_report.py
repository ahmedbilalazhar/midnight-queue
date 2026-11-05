"""Generate an editable five-page LaTeX report from the same measured content.

The existing report builder is the single source for evidence and tables.
This exporter preserves its content and page grouping, uses vector figures,
and writes ordinary editable TeX with relative image paths.
"""
from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil

from reportlab.platypus import Image, PageBreak, Paragraph, Spacer, Table
import build_report as report

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "23I-2581-A2-DS-B.tex"
IMAGES = ROOT / "report" / "images"


def escape(text):
    replacements = {
        "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$",
        "&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_",
        "^": r"\textasciicircum{}", "~": r"\textasciitilde{}",
        "Θ": r"\(\Theta\)", "Σ": r"\(\Sigma\)", "α": r"\(\alpha\)",
        "≈": r"\(\approx\)", "≤": r"\(\leq\)", "≥": r"\(\geq\)",
        "→": r"\(\rightarrow\)", "×": r"\(\times\)", "²": r"\(^{2}\)",
        "−": "-", "–": "--", "—": "---", "·": r"\,\textbullet\,",
        "…": r"\ldots{}", "\u00a0": " ",
    }
    return "".join(replacements.get(c,c) for c in str(text))


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.stack = []

    def handle_starttag(self,tag,attrs):
        command = {"b":r"\textbf{", "i":r"\textit{", "font":r"\texttt{"}.get(tag)
        if command:
            self.parts.append(command)
            self.stack.append(tag)
        elif tag == "br":
            self.parts.append(r"\newline " + "\n")

    def handle_endtag(self,tag):
        if self.stack and self.stack[-1] == tag:
            self.parts.append("}")
            self.stack.pop()

    def handle_data(self,data):
        value = escape(data)
        if self.stack and self.stack[-1] == "font":
            value = value.replace(r"\_",r"\_\allowbreak{}")
        self.parts.append(value)


def text(value):
    parser = Text()
    parser.feed(str(value))
    return "".join(parser.parts)


def leaf_table(item, font=6.2):
    data = item._cellvalues
    widths = item._colWidths
    total = sum(widths)
    specs = []
    count = len(widths)
    time_pair = count == 7 and str(data[0][0]) == "Contender"
    for width in widths:
        weight = width / total * count
        specs.append(r">{\hsize=" + f"{weight:.4f}" + r"\hsize\linewidth=\hsize\raggedright\arraybackslash}X")
    lines = [r"{\fontsize{" + str(font) + "}{" + str(font*1.18) + r"}\selectfont",
             r"\setlength{\tabcolsep}{2pt}\renewcommand{\arraystretch}{1.06}",
             r"\begin{tabularx}{\linewidth}{@{}" + "".join(specs) + "@{}}",
             r"\toprule\rowcolor{pale}"]
    for i,row in enumerate(data):
        converted = []
        for cell in row:
            value = text(cell.text) if isinstance(cell,Paragraph) else text(cell)
            if i and re.fullmatch(r"[\d.]+[kMB]?/[\d.]+[kMB]?", str(cell)):
                left,right = str(cell).split("/")
                value = r"\shortstack[l]{" + left + r"\,/\\ " + right + "}"
            elif i and time_pair:
                # Keep the corresponding time/count rows horizontally aligned.
                value = r"\shortstack[l]{" + value + r"\\ \strut}"
            if i and count == 5 and len(str(cell)) > 45:
                value = value.replace(", ", r",\allowbreak ")
            converted.append(r"\textbf{" + value + "}" if i == 0 else value)
        lines.append(" & ".join(converted) + r" \\")
        if i == 0:
            lines.append(r"\midrule")
        elif i % 2 == 0 and i < len(data)-1:
            lines.append(r"\rowcolor{wash}")
    lines += [r"\bottomrule", r"\end{tabularx}}"]
    return "\n".join(lines)


def image(item,width=r"\linewidth"):
    source = Path(item.filename)
    preferred = source.with_suffix(".pdf")
    name = preferred.name if preferred.exists() else source.name
    # The editable TeX is at project root; paths remain portable.
    return r"\includegraphics[width=" + width + "]{report/images/" + name + "}"


def render_table(item,page):
    data = item._cellvalues
    nested = any(isinstance(cell,(Table,Image)) for row in data for cell in row)
    if not nested:
        return leaf_table(item, 6.5 if page != 4 else 6.2) + r"\par\vspace{2pt}"
    # Use the full report width for the two-panel data profile; its numerical
    # table remains editable text below, rather than a screenshot.
    if page == 1 and any(isinstance(c,Image) for r in data for c in r):
        contents = []
        for row in data:
            for cell in row:
                if isinstance(cell,Image):
                    contents.insert(0,image(cell,r".96\linewidth") + r"\par")
                elif isinstance(cell,Table):
                    contents.append(leaf_table(cell,7.2))
        return "\n".join(contents) + r"\par\vspace{3pt}"
    row = data[0]
    real = [cell for cell in row if isinstance(cell,(Table,Image))]
    fractions = [.485]*len(real)
    if len(real) == 1:
        fractions = [1.0]
    chunks = []
    for cell,fraction in zip(real,fractions):
        content = (leaf_table(cell,6.4 if page != 5 else 8.0)
                   if isinstance(cell,Table) else image(cell))
        chunks.append(r"\begin{minipage}[t]{" + f"{fraction:.3f}" + r"\linewidth}\vspace{0pt}"
                      + "\n" + content + "\n" + r"\end{minipage}")
    return "\n\\hfill\n".join(chunks) + r"\par\vspace{3pt}"


MATH = {
    "M1": r"""\textbf{M1 --- Insertion Sort.} If \(I\) is the inversion count, every
    shift removes one inversion: moves \(=I+n-1\), comparisons
    \(=I+n-1-z\), with \(0\leq z\leq n-1\). Thus \(T(n,I)=\Theta(n+I)\).
    Best: \(I=0\), \(\Theta(n)\); random distinct keys:
    \(\mathbb E[I]=n(n-1)/4\), \(\Theta(n^2)\); reverse:
    \(I=n(n-1)/2\), \(\Theta(n^2)\). C5 inversion counts at the four sizes:
    \(3{,}007;\ 325{,}988;\ 34{,}333{,}390;\ 272{,}954{,}546\).
    Moving only 1\% of records does not guarantee linear work.""",
    "M2": r"""\textbf{M2 --- Merge Sort.} Iterating
    \(T(n)=2T(n/2)+cn\) gives
    \(T(n)=2^jT(n/2^j)+jcn\).
    At \(j=\log_2n\), this is \(nT(1)+cn\log_2n=\Theta(n\log n)\).
    Master's theorem: \(a=b=2\), \(f(n)=\Theta(n^{\log_ba})=\Theta(n)\);
    case 2 confirms \(\Theta(n\log n)\).""",
    "M3": r"""\textbf{M3 --- Quick Sort.} (a) Iteration of
    \(T(n)=T(n-1)+cn\) yields
    \(T(1)+c\sum_{j=2}^{n}j=\Theta(n^2)\).
    (b) The balanced recursion tree has \(\log_2n\) levels of
    \(\Theta(n)\) work, hence \(\Theta(n\log n)\).
    (c) For \(T(n)=T(n/10)+T(9n/10)+n\), each complete level conserves
    total size \(n\). The first \(\lfloor\log_{10}n\rfloor\) levels give
    \(\Omega(n\log n)\); depth is at most
    \(\lceil\log_{10/9}n\rceil\), giving \(O(n\log n)\).
    Together these prove the tight bound \(\Theta(n\log n)\).""",
    "M4": r"""\textbf{M4 --- Heap Sort.} A height-\(h\) node costs \(O(h)\)
    to sift, and there are at most \(\lceil n/2^{h+1}\rceil\) such nodes.
    Bottom-up build costs
    \(O(n\sum_{h\geq0}h/2^{h+1})=O(n)\); visiting the internal nodes gives
    \(\Omega(n)\), so build is \(\Theta(n)\).
    Each of \(n-1\) extractions costs \(O(\log n)\);
    total worst-case time is \(\Theta(n\log n)\), with \(O(1)\) auxiliary space.""",
    "M7": r"""\textbf{M7 --- Live feed.} For \(w\) equal-size windows and \(K\geq2\),
    the worst-case costs are
    \(T_A=\sum_{j=1}^{w}\Theta((jn/w)\log(jn/w))=\Theta(nw\log n)\);
    \(T_B=O(n\log K+wK\log K)\), including every ordered heap publication;
    and \(T_C=O(n\log(n/w)+wK)\). Comparing the selection/sorting terms gives
    the rough threshold \(w\approx n/K\): many small windows favour merge,
    fewer large windows favour the heap. This threshold ignores constants and
    publication terms, so it is a guide rather than a measured crossover.
    At \(n=284{,}807\), \(K=52\), it suggests about \(5{,}477\) windows;
    the tested 48 and 288 windows both favour the heap in the recorded data.""",
    "M8": r"""\textbf{M8 --- Space.} Insertion and Heap Sort: \(O(1)\);
    Merge Sort: \(O(n)\); both Quick Sort variants: \(O(\log n)\) explicit
    stack because the smaller side is processed first; size-\(K\) heap and
    bounded buffer: \(O(K)\). Live re-rank: \(O(n)\);
    live heap: \(O(K)\); live window merge: \(O(n/w+K)\), for equal-size windows.
    These are algorithmic auxiliary-space bounds; retained measurement logs are separate.""",
}


PREAMBLE = r"""% !TeX program = xelatex
% Editable source generated from measured project artifacts.
% Compile from this directory: tectonic 23I-2581-A2-DS-B.tex
% Or select XeLaTeX in Overleaf. Upload this file and report/images/.
\documentclass[10pt,a4paper]{article}
\usepackage[margin=12mm,top=12mm,bottom=13mm]{geometry}
\usepackage{fontspec}
\IfFontExistsTF{Arial}{\setmainfont{Arial}\setsansfont{Arial}}
  {\setmainfont{TeX Gyre Heros}\setsansfont{TeX Gyre Heros}}
\IfFontExistsTF{Consolas}{\setmonofont[Scale=.88]{Consolas}}
  {\setmonofont[Scale=.88]{Latin Modern Mono}}
\usepackage{amsmath,amssymb}
\usepackage[table]{xcolor}
\usepackage{graphicx,tabularx,booktabs,array,fancyhdr}
\usepackage{microtype}
\usepackage[hidelinks]{hyperref}
\definecolor{ink}{HTML}{18364B}
\definecolor{teal}{HTML}{008C95}
\definecolor{muted}{HTML}{5B7080}
\definecolor{pale}{HTML}{E5EFF4}
\definecolor{wash}{HTML}{F5F8FA}
\color{ink}
\setlength{\parindent}{0pt}
\setlength{\parskip}{2.5pt}
\setlength{\emergencystretch}{2em}
\setlength{\abovedisplayskip}{3pt}
\setlength{\belowdisplayskip}{3pt}
\pagestyle{fancy}\fancyhf{}
\fancyfoot[L]{\fontsize{7}{8}\selectfont\color{muted}23I-2581 · DS-B\quad / \quad THE MIDNIGHT QUEUE}
\fancyfoot[R]{\fontsize{7}{8}\selectfont\color{muted}\thepage\ / 5}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{.3pt}
\newcommand{\sectiontitle}[1]{\par\vspace{4pt}{\color{teal}\fontsize{12}{14}\selectfont\bfseries #1}\par\vspace{1pt}}
\newcommand{\subheading}[1]{\par\vspace{3pt}{\fontsize{9}{11}\selectfont\bfseries #1}\par}
\newcommand{\figcaption}[1]{\par{\fontsize{6.2}{7.1}\selectfont\color{muted}#1}\par\vspace{1pt}}
\hypersetup{pdftitle={The Midnight Queue},pdfauthor={23I-2581},
pdfsubject={Design and Analysis of Algorithms - Assignment 2}}
\begin{document}
\fontsize{8.6}{10.7}\selectfont
"""


def main():
    IMAGES.mkdir(parents=True,exist_ok=True)
    for path in sorted((ROOT / "outputs/figures").glob("*")):
        if path.suffix in {".pdf",".png"} and path.stem != "legend_zoom":
            shutil.copy2(path, IMAGES / path.name)
    story = report.main(story_only=True)
    page = 1
    chunks = [PREAMBLE]
    for item in story:
        if isinstance(item,PageBreak):
            page += 1
            size = {2:(7.7,9.4),3:(7.5,9.1),4:(8.1,9.8),5:(8.8,10.6)}[page]
            chunks.append(r"\newpage" + "\n" + r"\fontsize{" + str(size[0]) + "}{" + str(size[1]) + r"}\selectfont")
        elif isinstance(item,Spacer):
            chunks.append(r"\vspace{2pt}")
        elif isinstance(item,Image):
            # Report-specific composites have all required panels and shared legends.
            chunks.append(image(item,r".98\linewidth") + r"\par")
        elif isinstance(item,Table):
            chunks.append(render_table(item,page))
        elif isinstance(item,Paragraph):
            source = item.text
            value = text(source)
            style = item.style.name
            if style == "title":
                chunks.append(r"{\fontsize{24}{26}\selectfont\bfseries The Midnight Queue}\par"
                              "\n" + r"{\fontsize{11}{14}\selectfont\color{muted}Ranking suspicious transactions at scale}\par"
                              "\n" + r"\vspace{4pt}{\color{teal}\hrule height 1.2pt}\vspace{4pt}")
            elif style == "h1":
                chunks.append(r"\sectiontitle{" + value + "}")
            elif style == "h2":
                chunks.append(r"\subheading{" + value + "}")
            elif style == "caption":
                if "log–log" in source and "Missing points" in source:
                    value += r" The shared legend below the figure applies to all six panels."
                if "Fig. E1." in source:
                    value += r" The vertical axes use logarithmic seconds so all completed strategies remain visible."
                chunks.append(r"\figcaption{" + value + "}")
            elif style == "subtitle":
                chunks.append(r"{\fontsize{7.2}{9}\selectfont\color{muted}" + value + r"}\par")
            else:
                key = re.match(r"<b>(M[1-478])\b",source)
                if key:
                    chunks.append(MATH[key.group(1)] + r"\par")
                elif source.startswith("<b>M5"):
                    current=report.load()
                    heap_10=report.topk_time(current["topk"],"Size-K Heap",100000,10000)
                    full_10=report.topk_time(current["topk"],"Full Sort (Hardened Quick Sort)",100000,10000)
                    heap_full=report.topk_time(current["topk"],"Size-K Heap",284807,28480)
                    full_full=report.topk_time(current["topk"],"Full Sort (Hardened Quick Sort)",284807,28480)
                    chunks.append(r"""\textbf{M5 --- Top-K.}
                    For \(2\leq K\leq n\), full sort and prefix costs \(\Theta(n\log n)\).
                    For the heap, bottom-up build is \(O(K)\), scanning is
                    \(O(n+A\log K)\) for \(A\) accepted replacements, and
                    ordered publication is \(O(K\log K)\); worst case
                    \(O(n\log K+K\log K)\).
                    The buffer costs \(O(K\log K+n+A(K+\log K))\):
                    rejected records need one comparison, accepted records need
                    binary search and explicit shifting. Worst case \(O(nK)\);
                    for a random permutation of distinct keys, record \(i>K\)
                    enters with probability \(K/i\), so \(\mathbb E[A]=K(H_n-H_K)\),
                    where \(H_j\) is the \(j\)-th harmonic number.
                    An idealised comparison equates
                    \((n+K)\log_2K=n\log_2n\); actual crossover depends on
                    constants, arrival order and acceptance rate, and is not
                    established beyond the measured grid. """ + escape(
                    f"The prediction that full sort overtakes near K=10,000 at n=100,000 "
                    f"{'was wrong' if heap_10<full_10 else 'is supported at this point'} on C2: "
                    f"heap {report.fmt_s(heap_10)}, full sort {report.fmt_s(full_10)}. "
                    f"At full size and K=n/10=28,480: heap {report.fmt_s(heap_full)}, "
                    f"full sort {report.fmt_s(full_full)}. These are measured points, not a universal crossover.")+r"\par")
                elif source.startswith("<b>M6"):
                    current=report.load()
                    a=current["ana"]["c6_band_analysis"]
                    chunks.append(r"""\textbf{M6 --- Naive Quick Sort on C6.}
                    A one-band subarray of size \(m\) loses one pivot each time,
                    so it costs \(\sum_{j=1}^{m-1}j=\binom m2\) comparisons.
                    Hence \(C(S)=\sum_i\binom{m_i}{2}+X(S)\), where \(X\)
                    counts cross-band comparisons and depends on the actual band sequence.
                    The exact model applies the descending-band Lomuto swaps and recurrence
                    \(C(S)=|S|-1+C(L_p(S))+C(R_p(S))\), with \(C(S)=0\) for \(|S|<2\).
                    Counts alone do not determine \(X\). """+escape(
                    f"At n=1,000 and 10,000, exact model = measured = "
                    f"{a['1000']['predicted_comparisons_exact_sequence']:,} and "
                    f"{a['10000']['predicted_comparisons_exact_sequence']:,}. "
                    f"The former ascending-partition model was incorrect. The within-band terms at "
                    f"100k and full size are {report.fmt_count(a['100000']['predicted_comparisons_group_formula'])} "
                    f"and {report.fmt_count(a['284807']['predicted_comparisons_group_formula'])}; "
                    "both measured cells are DNFs. Three-way partitioning processes equal bands together.")+r"\par")
                elif source.startswith("I used OpenCode"):
                    chunks.append(escape(
                        "The original project records OpenCode with DeepSeek V4.1 Flash assistance "
                        "for implementation, tests, experiment orchestration, analysis and drafting. "
                        "OpenAI Codex helped revise visualisations, notebook presentation, compliance checks "
                        "and this editable LaTeX report; then hardened quicksort, corrected the "
                        "C6 model and timing scopes, expanded tests and reran affected experiments. "
                        "Historical measurements remain archived, including excluded over-limit C5 insertion runs. "
                        "The student must verify the submission and be able to explain and modify it in the viva.") + r"\par")
                else:
                    value = value.replace("this is thermal/scheduling noise, not an algorithmic reversal",
                        "this is consistent with scheduling or thermal variation, whose cause was not independently measured")
                    value = value.replace("legend in panel (a)", "shared legend below the figure")
                    value = value.replace("Band groups m\\_i", "Band groups")
                    chunks.append(value + r"\par")
    chunks.append(r"\end{document}")
    OUT.write_text("\n\n".join(chunks),encoding="utf-8")
    print(f"Wrote editable LaTeX: {OUT}")
    print(f"Portable image folder: {IMAGES}")


if __name__ == "__main__":
    main()
