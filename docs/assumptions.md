# Assumptions (Phase 1)

## Time and horizon
- Monthly time step
- Horizons: 6m (6), 12m (12), 18m (18), 2y (24), 5y (60), 10y (120)

## Base costs
- Base monthly costs (C_base): €2,000 / month

## People
- Initial active people (A0): 100
- In Phase 1 we keep A(t) constant to isolate reinvestment effects

## Bonds
- US Gov bond annual rate (r_annual): 4%
- Monthly approximation: r_month = r_annual / 12

## Revenue abstraction
- Net margin per active person per month: m (€/person/month)
- Revenue(t) = A0 * m

## Utility and rule
- U(t) = Revenue(t) + BondInterest(t) - C_base
- Conservative rule:
  - If U(t) <= 0, then reinvest = 0 and impact = 0 that month

## Reinvestment sweep
- α ∈ {0.90, 0.80, 0.70, 0.60, 0.50}
- If U(t) > 0:
  - Reinvest(t) = α * U(t) -> added to BondCapital
  - ImmediateImpact(t) = (1-α) * U(t) -> counted as community impact
