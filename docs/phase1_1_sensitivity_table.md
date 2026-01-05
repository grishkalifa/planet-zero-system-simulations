# Phase 1.1 — Sensitivity Table (α vs margin vs horizon)

## Goal
Identify which reinvestment share **α** maximizes **cumulative impact** for different:
- horizons (2y / 5y / 10y)
- net margin per person per month (m)

This produces a map: (m, horizon) -> best α.

## Inputs to sweep
### Margins (m) to test
We will test a representative range (€/person/month):
- 10, 15, 20, 25, 30, 40, 50

### Reinvestment shares (α) to test
- 0.90, 0.80, 0.70, 0.60, 0.50

### Horizons
- 24, 60, 120 months

## Output table format
For each horizon, we will publish:

### Table A — Best α by margin
Columns:
- m
- best α
- TotalImpact at horizon
- BondCapital at horizon
- % months with U>0

### Table B — Full results (optional)
For each m, list TotalImpact for each α.

## Notes
- Break-even margin threshold (ignoring interest):
  - m* ≈ C_base / A0 = 2000 / 100 = €20 per person per month
- If m < m*, the system will likely produce U<=0 for many months, resulting in near-zero impact under the conservative rule.
