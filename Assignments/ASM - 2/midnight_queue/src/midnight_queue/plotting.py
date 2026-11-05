"""Generate the required publication-quality figures from measured CSVs."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from midnight_queue.config import CONFIG, PROJECT_ROOT

FIGURES = PROJECT_ROOT / "outputs" / "figures"
RAW = PROJECT_ROOT / "outputs" / "raw"
ANALYSIS = PROJECT_ROOT / "outputs" / "analysis"
COLORS = {
    "Insertion Sort": "#D1495B",
    "Merge Sort": "#00798C",
    "Naive Quick Sort": "#EDAE49",
    "Hardened Quick Sort": "#003D5B",
    "Heap Sort": "#6A4C93",
    "Size-K Heap": "#00798C",
    "Bounded Insertion Buffer": "#D1495B",
    "Full Sort (Hardened Quick Sort)": "#003D5B",
    "rerank": "#D1495B",
    "heap": "#00798C",
    "merge": "#EDAE49",
}
MARKERS = {
    "Insertion Sort": "o",
    "Merge Sort": "s",
    "Naive Quick Sort": "^",
    "Hardened Quick Sort": "D",
    "Heap Sort": "v",
    "Size-K Heap": "o",
    "Bounded Insertion Buffer": "s",
    "Full Sort (Hardened Quick Sort)": "D",
}
CAPTIONS: dict[str, str] = {}


def _save(fig, name: str, caption: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIGURES / name, dpi=200, bbox_inches="tight")
    plt.close(fig)
    CAPTIONS[name] = caption


def tournament() -> pd.DataFrame:
    path = RAW / "tournament.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    med = frame[frame.record_type == "median"].copy()
    for col in ("n", "median_s", "comparisons", "moves"):
        if col in med:
            med[col] = pd.to_numeric(med[col], errors="coerce")
    return med


def plot_profile() -> None:
    profile = json.loads((PROJECT_ROOT / "outputs" / "profile.json").read_text())
    bands = [int(k) for k in profile["band_counts"]]
    counts = [profile["band_counts"][str(b)] for b in bands]
    frauds = [profile["fraud_by_band"][str(b)] for b in bands]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.bar(bands, counts, color="#A8C5DA", label="All transactions")
    ax.bar(bands, frauds, color="#D1495B", label="Fraud-labelled")
    ax.set_yscale("log")
    ax.set_xticks(range(10))
    ax.set_xlabel("Risk band (dimensionless)")
    ax.set_ylabel("Transaction count (log scale)")
    ax.set_title("Risk-band distribution and fraud labels")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    _save(
        fig,
        "07_band_distribution.png",
        "Fig. A1. Risk bands over the full 284,807-row file. Class is shown "
        "only after ranking for evaluation. Bands 0 and 1 are empty; nearly "
        "all frauds occur in bands 6-9.",
    )


def plot_fraud_curve() -> None:
    curve = pd.read_csv(ANALYSIS / "fraud_curve.csv")
    summary = json.loads((ANALYSIS / "data_analysis.json").read_text())
    k_half = summary["fraud_capture"]["k_half"]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.plot(curve["k"], curve["fraction"], color="#003D5B", lw=1.8)
    ax.axhline(0.5, color="#888888", ls="--", lw=1, label="50% of frauds")
    y = curve.loc[curve["k"] == k_half, "fraction"].iloc[0]
    ax.scatter([k_half], [y], color="#D1495B", zorder=5, label=f"K={k_half:,}")
    ax.set_xscale("log")
    ax.set_xlabel("K: queue capacity (transactions, log scale)")
    ax.set_ylabel("Fraction of all 492 frauds captured")
    ax.set_ylim(0, 1.02)
    ax.set_title("Fraud capture as the shift queue grows")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(alpha=0.25)
    _save(
        fig,
        "08_fraud_capture.png",
        "Fig. A2. Fraud capture is evaluated only after the queue is built. "
        "The smallest queue capturing at least half of all frauds is "
        f"K={k_half:,}.",
    )


def plot_tournament(med: pd.DataFrame) -> None:
    if med.empty:
        return
    alg_names = [
        "Insertion Sort",
        "Merge Sort",
        "Naive Quick Sort",
        "Hardened Quick Sort",
        "Heap Sort",
    ]

    def line_plot(metric: str, ylabel: str, title: str, name: str, caption: str):
        fig, ax = plt.subplots(figsize=(7.2, 4.1))
        sub = med[med.condition == "C2"]
        for algorithm in alg_names:
            d = sub[sub.algorithm == algorithm].sort_values("n")
            d = d[d[metric].notna()]
            if d.empty:
                continue
            ax.plot(
                d["n"],
                d[metric],
                marker=MARKERS[algorithm],
                label=algorithm,
                color=COLORS[algorithm],
                lw=1.8,
                ms=5,
            )
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("n (transactions, log scale)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend(frameon=False, fontsize=8, ncol=2)
        ax.grid(alpha=0.25, which="both")
        _save(fig, name, caption)

    line_plot(
        "median_s",
        "Median execution time (seconds, log scale)",
        "Full-sort execution time on shuffled input C2",
        "01_time_vs_n_C2.png",
        "Fig. C1. Medians of five timed runs on C2. Missing points are DNF "
        "or not-yet-run; they are never plotted as measurements.",
    )
    line_plot(
        "comparisons",
        "Key comparisons (count, log scale)",
        "Key comparisons on shuffled input C2",
        "03_comparisons_vs_n_C2.png",
        "Fig. C3. Instrumented logical comparator calls on C2. Counts are "
        "deterministic and identical across the five repetitions.",
    )
    line_plot(
        "moves",
        "Element moves (count, log scale)",
        "Element moves on shuffled input C2",
        "04_moves_vs_n_C2.png",
        "Fig. C4. Element moves under the documented move convention. A swap "
        "counts as three record assignments.",
    )

    # Grouped bars at n=10,000.
    sub = med[med.n == 10_000]
    fig, ax = plt.subplots(figsize=(8.0, 3.9))
    conditions = ["C1", "C2", "C3", "C4", "C5", "C6"]
    width = 0.15
    x = np.arange(len(conditions))
    for i, algorithm in enumerate(alg_names):
        vals = []
        for c in conditions:
            row = sub[(sub.condition == c) & (sub.algorithm == algorithm)]
            vals.append(row["median_s"].iloc[0] if not row.empty else np.nan)
        ax.bar(
            x + (i - 2) * width,
            vals,
            width,
            label=algorithm,
            color=COLORS[algorithm],
        )
    ax.set_yscale("log")
    ax.set_xticks(x, conditions)
    ax.set_xlabel("Input condition")
    ax.set_ylabel("Median execution time (seconds, log scale)")
    ax.set_title("Execution time across C1-C6 at n = 10,000")
    ax.legend(frameon=False, fontsize=7, ncol=3)
    ax.grid(axis="y", alpha=0.25, which="both")
    _save(
        fig,
        "02_time_by_condition_n10000.png",
        "Fig. C2. Five-run medians at n=10,000. Absent bars are runs that did "
        "not complete; they are not zero-time measurements.",
    )

    # Normalised time.
    for metric, denom_name, label, name, caption in (
        (
            "median_s",
            "nlogn",
            "Time / (n log$_2$ n) (s per unit)",
            "05_time_nlogn_vs_n_C2.png",
            "Fig. C5. Time divided by n log2 n. A flat line is consistent "
            "with n log n growth; upward drift indicates extra polynomial work.",
        ),
        (
            "median_s",
            "n2",
            "Time / n$^2$ (s per transaction$^2$)",
            "06_time_n2_vs_n_C2.png",
            "Fig. C6. Time divided by n squared. A roughly horizontal line "
            "for a quadratic contender separates it from n log n contenders.",
        ),
    ):
        fig, ax = plt.subplots(figsize=(7.2, 4.0))
        sub_c2 = med[med.condition == "C2"].copy()
        for algorithm in alg_names:
            d = sub_c2[sub_c2.algorithm == algorithm].sort_values("n")
            if d.empty:
                continue
            denominator = (
                d["n"] * np.log2(d["n"])
                if denom_name == "nlogn"
                else d["n"].astype(float) ** 2
            )
            ax.plot(
                d["n"],
                d["median_s"] / denominator,
                marker=MARKERS[algorithm],
                label=algorithm,
                color=COLORS[algorithm],
                lw=1.8,
                ms=5,
            )
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("n (transactions, log scale)")
        ax.set_ylabel(label)
        ax.set_title(f"Normalised execution time on C2 ({denom_name})")
        ax.legend(frameon=False, fontsize=8, ncol=2)
        ax.grid(alpha=0.25, which="both")
        _save(fig, name, caption)


def plot_topk() -> None:
    path = RAW / "topk.csv"
    if not path.exists():
        return
    frame = pd.read_csv(path)
    med = frame[(frame.record_type == "median") & (frame.k.notna())].copy()
    if med.empty:
        return
    med["k"] = pd.to_numeric(med["k"], errors="coerce")
    med["n"] = pd.to_numeric(med["n"], errors="coerce")
    med["median_s"] = pd.to_numeric(med["median_s"], errors="coerce")
    fig, axes = plt.subplots(2, 2, figsize=(8.2, 5.6), sharex=True)
    for row, n in enumerate((100_000, 284_807)):
        for col, condition in enumerate(("C1", "C2")):
            ax = axes[row][col]
            d = med[(med.n == n) & (med.condition == condition)]
            for method in (
                "Full Sort (Hardened Quick Sort)",
                "Size-K Heap",
                "Bounded Insertion Buffer",
            ):
                dm = d[d.algorithm == method].sort_values("k")
                dm = dm[dm.median_s.notna()]
                if dm.empty:
                    continue
                ax.plot(
                    dm["k"],
                    dm["median_s"],
                    marker=MARKERS.get(method, "o"),
                    label=method,
                    color=COLORS[method],
                    lw=1.6,
                )
            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.set_title(f"{condition}, n={n:,}")
            ax.set_xlabel("K (transactions)")
            ax.set_ylabel("Time (s)")
            ax.grid(alpha=0.25, which="both")
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
    fig.suptitle("Top-K queue construction cost", y=1.0)
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    fig.savefig(FIGURES / "09_topk_cost.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    CAPTIONS["09_topk_cost.png"] = (
        "Fig. D1. Cost of producing an ordered K-queue at the two required "
        "sizes and conditions. DNF points are omitted, not interpolated."
    )


def plot_livefeed() -> None:
    path = RAW / "livefeed.csv"
    if not path.exists():
        return
    frame = pd.read_csv(path)
    runs = frame[(frame.record_type == "run") & frame.window.notna()].copy()
    if runs.empty:
        return
    runs["window"] = pd.to_numeric(runs["window"])
    runs["cumulative_s"] = pd.to_numeric(runs["cumulative_s"], errors="coerce")
    for width, name in ((3600, "10_livefeed_1h.png"), (600, "11_livefeed_10min.png")):
        sub = runs[runs.width_s == width]
        if sub.empty:
            continue
        fig, ax = plt.subplots(figsize=(7.2, 3.8))
        for strategy in ("rerank", "heap", "merge"):
            d = sub[sub.strategy == strategy]
            if d.empty:
                continue
            group = (
                d.groupby("window")["cumulative_s"]
                .median()
                .reset_index()
                .sort_values("window")
            )
            ax.plot(
                group["window"],
                group["cumulative_s"],
                marker="o" if strategy == "heap" else None,
                ms=3,
                lw=1.8,
                label={
                    "rerank": "A: re-rank everything",
                    "heap": "B: maintained size-K heap",
                    "merge": "C: sort window + merge",
                }[strategy],
                color=COLORS[strategy],
            )
        ax.set_xlabel("Window number")
        ax.set_ylabel("Cumulative execution time (seconds)")
        ax.set_title(
            f"Live-feed cumulative cost, {width // 60}-minute windows"
        )
        ax.legend(frameon=False)
        ax.grid(alpha=0.25)
        missing = (
            " Strategy A exceeded the 300 s watchdog and is a genuine DNF."
            if sub[sub.strategy == "rerank"].empty
            else ""
        )
        _save(
            fig,
            name,
            f"Fig. E1. Median cumulative time across five complete simulations "
            f"with {width // 60}-minute windows and K={CONFIG.k}. Each "
            "published queue was checked against the independent reference."
            + missing,
        )


def plot_inversions() -> None:
    path = ANALYSIS / "data_analysis.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())
    inv = data["inversions_c5"]
    sizes = [int(k) for k in inv]
    values = [inv[str(n)] for n in sizes]
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    ax.plot(sizes, values, marker="o", color="#D1495B", lw=1.8)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("n (transactions, log scale)")
    ax.set_ylabel("Inversions (count, log scale)")
    ax.set_title("C5 inversion count used by insertion sort")
    ax.grid(alpha=0.25, which="both")
    _save(
        fig,
        "12_c5_inversions.png",
        "Fig. F1. Exact C5 inversion counts. They grow quadratically even "
        "though only 1% of records are displaced.",
    )


def _small_axes(ax) -> None:
    ax.tick_params(labelsize=5.6, length=2.5, width=0.5)
    for spine in ax.spines.values():
        spine.set_linewidth(0.5)


def plot_report_composites() -> None:
    """Compact multi-panel versions for the five-page report.

    The individual figures remain the detailed deliverables; these composites
    keep the printed report inside its strict page budget without dropping any
    required graph.
    """

    med = tournament()
    if med.empty:
        return
    alg_names = [
        "Insertion Sort",
        "Merge Sort",
        "Naive Quick Sort",
        "Hardened Quick Sort",
        "Heap Sort",
    ]
    plt.rcParams.update(
        {
            "font.size": 6.0,
            "axes.titlesize": 6.8,
            "axes.labelsize": 6.0,
            "legend.fontsize": 5.4,
            "xtick.labelsize": 5.6,
            "ytick.labelsize": 5.6,
        }
    )

    fig, axes = plt.subplots(3, 2, figsize=(7.4, 4.8), constrained_layout=True)
    ax = axes[0][0]
    for algorithm in alg_names:
        d = med[(med.condition == "C2") & (med.algorithm == algorithm)].sort_values(
            "n"
        )
        ax.plot(
            d.n,
            d.median_s,
            marker=MARKERS[algorithm],
            color=COLORS[algorithm],
            ms=2.5,
            lw=1.0,
            label=algorithm,
        )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("n (transactions, log)")
    ax.set_ylabel("Median time (s, log)")
    ax.set_title("(a) C2 time vs n")
    ax.grid(alpha=0.25, which="both")
    ax.legend(frameon=False, fontsize=4.7, ncol=1, loc="upper left")

    ax = axes[0][1]
    conditions = ["C1", "C2", "C3", "C4", "C5", "C6"]
    width = 0.16
    x = np.arange(len(conditions))
    sub = med[med.n == 10_000]
    for i, algorithm in enumerate(alg_names):
        vals = []
        for condition in conditions:
            row = sub[(sub.condition == condition) & (sub.algorithm == algorithm)]
            vals.append(row.median_s.iloc[0] if not row.empty else np.nan)
        ax.bar(
            x + (i - 2) * width,
            vals,
            width,
            color=COLORS[algorithm],
            label=algorithm,
        )
    ax.set_yscale("log")
    ax.set_xticks(x, conditions)
    ax.set_xlabel("Condition")
    ax.set_ylabel("Median time (s, log)")
    ax.set_title("(b) Time at n=10,000")
    ax.grid(axis="y", alpha=0.25, which="both")

    for col, metric, ylabel, title in (
        (0, "comparisons", "Key comparisons (count, log)", "(c) C2 comparisons"),
        (1, "moves", "Element moves (count, log)", "(d) C2 moves"),
    ):
        ax = axes[1][col]
        for algorithm in alg_names:
            d = med[
                (med.condition == "C2") & (med.algorithm == algorithm)
            ].sort_values("n")
            ax.plot(
                d.n,
                d[metric],
                marker=MARKERS[algorithm],
                color=COLORS[algorithm],
                ms=2.5,
                lw=1.0,
            )
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("n (transactions, log)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(alpha=0.25, which="both")

    for col, denom_name, ylabel, title in (
        (
            0,
            "nlogn",
            "Time / (n log$_2$ n) (s)",
            "(e) C2 time / n log n",
        ),
        (1, "n2", "Time / n$^2$ (s)", "(f) C2 time / n$^2$"),
    ):
        ax = axes[2][col]
        c2 = med[med.condition == "C2"]
        for algorithm in alg_names:
            d = c2[c2.algorithm == algorithm].sort_values("n")
            denominator = (
                d.n * np.log2(d.n)
                if denom_name == "nlogn"
                else d.n.astype(float) ** 2
            )
            ax.plot(
                d.n,
                d.median_s / denominator,
                marker=MARKERS[algorithm],
                color=COLORS[algorithm],
                ms=2.5,
                lw=1.0,
            )
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("n (transactions, log)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(alpha=0.25, which="both")

    for row in axes:
        for ax in row:
            _small_axes(ax)
    fig.savefig(FIGURES / "report_C_tournament.png", dpi=260, bbox_inches="tight")
    plt.close(fig)
    CAPTIONS["report_C_tournament.png"] = (
        "Fig. C1. Tournament: (a) median time on C2; (b) time by condition at "
        "n=10,000; (c) comparisons and (d) moves on C2; (e) time/(n log2 n); "
        "(f) time/n^2. DNF is absent, not zero."
    )

    # Top-K report composite.
    path = RAW / "topk.csv"
    if path.exists():
        frame = pd.read_csv(path)
        medk = frame[
            (frame.record_type == "median") & frame.k.notna()
        ].copy()
        for col in ("k", "n", "median_s"):
            medk[col] = pd.to_numeric(medk[col], errors="coerce")
        fig, axes = plt.subplots(2, 2, figsize=(7.4, 3.5), constrained_layout=True)
        for row, n in enumerate((100_000, 284_807)):
            for col, condition in enumerate(("C1", "C2")):
                ax = axes[row][col]
                d = medk[(medk.n == n) & (medk.condition == condition)]
                for method in (
                    "Full Sort (Hardened Quick Sort)",
                    "Size-K Heap",
                    "Bounded Insertion Buffer",
                ):
                    dm = d[d.algorithm == method].sort_values("k")
                    dm = dm[dm.median_s.notna()]
                    if dm.empty:
                        continue
                    ax.plot(
                        dm.k,
                        dm.median_s,
                        marker=MARKERS.get(method, "o"),
                        color=COLORS[method],
                        ms=2.5,
                        lw=1.0,
                        label=method,
                    )
                ax.set_xscale("log")
                ax.set_yscale("log")
                ax.set_title(f"({chr(97 + row * 2 + col)}) {condition}, n={n:,}")
                ax.set_xlabel("K (transactions, log)")
                ax.set_ylabel("Median time (s, log)")
                ax.grid(alpha=0.25, which="both")
                _small_axes(ax)
        # Put the legend inside the first panel.  A figure-level legend at the
        # bottom collided with the x-axis labels of the second row.
        axes[0][0].legend(
            frameon=False,
            fontsize=4.7,
            ncol=1,
            loc="upper left",
        )
        fig.savefig(
            FIGURES / "report_D_topk.png",
            dpi=260,
            bbox_inches="tight",
        )
        plt.close(fig)
        CAPTIONS["report_D_topk.png"] = (
            "Fig. D1. Ordered K-queue cost at the two required sizes and both "
            "C1 and C2. Full-sort cost is K-independent. DNF is omitted."
        )

    # Live-feed report composite.
    path = RAW / "livefeed.csv"
    if path.exists():
        frame = pd.read_csv(path)
        runs = frame[
            (frame.record_type == "run") & frame.window.notna()
        ].copy()
        if not runs.empty:
            runs["window"] = pd.to_numeric(runs["window"])
            runs["cumulative_s"] = pd.to_numeric(
                runs["cumulative_s"], errors="coerce"
            )
            fig, axes = plt.subplots(1, 2, figsize=(7.4, 2.4), constrained_layout=True)
            for ax, width in zip(axes, (3600, 600)):
                sub = runs[runs.width_s == width]
                for strategy in ("rerank", "heap", "merge"):
                    d = sub[sub.strategy == strategy]
                    if d.empty:
                        continue
                    group = (
                        d.groupby("window")["cumulative_s"]
                        .median()
                        .reset_index()
                        .sort_values("window")
                    )
                    ax.plot(
                        group.window,
                        group.cumulative_s,
                        lw=1.2,
                        label={
                            "rerank": "A: re-rank",
                            "heap": "B: maintained heap",
                            "merge": "C: window merge",
                        }[strategy],
                        color=COLORS[strategy],
                    )
                ax.set_xlabel("Window number")
                ax.set_ylabel("Cumulative time (s)")
                ax.set_title(f"{width // 60}-minute windows, K={CONFIG.k}")
                ax.grid(alpha=0.25)
                ax.legend(frameon=False, fontsize=5.2)
                _small_axes(ax)
            fig.savefig(
                FIGURES / "report_E_livefeed.png",
                dpi=260,
                bbox_inches="tight",
            )
            plt.close(fig)
            CAPTIONS["report_E_livefeed.png"] = (
                "Fig. E1. Median cumulative time over five complete live-feed "
                "simulations, 1-hour and 10-minute windows, K=52. The 10-minute "
                "re-rank is a genuine DNF and has no line."
            )


def write_captions() -> None:
    (FIGURES / "captions.json").write_text(
        json.dumps(CAPTIONS, indent=2), encoding="utf-8"
    )


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    plot_profile()
    plot_fraud_curve()
    med = tournament()
    plot_tournament(med)
    plot_topk()
    plot_livefeed()
    plot_inversions()
    plot_report_composites()
    write_captions()
    print(f"Figures written to {FIGURES}")


if __name__ == "__main__":
    from midnight_queue.visuals import main as polished_main
    polished_main()
