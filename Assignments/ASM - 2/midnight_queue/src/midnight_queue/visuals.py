"""One visual system for the notebook, print report and editable exports.

Only recorded measurements are plotted. NaNs are retained so a missing or
timed-out observation breaks a line instead of suggesting an interpolation.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import NullLocator, PercentFormatter
import numpy as np
import pandas as pd

from .config import CONFIG, PROJECT_ROOT

FIGURES = PROJECT_ROOT / "outputs" / "figures"
RAW = PROJECT_ROOT / "outputs" / "raw"
ANALYSIS = PROJECT_ROOT / "outputs" / "analysis"
ALGORITHMS = ("Insertion Sort", "Merge Sort", "Naive Quick Sort",
              "Hardened Quick Sort", "Heap Sort")
METHODS = ("Full Sort (Hardened Quick Sort)", "Size-K Heap", "Bounded Insertion Buffer")
COLORS = dict(zip(ALGORITHMS, ("#D14E64", "#008C95", "#CF8A24", "#174C78", "#7A62A3")))
COLORS.update(dict(zip(METHODS, ("#174C78", "#008C95", "#D14E64"))))
COLORS.update(rerank="#D14E64", heap="#008C95", merge="#CF8A24")
MARKERS = dict(zip(ALGORITHMS, ("o", "s", "^", "D", "v")))
MARKERS.update(dict(zip(METHODS, ("D", "o", "s"))))
INK, MUTED, GRID = "#18364B", "#5B7080", "#E3EAF0"
CAPTIONS: dict[str, str] = {}


def theme() -> None:
    """Set a quiet, colour-consistent, print-safe Matplotlib theme."""
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10,
        "text.color": INK, "axes.labelcolor": MUTED, "axes.edgecolor": "#BCCBD5",
        "axes.titlecolor": INK, "axes.titlesize": 12, "axes.titleweight": "bold",
        "axes.titlepad": 14, "axes.labelsize": 9, "axes.labelpad": 8,
        "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelsize": 9,
        "ytick.labelsize": 9, "axes.spines.top": False, "axes.spines.right": False,
        "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": .7,
        "legend.frameon": False, "legend.fontsize": 9, "legend.labelcolor": INK,
        "lines.linewidth": 2.2, "lines.markersize": 6,
        "figure.facecolor": "white", "axes.facecolor": "white",
        "savefig.facecolor": "white", "pdf.fonttype": 42, "ps.fonttype": 42,
    })


def finish(ax, *, logx=False, logy=False):
    if logx:
        ax.set_xscale("log")
        ax.xaxis.set_minor_locator(NullLocator())
    if logy:
        ax.set_yscale("log")
        ax.yaxis.set_minor_locator(NullLocator())
    ax.grid(axis="y", which="major")
    ax.tick_params(length=0, pad=7)
    ax.margins(x=.06, y=.12)


def legend(fig, names, *, y=.01, columns=3):
    handles = [Line2D([], [], color=COLORS[n], marker=MARKERS.get(n, ""),
                      label=n, linewidth=2, markersize=5) for n in names]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.5, y),
               ncol=columns, columnspacing=1.6, handlelength=2.2)


def save(fig, name: str, caption: str):
    FIGURES.mkdir(parents=True, exist_ok=True)
    for extension in ("png", "pdf", "svg"):
        fig.savefig(FIGURES / Path(name).with_suffix(f".{extension}"),
                    dpi=240, bbox_inches="tight", pad_inches=.16)
    CAPTIONS[name] = caption
    plt.close(fig)


def load_medians(file="tournament.csv"):
    frame = pd.read_csv(RAW / file)
    frame = frame.loc[frame.record_type.eq("median")].copy()
    for column in ("n", "k", "median_s", "comparisons", "moves"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def profile_chart():
    profile = json.loads((PROJECT_ROOT / "outputs/profile.json").read_text())
    bands = np.arange(10)
    totals = np.array([profile["band_counts"][str(b)] for b in bands])
    frauds = np.array([profile["fraud_by_band"][str(b)] for b in bands])
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), gridspec_kw={"width_ratios": [1.5, 1]})
    ax = axes[0]
    # Grouped bars show the two counts without implying additive populations.
    ax.bar(bands-.17, np.where(totals > 0, totals, np.nan), .34,
           color="#94B7CC", label="All transactions", zorder=3)
    ax.bar(bands+.17, np.where(frauds > 0, frauds, np.nan), .34,
           color=COLORS["Insertion Sort"], label="Fraud-labelled", zorder=3)
    ax.set(xticks=bands, xlabel="Risk band", ylabel="Transactions (count; log scale)",
           title="Volume concentrates in bands 3–4")
    finish(ax, logy=True)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_xlim(-.6,9.6)
    fig.text(.075, .015, "Bands 0–1: no records  ·  Band 2: no fraud labels",
             fontsize=8, color=MUTED)
    rate = np.divide(frauds, totals, out=np.zeros(10, dtype=float), where=totals > 0)
    ax = axes[1]
    ax.barh(bands[2:], rate[2:], color="#008C95",
            height=.62, label="Fraud labels / all records")
    ax.set(yticks=bands[2:], ylabel="Risk band", xlabel="Fraud-labelled share (%)",
           title="High bands have greater fraud density")
    ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_xlim(0, max(rate)*1.3)
    for b in bands[2:]:
        ax.text(rate[b]+.003, b, f"{rate[b]:.2%}", va="center", fontsize=8)
    finish(ax)
    ax.legend(loc="lower right", fontsize=7)
    fig.tight_layout(w_pad=3, rect=(0,.07,1,1))
    save(fig, "07_band_distribution.png", "Risk-band counts and fraud density on the full file. "
         "Fraud-labelled records are a subset of all records; empty bands are explicitly noted. "
         "Class is used only for evaluation after scoring.")


def fraud_chart():
    curve = pd.read_csv(ANALYSIS / "fraud_curve.csv")
    half = curve.loc[curve.fraction.ge(.5)].iloc[0]
    k_half = int(half.k)
    fig, ax = plt.subplots(figsize=(9.5, 4.5))
    ax.fill_between(curve.k, curve.fraction, color="#E6F1F4", step="post")
    ax.step(curve.k, curve.fraction, where="post", color=COLORS["Hardened Quick Sort"],
            label="Full-file triage queue")
    ax.axhline(.5, color=MUTED, lw=1, ls=(0, (4, 4)), label="50% capture target")
    ax.plot(k_half, half.fraction, "o", ms=8, color=COLORS["Insertion Sort"], zorder=5)
    ax.annotate(f"HALF OF ALL FRAUDS\nK = {k_half:,}", (k_half, half.fraction),
                xytext=(.60, .20), textcoords="axes fraction", fontsize=9,
                color=INK, fontweight="bold", arrowprops={"arrowstyle":"-", "color":MUTED},
                bbox={"boxstyle":"round,pad=.6", "fc":"white", "ec":GRID})
    ax.axvline(CONFIG.k, color="#008C95", ls=":", lw=1.3, label=f"Shift capacity K={CONFIG.k}")
    ax.set(xlabel="Queue capacity K (transactions; log scale)",
           ylabel="All fraud labels captured (%)", ylim=(-.01, 1.04),
           title="A fast queue is only useful if it surfaces the right cases")
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    finish(ax, logx=True)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    save(fig, "08_fraud_capture.png", f"Full-file fraud capture versus queue capacity. "
         f"The minimum K reaching 50% capture is {k_half:,}; K={CONFIG.k} captures no frauds. "
         "The curve is a step function; Class is never a ranking key.")


def growth(ax, med, metric="median_s", normalise=None):
    for name in ALGORITHMS:
        d = med.loc[med.condition.eq("C2") & med.algorithm.eq(name)].set_index("n")
        d = d.reindex(CONFIG.sizes)
        values = d[metric].copy()
        n = np.array(CONFIG.sizes, dtype=float)
        if normalise == "nlogn":
            values = values / (n*np.log2(n))
        elif normalise == "n2":
            values = values / n**2
        ax.plot(n, values, marker=MARKERS[name], color=COLORS[name], label=name,
                markeredgecolor="white", markeredgewidth=.7)
    finish(ax, logx=True, logy=True)
    ax.set_xlabel("Input size n (transactions; log scale)")


def conditions(ax, med):
    conditions = [f"C{i}" for i in range(1, 7)]
    x = np.arange(6)
    for i, name in enumerate(ALGORITHMS):
        d = med.loc[med.n.eq(10000) & med.algorithm.eq(name)].set_index("condition")
        values = d.reindex(conditions).median_s
        ax.bar(x+(i-2)*.15, values, width=.135, color=COLORS[name],
               label=name, zorder=3, edgecolor="white", linewidth=.35)
    ax.set_xticks(x, ["C1\nArrival", "C2\nShuffle", "C3\nRanked", "C4\nReverse", "C5\n1% moved", "C6\nBand only"])
    ax.set(xlabel="Input condition", ylabel="Median time (s; log scale)")
    finish(ax, logy=True)


def tournament_charts():
    med = load_medians()
    specs = [
        ("01_time_vs_n_C2.png", "median_s", None, "Median time (s; log scale)", "Sorting cost grows very differently on shuffled input"),
        ("03_comparisons_vs_n_C2.png", "comparisons", None, "Key comparisons (count; log scale)", "Comparison counts reveal the work behind the clock"),
        ("04_moves_vs_n_C2.png", "moves", None, "Element moves (count; log scale)", "Record movement separates the sorting strategies"),
        ("05_time_nlogn_vs_n_C2.png", "median_s", "nlogn", "Time / (n log₂ n) (s; log scale)", "Normalising by n log n tests the expected growth"),
        ("06_time_n2_vs_n_C2.png", "median_s", "n2", "Time / n² (s / transaction²; log scale)", "Quadratic normalisation exposes insertion sort"),
    ]
    for name, metric, norm, ylabel, title in specs:
        fig, ax = plt.subplots(figsize=(9.5, 4.8))
        growth(ax, med, metric, norm)
        ax.set(ylabel=ylabel, title=title)
        if metric == "median_s" and norm is None:
            ax.annotate("Insertion Sort: DNF at n ≥ 100,000", xy=(10000, 21.04),
                        xytext=(.52, .85), textcoords="axes fraction", fontsize=8,
                        color=COLORS["Insertion Sort"],
                        arrowprops={"arrowstyle":"-", "color":COLORS["Insertion Sort"]})
        legend(fig, ALGORITHMS)
        fig.tight_layout(rect=(0, .14, 1, 1))
        save(fig, name, f"{title}. C2 uses a seeded shuffle. Timing points are medians of "
             "five completed runs; missing points are DNF and are never interpolated. "
             "Counts use the documented comparison/move convention.")
    fig, ax = plt.subplots(figsize=(10, 4.7))
    conditions(ax, med)
    ax.set_title("Input order changes the winner at n = 10,000")
    legend(fig, ALGORITHMS)
    fig.tight_layout(rect=(0, .15, 1, 1))
    save(fig, "02_time_by_condition_n10000.png", "Five-run median execution time by input "
         "condition at n=10,000. Grouped bars use a log time axis and identify the actual contenders.")
    with plt.rc_context({"font.size":7, "axes.titlesize":9, "axes.labelsize":7,
                         "xtick.labelsize":6, "ytick.labelsize":6, "legend.fontsize":7,
                         "lines.markersize":4, "lines.linewidth":1.5}):
        fig, axes = plt.subplots(3, 2, figsize=(10.8, 5.9))
        for ax, (_, metric, norm, ylabel, _) in zip(
                [axes[0,0], axes[1,0], axes[1,1], axes[2,0], axes[2,1]], specs):
            growth(ax, med, metric, norm)
            ax.set_ylabel(ylabel)
        conditions(axes[0,1], med)
        titles = ["(a) C2 · execution time", "(b) Conditions · n = 10,000",
                  "(c) C2 · key comparisons", "(d) C2 · element moves",
                  "(e) C2 · time / (n log₂ n)", "(f) C2 · time / n²"]
        for ax, title in zip(axes.flat, titles):
            ax.set_title(title, loc="left")
        legend(fig, ALGORITHMS, columns=3)
        fig.tight_layout(rect=(0,.10,1,1), h_pad=1.1, w_pad=2.5)
        save(fig, "report_C_tournament.png", "Tournament: C2 growth in time, comparisons and "
             "moves; condition comparison at n=10,000; time normalised by n log₂ n and n². "
             "The shared legend applies to every panel. DNF points are absent.")


def topk_charts():
    med = load_medians("topk.csv")
    fig, axes = plt.subplots(2, 2, figsize=(10, 6))
    for ax, (n, condition) in zip(axes.flat, [(100000,"C1"),(100000,"C2"),(284807,"C1"),(284807,"C2")]):
        d = med.loc[med.n.eq(n) & med.condition.eq(condition)]
        for method in METHODS:
            dm = d.loc[d.algorithm.eq(method)].sort_values("k")
            ax.plot(dm.k, dm.median_s, marker=MARKERS[method], color=COLORS[method],
                    label=method, markeredgecolor="white", markeredgewidth=.5)
        finish(ax, logx=True, logy=True)
        ax.axvline(CONFIG.k, ls=":", color="#BCCBD5", lw=1)
        ax.set(title=f"{condition} · n = {n:,}", xlabel="Queue capacity K (transactions; log scale)",
               ylabel="Median time (s; log scale)")
    with plt.rc_context({"legend.fontsize":8}):
        legend(fig, METHODS, columns=3)
    fig.tight_layout(rect=(0,.09,1,1), h_pad=2, w_pad=2)
    caption = "Cost of producing an ordered Top-K queue, including final publication. "
    caption += "Five-run medians at both required sizes and C1/C2; the dotted guide marks K=52. "
    caption += "Full sort is measured separately at each K, including its prefix copy; DNF is not plotted as zero."
    # Both uses share exactly the same measured data and design.
    for name in ("09_topk_cost.png", "report_D_topk.png"):
        if name.startswith("report_"):
            fig.set_size_inches(10,4.2)
            for ax in axes.flat:
                ax.title.set_fontsize(10)
                ax.xaxis.label.set_fontsize(8)
                ax.yaxis.label.set_fontsize(8)
                ax.tick_params(labelsize=7)
            fig.tight_layout(rect=(0,.12,1,1),h_pad=.7,w_pad=2)
        for ext in ("png", "pdf", "svg"):
            fig.savefig(FIGURES / Path(name).with_suffix(f".{ext}"), dpi=240,
                        bbox_inches="tight", pad_inches=.16)
        CAPTIONS[name] = caption
    plt.close(fig)


def livefeed_charts():
    frame = pd.read_csv(RAW / "livefeed.csv")
    runs = frame.loc[frame.record_type.eq("run") & frame.window.notna()].copy()
    for col in ("window", "width_s", "cumulative_s"):
        runs[col] = pd.to_numeric(runs[col], errors="coerce")
    labels = {"rerank":"A · Re-rank all records", "heap":"B · Maintained size-K heap",
              "merge":"C · Sort window + merge"}

    def draw(ax, width):
        for strategy in labels:
            d = runs.loc[runs.width_s.eq(width) & runs.strategy.eq(strategy)]
            completed = frame.loc[frame.record_type.eq("summary") & frame.strategy.eq(strategy)
                                 & pd.to_numeric(frame.width_s,errors="coerce").eq(width)]
            if completed.empty:
                # Only assert a timeout when an explicit DNF record exists.
                dnf = frame.loc[frame.record_type.eq("dnf") & frame.strategy.eq(strategy)
                                & pd.to_numeric(frame.width_s, errors="coerce").eq(width)]
                if len(dnf):
                    ax.text(.03,.96, labels[strategy].split(" · ")[0]+" · DNF (>300 s watchdog)", transform=ax.transAxes,
                            va="top", color=COLORS[strategy], fontsize=8)
                continue
            group = d.groupby("window").cumulative_s.median().sort_index()
            ax.plot(group.index, group.values, color=COLORS[strategy], label=labels[strategy])
        ax.set(xlabel="Published window (count)", ylabel="Cumulative time (s; log scale)",
               title=f"{width//60}-minute windows · K = {CONFIG.k}")
        # A logarithmic scale keeps all three real cost curves legible.
        finish(ax, logy=True)
        ax.legend(loc="lower right", fontsize=7)

    for width, name in ((3600,"10_livefeed_1h.png"),(600,"11_livefeed_10min.png")):
        fig, ax = plt.subplots(figsize=(9,4.4))
        draw(ax, width)
        fig.tight_layout()
        save(fig, name, f"Median cumulative time at each publication over five complete "
             f"{width//60}-minute-window simulations. Log time reveals all strategies. "
             "Any explicit DNF has an annotation and no fabricated trajectory.")
    with plt.rc_context({"axes.titlesize":10, "axes.labelsize":8, "xtick.labelsize":7,
                         "ytick.labelsize":7}):
        fig, axes = plt.subplots(1,2,figsize=(10,2.5))
        for ax,width in zip(axes,(3600,600)):
            draw(ax,width)
        fig.tight_layout(w_pad=2)
        save(fig,"report_E_livefeed.png", "Median cumulative publication cost over five "
             "simulations at each window width. The time axis is logarithmic. "
             "Only complete five-run strategies have curves; any DNF is explicitly annotated.")


def inversion_chart():
    data = json.loads((ANALYSIS / "data_analysis.json").read_text())
    pairs = sorted((int(n),v) for n,v in data["inversions_c5"].items())
    n, values = map(np.array, zip(*pairs))
    fig, ax = plt.subplots(figsize=(9,4.2))
    ax.plot(n,values,marker="o",color=COLORS["Insertion Sort"], label="C5 · exact inversion count")
    for x,y in pairs:
        ax.annotate(f"{y:,}",(x,y),xytext=(0,10),textcoords="offset points",
                    ha="center",fontsize=8,color=INK)
    finish(ax,logx=True,logy=True)
    ax.set(xlabel="Input size n (transactions; log scale)",
           ylabel="Inversions (count; log scale)", title="Moving 1% of records can still create quadratic work")
    ax.legend(loc="lower right")
    fig.tight_layout()
    save(fig,"12_c5_inversions.png", "Exact C5 inversion counts for the required sizes. "
         "Only floor(0.01n) records are displaced; insertion sort still pays for every inversion.")


def main():
    theme()
    FIGURES.mkdir(parents=True,exist_ok=True)
    profile_chart()
    fraud_chart()
    tournament_charts()
    topk_charts()
    livefeed_charts()
    inversion_chart()
    (FIGURES / "captions.json").write_text(json.dumps(CAPTIONS,indent=2),encoding="utf-8")
    print(f"Exported {len(CAPTIONS)} figures as PNG, PDF and SVG to {FIGURES}")


if __name__ == "__main__":
    main()
