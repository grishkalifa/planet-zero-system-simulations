from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from pz_model import PZParams, simulate_pz


OUT_CSV_DIR = Path("outputs/csv")
OUT_PLOT_DIR = Path("outputs/plots")


def ensure_dirs() -> None:
    OUT_CSV_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PLOT_DIR.mkdir(parents=True, exist_ok=True)


def run_path_until(months: int, params: PZParams, A0: float, m0: float) -> pd.DataFrame:
    """
    Runs month-by-month simulation to record FS coverage path and detect threshold crossing times.
    We reuse simulate_pz end-state for summary, but this function builds a trajectory.
    """
    # Minimal re-sim here (simple, explicit) rather than refactoring model.
    # We'll call simulate_pz at full horizon for final summary numbers,
    # and separately compute first times FS crosses thresholds using monthly steps.

    rm = params.r_annual / 12.0

    A = float(A0)
    m = float(m0)
    employees = int(params.employees0)
    BC = 0.0
    FS = 0.0

    hires = 0
    last_hire_month = -10_000

    rows = []

    for t in range(1, months + 1):
        costs = employees * params.cost_per_employee + params.other_fixed_costs
        revenue = A * m
        interest = rm * (BC + FS)
        U = revenue + interest - costs

        # FS coverage before allocation
        fs_cov = (FS / costs) if costs > 0 else np.inf

        # effective p
        if 0.0 <= params.p_override <= 1.0:
            p_eff = params.p_override
        elif params.use_dynamic_p:
            from pz_model import p_dynamic_from_fs  # local import to avoid circular
            p_eff = p_dynamic_from_fs(fs_cov, p4_max=params.p4_max)
        else:
            p_eff = 0.30  # irrelevant if not used; kept for completeness

        p_eff = max(0.0, min(1.0, p_eff))

        impact = 0.0

        if U > 0:
            BC_in = p_eff * U
            BPZ_in = (1.0 - p_eff) * U
            BC += BC_in

            FS_in = params.fs_pct_of_bpz * BPZ_in
            FS += FS_in

            BPZ_rem = (1.0 - params.fs_pct_of_bpz) * BPZ_in
            impact = params.impact_pct_of_bpz_rem * BPZ_rem
            internal = params.internal_pct_of_bpz_rem * BPZ_rem
            rd = params.rd_pct_of_internal * internal

            # churn & acquisition
            churn = params.churn_rate * A
            acq_baseline = params.acq_churn_ratio * churn
            acq_boost = params.k_acq * (impact / (costs + 1.0))
            acquisitions = acq_baseline + acq_boost
            A = max(0.0, A + acquisitions - churn)

            # margin growth
            g_m = params.km_margin * (impact / (costs + 1.0)) + params.krd_margin * (rd / (costs + 1.0))
            g_m = min(params.max_margin_growth, max(0.0, g_m))
            m = m * (1.0 + g_m)

            # hiring
            from pz_model import fs_ratio_for_employees
            fs_ratio = fs_ratio_for_employees(employees)
            fs_target = fs_ratio * costs
            if (t - last_hire_month) >= params.hire_cooldown_months:
                if FS >= params.hire_trigger_buffer * fs_target:
                    employees += 1
                    hires += 1
                    last_hire_month = t

        fs_cov_after = (FS / (employees * params.cost_per_employee + params.other_fixed_costs)) if (employees * params.cost_per_employee + params.other_fixed_costs) > 0 else np.inf

        rows.append({
            "t": t,
            "A": A,
            "m": m,
            "employees": employees,
            "BC": BC,
            "FS": FS,
            "U": U,
            "p_eff": p_eff,
            "impact": impact,
            "fs_cov_before": fs_cov,
            "fs_cov_after": fs_cov_after,
        })

    return pd.DataFrame(rows)


def first_crossing_month(traj: pd.DataFrame, threshold: float) -> float:
    hit = traj.index[traj["fs_cov_after"] >= threshold].tolist()
    if not hit:
        return float("nan")
    return float(traj.loc[hit[0], "t"])


def make_heatmap(df: pd.DataFrame, title: str, value_col: str, A_vals: list[float], m_vals: list[float], outpath: Path) -> None:
    pivot = df.pivot(index="m0", columns="A0", values=value_col).reindex(index=m_vals, columns=A_vals)

    fig = plt.figure()
    ax = fig.add_subplot(111)
    im = ax.imshow(pivot.values, aspect="auto", origin="lower")
    ax.set_xticks(range(len(A_vals)))
    ax.set_xticklabels([str(int(a)) for a in A_vals], rotation=0)
    ax.set_yticks(range(len(m_vals)))
    ax.set_yticklabels([str(m) for m in m_vals])
    ax.set_xlabel("A0 (people)")
    ax.set_ylabel("m0 (€/person/month)")
    ax.set_title(title)
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(outpath, dpi=200)
    plt.close(fig)


def main() -> None:
    ensure_dirs()

    # GRID (editable)
    A_vals = [10, 25, 50, 100, 250, 500]
    m_vals = [5, 10, 15, 20, 25, 40, 50, 75, 100, 150, 250]
    horizons = [24, 60, 120]

    # Baseline params (same as Phase 1)
    base = PZParams(
        r_annual=0.04,
        employees0=2,
        cost_per_employee=1000.0,
        other_fixed_costs=0.0,
        fs_pct_of_bpz=0.30,
        impact_pct_of_bpz_rem=0.60,
        internal_pct_of_bpz_rem=0.40,
        rd_pct_of_internal=0.60,
        churn_rate=0.03,
        acq_churn_ratio=1.00,   # neutral baseline
        k_acq=0.20,
        use_dynamic_p=True,
        p_override=-1.0,
        p4_max=0.70,
    )

    rows = []

    for H in horizons:
        for A0 in A_vals:
            for m0 in m_vals:
                params = replace(base, A0=float(A0), m0=float(m0))
                traj = run_path_until(H, params, A0=float(A0), m0=float(m0))

                t_fs3 = first_crossing_month(traj, 3.0)
                t_fs6 = first_crossing_month(traj, 6.0)
                t_fs12 = first_crossing_month(traj, 12.0)

                summary = simulate_pz(months=H, p_to_bc=0.30, params=params, B0=0.0, FS0=0.0)

                # viability flags (with positivity constraint)
                pos_ok = (summary["pct_months_U_pos"] >= 0.70)

                viable_3 = (not np.isnan(t_fs3)) and pos_ok
                viable_6 = (not np.isnan(t_fs6)) and pos_ok
                viable_12 = (not np.isnan(t_fs12)) and pos_ok

                rows.append({
                    "horizon": H,
                    "A0": float(A0),
                    "m0": float(m0),
                    "time_to_fs3": t_fs3,
                    "time_to_fs6": t_fs6,
                    "time_to_fs12": t_fs12,
                    "viable_fs3": int(viable_3),
                    "viable_fs6": int(viable_6),
                    "viable_fs12": int(viable_12),
                    "impact_cum_end": summary["impact_cum_end"],
                    "FS_end": summary["FS_end"],
                    "BC_end": summary["BC_end"],
                    "employees_end": summary["employees_end"],
                    "pct_months_U_pos": summary["pct_months_U_pos"],
                    "avg_U": summary["avg_U"],
                    "A_end": summary["A_end"],
                    "m_end": summary["m_end"],
                    "p_eff_last": summary["p_eff_last"],
                    "phase_final": summary["phase_final"],
                    "fs_cov_final": summary["fs_coverage_months_final"],
                })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV_DIR / "phase2_viability_grid_raw.csv", index=False)

    # Summary
    summary_rows = []
    for H in horizons:
        dH = df[df["horizon"] == H]
        summary_rows.append({
            "horizon": H,
            "grid_points": len(dH),
            "pct_viable_fs3": dH["viable_fs3"].mean(),
            "pct_viable_fs6": dH["viable_fs6"].mean(),
            "pct_viable_fs12": dH["viable_fs12"].mean(),
            "max_impact": dH["impact_cum_end"].max(),
        })
    df_sum = pd.DataFrame(summary_rows)
    df_sum.to_csv(OUT_CSV_DIR / "phase2_viability_grid_summary.csv", index=False)

    # Heatmaps per horizon (time to FS3 as primary)
    for H in horizons:
        dH = df[df["horizon"] == H].copy()
        # replace NaN times with large number for visualization
        dH["time_to_fs3_vis"] = dH["time_to_fs3"].fillna(H + 1)
        make_heatmap(
            dH,
            title=f"Time to FS>=3 months (H={H}) — NaN shown as >H",
            value_col="time_to_fs3_vis",
            A_vals=[float(a) for a in A_vals],
            m_vals=[float(m) for m in m_vals],
            outpath=OUT_PLOT_DIR / f"phase2_heatmap_time_to_fs3_H{H}.png",
        )

    print("Saved:")
    print(" - outputs/csv/phase2_viability_grid_raw.csv")
    print(" - outputs/csv/phase2_viability_grid_summary.csv")
    print(" - outputs/plots/phase2_heatmap_time_to_fs3_H24.png")
    print(" - outputs/plots/phase2_heatmap_time_to_fs3_H60.png")
    print(" - outputs/plots/phase2_heatmap_time_to_fs3_H120.png")


if __name__ == "__main__":
    main()
