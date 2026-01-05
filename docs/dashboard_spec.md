# Dashboard Spec (Phase 1)

## Inputs (sliders)
- Horizons 6, 12, 18, 24, 60, 120 months
- A0 (initial active people)
- C_base (monthly base costs)
- m (net margin per person per month)
- r_annual (bond annual rate)
- α options (choose sweep set)

## Outputs (charts)
1) Cumulative Impact vs time (one line per α)
2) BondCapital vs time (one line per α)
3) Monthly Utility U(t) vs time (one line per α)
4) TotalImpact at Horizon (bar chart by α)

## KPIs
- Best α for chosen horizon
- Total impact at horizon
- Bond capital at horizon
- Break-even margin threshold: m* = C_base / A0 (approx, ignoring interest)
