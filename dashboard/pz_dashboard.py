from __future__ import annotations

from pathlib import Path
import sys
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from pz_model import PZParams, simulate_pz  # type: ignore


st.set_page_config(page_title="Planet Zero Dashboard", layout="wide")
st.title("Planet Zero — Dashboard (Auto governance + Operator override)")

# Sidebar
st.sidebar.header("Horizon")
horizon = st.sidebar.selectbox("Months", [6, 12, 18, 24, 60, 120], index=1)

st.sidebar.header("Governance")
use_dynamic_p = st.sidebar.checkbox("Auto p = f(FS)", value=True)
use_override = st.sidebar.checkbox("Operator override p", value=False)
p_override = st.sidebar.slider("p_override (BC share)", 0.0, 1.0, 0.3, 0.05) if use_override else -1.0
p_input = st.sidebar.slider("p_to_bc input (used only if auto off & no override)", 0.1, 0.9, 0.3, 0.05)

st.sidebar.header("Starting state")
A0 = st.sidebar.number_input("A0", 1.0, 1_000_000.0, 100.0, 10.0)
m0 = st.sidebar.number_input("m0 (€/person/month)", 0.0, 10_000.0, 25.0, 1.0)
employees0 = st.sidebar.number_input("employees0", 1, 200, 2, 1)

st.sidebar.header("Costs")
cost_per_employee = st.sidebar.number_input("cost_per_employee", 0.0, 50_000.0, 1000.0, 50.0)
other_fixed_costs = st.sidebar.number_input("other_fixed_costs", 0.0, 100_000.0, 0.0, 50.0)

st.sidebar.header("Finance")
r_annual = st.sidebar.slider("bond annual rate", 0.0, 0.10, 0.04, 0.005)

st.sidebar.header("BPZ split")
fs_pct = st.sidebar.slider("FS_pct_of_BPZ", 0.1, 0.6, 0.30, 0.05)
impact_pct = st.sidebar.slider("Impact % of BPZ_rem", 0.1, 0.9, 0.60, 0.05)
rd_pct_internal = st.sidebar.slider("RD % of internal", 0.1, 0.9, 0.60, 0.05)

st.sidebar.header("Growth")
churn_rate = st.sidebar.slider("churn_rate", 0.0, 0.10, 0.03, 0.005)
acq_churn_ratio = st.sidebar.slider("acq_churn_ratio", 0.5, 1.5, 1.00, 0.05)
k_acq = st.sidebar.slider("k_acq (impact→acq boost)", 0.0, 5.0, 0.20, 0.05)

st.sidebar.header("p Phase-4 cap")
p4_max = st.sidebar.slider("p4_max (only matters if FS>=12)", 0.5, 0.9, 0.70, 0.05)

params = PZParams(
    r_annual=r_annual,
    A0=A0,
    m0=m0,
    employees0=int(employees0),
    cost_per_employee=cost_per_employee,
    other_fixed_costs=other_fixed_costs,
    fs_pct_of_bpz=fs_pct,
    impact_pct_of_bpz_rem=impact_pct,
    internal_pct_of_bpz_rem=1.0 - impact_pct,
    rd_pct_of_internal=rd_pct_internal,
    churn_rate=churn_rate,
    acq_churn_ratio=acq_churn_ratio,
    k_acq=k_acq,
    use_dynamic_p=use_dynamic_p,
    p_override=p_override,
    p4_max=p4_max,
)

summary = simulate_pz(months=horizon, p_to_bc=p_input, params=params, B0=0.0, FS0=0.0)

# KPIs
c1, c2, c3, c4 = st.columns(4)
c1.metric("Impact cumulative", f"{summary['impact_cum_end']:.2f}")
c2.metric("FS coverage (months)", f"{summary['fs_coverage_months_final']:.2f}")
c3.metric("BC end", f"{summary['BC_end']:.2f}")
c4.metric("Avg U/month", f"{summary['avg_U']:.2f}")

c5, c6, c7, c8 = st.columns(4)
c5.metric("A end", f"{summary['A_end']:.2f}")
c6.metric("m end", f"{summary['m_end']:.2f}")
c7.metric("Employees end", f"{int(summary['employees_end'])}")
c8.metric("% months U>0", f"{summary['pct_months_U_pos']*100:.1f}%")

st.info(
    f"Final FS ratio target: {int(summary['fs_ratio_final'])} months | "
    f"FS target final: €{summary['fs_target_final']:.0f} | "
    f"Phase final: {int(summary['phase_final'])} | "
    f"p_dyn_final: {summary['p_dyn_final']:.2f} | "
    f"p_eff_last: {summary['p_eff_last']:.2f}"
)

st.subheader("Quick p-override sweep (compare fixed policies)")
do_sweep = st.checkbox("Run fixed p sweep (override)", value=True)

if do_sweep:
    ps = [0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9]
    rows = []
    for p in ps:
        params_over = params.__class__(**{**params.__dict__, "p_override": p, "use_dynamic_p": True})
        rows.append(simulate_pz(months=horizon, p_to_bc=p, params=params_over, B0=0.0, FS0=0.0))
    df = pd.DataFrame(rows).sort_values("p_eff_last")

    st.dataframe(df[[
        "p_eff_last","impact_cum_end","fs_coverage_months_final","BC_end","FS_end",
        "avg_U","pct_months_U_pos","A_end","m_end","employees_end"
    ]], use_container_width=True)

    fig1 = plt.figure()
    ax1 = fig1.add_subplot(111)
    ax1.plot(df["p_eff_last"], df["impact_cum_end"], marker="o")
    ax1.set_xlabel("fixed p (override)")
    ax1.set_ylabel("impact cumulative")
    ax1.set_title("Impact vs fixed p")
    st.pyplot(fig1, clear_figure=True)

    fig2 = plt.figure()
    ax2 = fig2.add_subplot(111)
    ax2.plot(df["p_eff_last"], df["fs_coverage_months_final"], marker="o")
    ax2.set_xlabel("fixed p (override)")
    ax2.set_ylabel("FS coverage (months)")
    ax2.set_title("FS coverage vs fixed p")
    st.pyplot(fig2, clear_figure=True)
