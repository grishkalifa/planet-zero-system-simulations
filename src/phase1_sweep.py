from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

from common import ModelParams, simulate_phase1


OUT_CSV_DIR = Path("outputs/csv")
OUT_PLOT_DIR = Path("outputs/plots")


def ensure_dirs() -> None:
    OUT_CSV_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PLOT_DIR.mkdir(parents=True, exist_ok=True)


def run_sweep(params: ModelParams) -> pd.DataFrame:
    rows = []
    for H in params.horizons:
        for m in params.margins:
            for a in params.alphas:
                rows.append(
                    simulate_phase1(
                        months=H,
                        A0=params.A0,
                        C_base=params.C_base,
                        r_annual=params.r_annual,
                        alpha=a,
                        margin_per_person=m,
                        B0=params.B0,
                    )
                )
    df = pd.DataFrame(rows)
    return df


def best_alpha_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each horizon and margin, pick alpha that maximizes cumulative impact.
    Ties broken by higher end bond capital, then higher pct positive months.
    """
    df2 = df.copy()

    # Sort for tie-breaking (descending)
    df2 = df2.sort_values(
        by=["impact_cum", "bond_capital_end", "pct_months_positive_u"],
        ascending=[False, False, False],
    )

    best = (
        df2.groupby(["months", "margin_per_person"], as_index=False)
        .first()
        .loc[:, [
            "months", "margin_per_person", "alpha",
            "impact_cum", "bond_capital_end",
            "pct_months_positive_u", "first_impact_month",
            "avg_u"
        ]]
        .rename(columns={
            "months": "horizon_months",
            "margin_per_person": "m",
            "alpha": "best_alpha",
            "impact_cum": "impact_cum_end",
            "bond_capital_end": "bond_capital_end",
            "pct_months_positive_u": "pct_positive_u",
            "first_impact_month": "first_impact_month",
            "avg_u": "avg_u_over_horizon"
        })
    )
    return best


def save_csv(df: pd.DataFrame, best: pd.DataFrame) -> None:
    df.to_csv(OUT_CSV_DIR / "phase1_full_sweep.csv", index=False)
    best.to_csv(OUT_CSV_DIR / "phase1_best_alpha_by_margin_and_horizon.csv", index=False)


def plot_best_alpha_heatmap(best: pd.DataFrame) -> None:
    """
    Simple heatmap-like table using matplotlib imshow.
    Axes:
      - y: horizons
      - x: margins
    Values:
      - best_alpha
    """
    pivot = best.pivot(index="horizon_months", columns="m", values="best_alpha").sort_index()
    horizons = list(pivot.index)
    margins = list(pivot.columns)

    fig = plt.figure()
    ax = fig.add_subplot(111)
    im = ax.imshow(pivot.values, aspect="auto")  # default colormap
    ax.set_title("Best α (reinvestment share) by margin and horizon")
    ax.set_xlabel("m = net margin per person per month (€/person/month)")
    ax.set_ylabel("Horizon (months)")
    ax.set_xticks(range(len(margins)))
    ax.set_xticklabels([str(int(x)) for x in margins])
    ax.set_yticks(range(len(horizons)))
    ax.set_yticklabels([str(int(h)) for h in horizons])

    # Annotate cells
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.values[i, j]
            ax.text(j, i, f"{val:.2f}", ha="center", va="center")

    fig.colorbar(im, ax=ax, shrink=0.9)
    fig.tight_layout()
    fig.savefig(OUT_PLOT_DIR / "best_alpha_heatmap.png", dpi=200)
    plt.close(fig)


def plot_impact_by_alpha(df: pd.DataFrame) -> None:
    """
    For each horizon, plot cumulative impact vs alpha for each margin.
    Produces one plot per horizon (readable, not too many lines).
    """
    for H in sorted(df["months"].unique()):
        sub = df[df["months"] == H].copy()
        # Keep alphas sorted descending so lines look consistent
        alphas_sorted = sorted(sub["alpha"].unique(), reverse=True)

        fig = plt.figure()
        ax = fig.add_subplot(111)
        for m in sorted(sub["margin_per_person"].unique()):
            s2 = sub[sub["margin_per_person"] == m].sort_values("alpha", ascending=False)
            ax.plot(s2["alpha"], s2["impact_cum"], marker="o", label=f"m={int(m)}")

        ax.set_title(f"Cumulative Impact at H={int(H)} months (by α and margin m)")
        ax.set_xlabel("α (reinvestment share into bonds)")
        ax.set_ylabel("Impact cumulative (€)")
        ax.set_xticks(alphas_sorted)
        ax.legend()
        fig.tight_layout()
        fig.savefig(OUT_PLOT_DIR / f"impact_vs_alpha_H{int(H)}.png", dpi=200)
        plt.close(fig)


def main() -> None:
    ensure_dirs()

    params = ModelParams(
        A0=100,
        C_base=2000.0,
        r_annual=0.04,
        B0=0.0,
        alphas=(0.90, 0.80, 0.70, 0.60, 0.50),
        margins=(10, 15, 20, 25, 30, 40, 50),
        horizons=(6, 12, 18, 24, 60, 120),
    )

    df = run_sweep(params)
    best = best_alpha_table(df)

    save_csv(df, best)
    plot_best_alpha_heatmap(best)
    plot_impact_by_alpha(df)

    print("Done.")
    print(f"Saved CSVs to: {OUT_CSV_DIR}")
    print(f"Saved plots to: {OUT_PLOT_DIR}")


if __name__ == "__main__":
    main()
