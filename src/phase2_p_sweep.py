from __future__ import annotations

from pathlib import Path
from dataclasses import replace
import pandas as pd
import matplotlib.pyplot as plt

from pz_model import PZParams, simulate_pz


OUT_CSV_DIR = Path("outputs/csv")
OUT_PLOT_DIR = Path("outputs/plots")


def ensure_dirs() -> None:
    OUT_CSV_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PLOT_DIR.mkdir(parents=True, exist_ok=True)


def run_auto(params: PZParams, horizons: list[int]) -> pd.DataFrame:
    rows = []
    for H in horizons:
        params_auto = replace(params, use_dynamic_p=True, p_override=-1.0)
        rows.append(simulate_pz(months=H, p_to_bc=0.30, params=params_auto, B0=0.0, FS0=0.0))
    df = pd.DataFrame(rows)
    df.insert(0, "policy", "AUTO_p=f(FS)")
    return df


def run_override_sweep(params: PZParams, horizons: list[int], p_values: list[float]) -> pd.DataFrame:
    rows = []
    for H in horizons:
        for p in p_values:
            # override always wins, even if use_dynamic_p=True
            params_over = replace(params, use_dynamic_p=True, p_override=p)
            rows.append(simulate_pz(months=H, p_to_bc=p, params=params_over, B0=0.0, FS0=0.0))
    df = pd.DataFrame(rows)
    df.insert(0, "policy", "OVERRIDE_fixed_p")
    return df


def pick_best_override(df_override: pd.DataFrame) -> pd.DataFrame:
    """
    Best p among OVERRIDE runs per horizon.
    Primary objective: maximize cumulative impact.
    Tie-breakers: higher FS coverage, then higher %U>0, then higher BC.
    """
    d = df_override.copy()
    d = d.sort_values(
        by=["months", "impact_cum_end", "fs_coverage_months_final", "pct_months_U_pos", "BC_end"],
        ascending=[True, False, False, False, False],
    )
    best = (
        d.groupby("months", as_index=False)
        .first()
        .loc[:, [
            "months",
            "p_override_used",  # we'll add below
            "impact_cum_end", "FS_end", "BC_end", "fs_coverage_months_final",
            "employees_end", "hires_total", "A_end", "m_end", "avg_U", "pct_months_U_pos"
        ]]
    )
    best = best.rename(columns={"months": "horizon_months", "p_override_used": "best_p_override"})
    return best


def add_p_override_used(df: pd.DataFrame) -> pd.DataFrame:
    # convenience column: for override sweep, p_eff_last should equal the override p
    out = df.copy()
    out["p_override_used"] = out["p_eff_last"]
    return out


def plot_compare_auto_vs_best_override(df_auto: pd.DataFrame, df_best: pd.DataFrame) -> None:
    # align horizons
    auto = df_auto.set_index("months")
    best = df_best.set_index("horizon_months")

    horizons = sorted(auto.index.tolist())

    # Impact comparison
    fig1 = plt.figure()
    ax1 = fig1.add_subplot(111)
    ax1.plot(horizons, [auto.loc[h, "impact_cum_end"] for h in horizons], marker="o", label="AUTO")
    ax1.plot(horizons, [best.loc[h, "impact_cum_end"] for h in horizons], marker="o", label="Best OVERRIDE")
    ax1.set_title("Impact cumulative: AUTO vs Best OVERRIDE")
    ax1.set_xlabel("Horizon (months)")
    ax1.set_ylabel("Cumulative impact (€)")
    ax1.legend()
    fig1.tight_layout()
    fig1.savefig(OUT_PLOT_DIR / "phase2_compare_impact_auto_vs_best_override.png", dpi=200)
    plt.close(fig1)

    # FS coverage comparison
    fig2 = plt.figure()
    ax2 = fig2.add_subplot(111)
    ax2.plot(horizons, [auto.loc[h, "fs_coverage_months_final"] for h in horizons], marker="o", label="AUTO")
    ax2.plot(horizons, [best.loc[h, "fs_coverage_months_final"] for h in horizons], marker="o", label="Best OVERRIDE")
    ax2.set_title("FS coverage: AUTO vs Best OVERRIDE")
    ax2.set_xlabel("Horizon (months)")
    ax2.set_ylabel("FS coverage (months of costs)")
    ax2.legend()
    fig2.tight_layout()
    fig2.savefig(OUT_PLOT_DIR / "phase2_compare_fs_auto_vs_best_override.png", dpi=200)
    plt.close(fig2)


def main() -> None:
    ensure_dirs()

    horizons = [6, 12, 18, 24, 60, 120]
    p_values = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]

    # Baseline parameters (feel free to adjust later)
    params = PZParams(
        r_annual=0.04,
        A0=100.0,
        m0=25.0,
        employees0=2,
        cost_per_employee=1000.0,
        other_fixed_costs=0.0,

        fs_pct_of_bpz=0.30,
        impact_pct_of_bpz_rem=0.60,
        internal_pct_of_bpz_rem=0.40,
        rd_pct_of_internal=0.60,

        churn_rate=0.03,
        acq_churn_ratio=1.00,
        k_acq=0.20,

        use_dynamic_p=True,
        p_override=-1.0,
        p4_max=0.70,
    )

    # AUTO runs
    df_auto = run_auto(params, horizons)
    df_auto.to_csv(OUT_CSV_DIR / "phase2_auto_policy.csv", index=False)

    # OVERRIDE sweep
    df_over = run_override_sweep(params, horizons, p_values)
    df_over = add_p_override_used(df_over)
    df_over.to_csv(OUT_CSV_DIR / "phase2_override_full_sweep.csv", index=False)

    # best override per horizon
    df_best = (
        df_over[df_over["policy"] == "OVERRIDE_fixed_p"]
        .copy()
    )
    # pick best
    df_best = df_best.sort_values(
        by=["months", "impact_cum_end", "fs_coverage_months_final", "pct_months_U_pos", "BC_end"],
        ascending=[True, False, False, False, False],
    ).groupby("months", as_index=False).first()

    df_best_out = df_best.loc[:, [
        "months", "p_override_used", "impact_cum_end", "FS_end", "BC_end", "fs_coverage_months_final",
        "employees_end", "hires_total", "A_end", "m_end", "avg_U", "pct_months_U_pos"
    ]].rename(columns={"months": "horizon_months", "p_override_used": "best_p_override"})

    df_best_out.to_csv(OUT_CSV_DIR / "phase2_best_override_by_horizon.csv", index=False)

    # Compare plots
    plot_compare_auto_vs_best_override(df_auto, df_best_out)

    print("Done.")
    print("Saved:")
    print(" -", OUT_CSV_DIR / "phase2_auto_policy.csv")
    print(" -", OUT_CSV_DIR / "phase2_override_full_sweep.csv")
    print(" -", OUT_CSV_DIR / "phase2_best_override_by_horizon.csv")
    print(" -", OUT_PLOT_DIR / "phase2_compare_impact_auto_vs_best_override.png")
    print(" -", OUT_PLOT_DIR / "phase2_compare_fs_auto_vs_best_override.png")


if __name__ == "__main__":
    main()
