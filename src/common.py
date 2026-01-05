from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Iterable


@dataclass(frozen=True)
class ModelParams:
    # Core assumptions
    A0: int = 100                      # active people (constant in Phase 1)
    C_base: float = 2000.0             # monthly base costs in €
    r_annual: float = 0.04             # annual bond rate (e.g., 0.04 for 4%)
    B0: float = 0.0                    # initial bond capital in €

    # Policy sweep
    alphas: tuple[float, ...] = (0.90, 0.80, 0.70, 0.60, 0.50)

    # Margins to test (€/person/month)
    margins: tuple[float, ...] = (10, 15, 20, 25, 30, 40, 50)

    # Horizons in months (including early checkpoints)
    horizons: tuple[int, ...] = (6, 12, 18, 24, 60, 120)


def r_monthly(r_annual: float) -> float:
    # Simple monthly approximation
    return r_annual / 12.0


def simulate_phase1(
    *,
    months: int,
    A0: int,
    C_base: float,
    r_annual: float,
    alpha: float,
    margin_per_person: float,
    B0: float = 0.0,
) -> Dict[str, float]:
    """
    Phase 1 model:
    - A(t) is constant = A0
    - Revenue(t) = A0 * margin_per_person
    - Bond interest each month = r_month * B(t)
    - Utility U(t) = Revenue + Interest - C_base
    - Conservative rule: if U <= 0 => reinvest = 0 and impact = 0 that month
    - If U > 0:
        reinvest = alpha * U  (added to bond capital)
        impact   = (1-alpha) * U (counted as immediate impact)
    """
    rm = r_monthly(r_annual)

    bond_capital = float(B0)
    impact_cum = 0.0
    months_positive_u = 0
    first_impact_month = None

    # For some summary stats
    u_sum = 0.0
    u_positive_sum = 0.0

    for t in range(1, months + 1):
        revenue = A0 * float(margin_per_person)
        interest = rm * bond_capital
        u = revenue + interest - float(C_base)

        u_sum += u
        if u > 0:
            months_positive_u += 1
            u_positive_sum += u

            reinvest = alpha * u
            impact = (1.0 - alpha) * u

            bond_capital += reinvest
            impact_cum += impact

            if first_impact_month is None and impact > 0:
                first_impact_month = t
        # else: conservative freeze (no reinvest, no impact)

    pct_positive_u = months_positive_u / months if months > 0 else 0.0

    return {
        "months": months,
        "A0": A0,
        "C_base": C_base,
        "r_annual": r_annual,
        "alpha": alpha,
        "margin_per_person": float(margin_per_person),
        "bond_capital_end": bond_capital,
        "impact_cum": impact_cum,
        "months_positive_u": months_positive_u,
        "pct_months_positive_u": pct_positive_u,
        "first_impact_month": float(first_impact_month) if first_impact_month is not None else float("nan"),
        "avg_u": u_sum / months if months > 0 else 0.0,
        "avg_u_positive": (u_positive_sum / months_positive_u) if months_positive_u > 0 else 0.0,
    }
