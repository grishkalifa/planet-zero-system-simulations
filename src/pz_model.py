from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
import math


@dataclass(frozen=True)
class PZParams:
    # Finance
    r_annual: float = 0.04  # bond annual rate

    # Starting state
    A0: float = 100.0       # active people
    m0: float = 25.0        # net margin per person per month (after COGS/variable costs, before fixed ops)
    employees0: int = 2

    # Costs
    cost_per_employee: float = 1000.0
    other_fixed_costs: float = 0.0  # tools, hosting, etc.

    # BPZ internal allocation
    fs_pct_of_bpz: float = 0.30          # Survival Fund (FS) gets 30% of BPZ_in always
    impact_pct_of_bpz_rem: float = 0.60  # of BPZ remaining (after FS), 60% impact
    internal_pct_of_bpz_rem: float = 0.40  # after FS, 40% internal

    # Internal split (only RD used for growth)
    rd_pct_of_internal: float = 0.60
    wellbeing_pct_of_internal: float = 0.25
    legal_pct_of_internal: float = 0.15

    # Growth dynamics
    churn_rate: float = 0.03         # monthly churn fraction of A
    acq_churn_ratio: float = 1.00    # baseline: acquisitions = churn (neutral)
    k_acq: float = 0.20              # acquisition boost sensitivity to impact intensity

    km_margin: float = 0.010         # margin growth sensitivity to impact intensity
    krd_margin: float = 0.006        # margin growth sensitivity to RD intensity
    max_margin_growth: float = 0.03  # cap monthly margin growth

    # Hiring rule
    hire_cooldown_months: int = 3
    hire_trigger_buffer: float = 1.20  # hire if FS >= buffer * FS_target

    # Governance for p (BC share of positive net utility)
    use_dynamic_p: bool = True
    p_override: float = -1.0  # if in [0,1], overrides; if -1 => no override
    p4_max: float = 0.70      # Phase-4 max p (can evolve later with rules)

    rev_growth: float = 0.0



def r_monthly(r_annual: float) -> float:
    return r_annual / 12.0


def fs_ratio_for_employees(employees: int) -> int:
    """
    Survival ratio maturity rule:
      - <= 2 employees: 3 months
      - 3 to 6 employees: 6 months
      - > 6 employees: 12 months
    """
    if employees <= 2:
        return 3
    if employees <= 6:
        return 6
    return 12


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def p_bounds_by_fs(fs_cov: float, p4_max: float = 0.70):
    """
    Hybrid policy (phase ranges + smooth within-phase interpolation):

    Phase 1: FS<3        => p in [0.05, 0.15]
    Phase 2: 3<=FS<6     => p in [0.20, 0.35]
    Phase 3: 6<=FS<12    => p in [0.30, 0.50]
    Phase 4: FS>=12      => p in [0.40, p4_max]

    Returns (p_min, p_max, phase_id, lambda_in_phase in [0,1])
    """
    if fs_cov < 3.0:
        pmin, pmax = 0.05, 0.15
        lam = fs_cov / 3.0
        phase = 1
    elif fs_cov < 6.0:
        pmin, pmax = 0.20, 0.35
        lam = (fs_cov - 3.0) / 3.0
        phase = 2
    elif fs_cov < 12.0:
        pmin, pmax = 0.30, 0.50
        lam = (fs_cov - 6.0) / 6.0
        phase = 3
    else:
        pmin, pmax = 0.40, p4_max
        lam = (fs_cov - 12.0) / 12.0
        phase = 4

    lam = clamp(lam, 0.0, 1.0)
    return pmin, pmax, phase, lam


def p_dynamic_from_fs(fs_cov: float, p4_max: float = 0.70) -> float:
    pmin, pmax, _, lam = p_bounds_by_fs(fs_cov, p4_max=p4_max)
    return pmin + lam * (pmax - pmin)


def simulate_pz(
    *,
    months: int,
    p_to_bc: float,
    params: PZParams,
    B0: float = 0.0,       # BC bond capital
    FS0: float = 0.0,      # survival fund capital (invested liquid/low risk)
) -> Dict[str, float]:
    """
    Planet Zero dynamic model:

    Monthly:
      costs = employees*cost_per_employee + other_fixed_costs
      revenue = A * m
      interest = rm * (BC + FS)
      U = revenue + interest - costs

    If U <= 0: conservative freeze (no split, no impact spending, no growth updates).
    If U > 0:
      Determine p_eff:
        - operator override (p_override) if set
        - else dynamic p from FS coverage if use_dynamic_p
        - else fixed input p_to_bc

      Split:
        BC_in  = p_eff * U
        BPZ_in = (1-p_eff) * U

      BPZ internal:
        FS_in = fs_pct_of_bpz * BPZ_in
        BPZ_rem = (1-fs_pct_of_bpz)*BPZ_in
          impact = impact_pct_of_bpz_rem * BPZ_rem
          internal = internal_pct_of_bpz_rem * BPZ_rem
            RD = rd_pct_of_internal * internal

      Growth:
        churn = churn_rate * A
        acquisitions = acq_churn_ratio * churn + k_acq*(impact/(costs+1))
        A_next = A + acquisitions - churn
        m grows with impact and RD, capped.

      Hiring:
        FS_target = fs_ratio(employees)*costs
        if FS >= hire_trigger_buffer*FS_target and cooldown ok -> hire +1
    """
    rm = r_monthly(params.r_annual)

    # states
    A = float(params.A0)
    m = float(params.m0)
    employees = int(params.employees0)

    BC = float(B0)
    FS = float(FS0)

    # metrics
    impact_cum = 0.0
    months_u_pos = 0
    first_impact_month: Optional[int] = None
    u_sum = 0.0

    hires = 0
    last_hire_month = -10_000

    # track final p stats
    last_p_eff: float = float("nan")
    last_phase: float = float("nan")

    for t in range(1, months + 1):
        costs = employees * params.cost_per_employee + params.other_fixed_costs

        revenue = A * m
        interest = rm * (BC + FS)
        U = revenue + interest - costs
        u_sum += U

        if U > 0:
            months_u_pos += 1

            # FS coverage BEFORE allocation (governance observes current state)
            fs_cov = (FS / costs) if costs > 0 else float("inf")

            # effective p (override > dynamic > fixed)
            if 0.0 <= params.p_override <= 1.0:
                p_eff = params.p_override
            elif params.use_dynamic_p:
                p_eff = p_dynamic_from_fs(fs_cov, p4_max=params.p4_max)
            else:
                p_eff = p_to_bc

            p_eff = clamp(p_eff, 0.0, 1.0)
            last_p_eff = p_eff

            # phase for reporting
            pmin, pmax, phase_id, _lam = p_bounds_by_fs(fs_cov, p4_max=params.p4_max)
            last_phase = float(phase_id)

            # Split
            BC_in = p_eff * U
            BPZ_in = (1.0 - p_eff) * U

            BC += BC_in

            # BPZ allocation
            FS_in = params.fs_pct_of_bpz * BPZ_in
            FS += FS_in

            BPZ_rem = (1.0 - params.fs_pct_of_bpz) * BPZ_in

            impact = params.impact_pct_of_bpz_rem * BPZ_rem
            internal = params.internal_pct_of_bpz_rem * BPZ_rem
            rd = params.rd_pct_of_internal * internal

            # accumulate impact
            impact_cum += impact
            if first_impact_month is None and impact > 0:
                first_impact_month = t

            # growth
            intensity_den = costs + 1.0

            churn = params.churn_rate * A
            acq_baseline = params.acq_churn_ratio * churn
            acq_boost = params.k_acq * (impact / intensity_den)
            acquisitions = acq_baseline + acq_boost

            A = max(0.0, A + acquisitions - churn)

            g_m = params.km_margin * (impact / intensity_den) + params.krd_margin * (rd / intensity_den)
            g_m = min(params.max_margin_growth, max(0.0, g_m))
            m = m * (1.0 + g_m)

            # hiring decision (post-allocation FS)
            fs_ratio = fs_ratio_for_employees(employees)
            fs_target = fs_ratio * costs

            if (t - last_hire_month) >= params.hire_cooldown_months:
                if FS >= params.hire_trigger_buffer * fs_target:
                    employees += 1
                    hires += 1
                    last_hire_month = t
        # else: conservative freeze

    pct_u_pos = months_u_pos / months if months > 0 else 0.0

    # final targets
    final_costs = employees * params.cost_per_employee + params.other_fixed_costs
    fs_ratio_final = fs_ratio_for_employees(employees)
    fs_target_final = fs_ratio_final * final_costs
    fs_cov_final = (FS / final_costs) if final_costs > 0 else float("inf")

    # final dynamic p range info (based on final FS coverage)
    pmin_f, pmax_f, phase_f, lam_f = p_bounds_by_fs(fs_cov_final, p4_max=params.p4_max)
    p_dyn_final = p_dynamic_from_fs(fs_cov_final, p4_max=params.p4_max)

    return {
        "months": months,
        "p_to_bc_input": p_to_bc,
        "p_eff_last": last_p_eff,
        "phase_last": last_phase,

        "impact_cum_end": impact_cum,
        "BC_end": BC,
        "FS_end": FS,

        "employees_end": employees,
        "hires_total": hires,
        "A_end": A,
        "m_end": m,

        "avg_U": u_sum / months if months > 0 else 0.0,
        "pct_months_U_pos": pct_u_pos,
        "first_impact_month": float(first_impact_month) if first_impact_month is not None else float("nan"),

        "fs_ratio_final": float(fs_ratio_final),
        "fs_target_final": fs_target_final,
        "fs_coverage_months_final": fs_cov_final,

        "p_range_min_final": pmin_f,
        "p_range_max_final": pmax_f,
        "p_dyn_final": p_dyn_final,
        "phase_final": float(phase_f),
        "lambda_in_phase_final": lam_f,
    }
