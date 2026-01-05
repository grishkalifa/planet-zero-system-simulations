# Phase 1 — Optimize Reinvestment Share (α)

## Goal
Find the reinvestment share **α** (portion of monthly net utility reinvested into US Gov bonds) that maximizes **cumulative community impact** over:
- 2 years (24 months)
- 5 years (60 months)
- 10 years (120 months)

We keep the "product" abstract: revenue is modeled as **net margin per active person per month**.

## Core Assumptions (Editable)
- Time step: 1 month
- Initial active people: A0 = 100 people
- Base monthly costs: C_base = €2,000 / month
- Bond annual rate: r_annual = 4% (conservative placeholder)
  - r_month = r_annual / 12
- Net margin per person per month: m = variable (€/person/month)
- Rule (conservative): if U(t) <= 0 then:
  - no split, no reinvest, no impact that month

## Definitions
### Utility
Revenue(t) = A(t) * m  
Costs(t) = C_base  
BondInterest(t) = r_month * BondCapital(t)

U(t) = Revenue(t) + BondInterest(t) - Costs(t)

### Reinvestment policy (sweep)
α ∈ {0.90, 0.80, 0.70, 0.60, 0.50}

If U(t) > 0:
- Reinvest(t) = α * U(t)  -> goes to BondCapital
- ImmediateImpact(t) = (1-α) * U(t) -> executed as community impact

If U(t) <= 0:
- Reinvest(t) = 0
- ImmediateImpact(t) = 0

### Stocks
BondCapital(t+1) = BondCapital(t) + Reinvest(t)
ImpactCum(t+1) = ImpactCum(t) + ImmediateImpact(t)

## What "Best α" means
For each horizon H ∈ {24, 60, 120} months, we compute:
- TotalImpact(H) = ImpactCum(H)
- BondCapital(H)
- % months with U(t) > 0
- Time-to-first-impact (first month where ImmediateImpact(t) > 0)

We select α that:
1) maximizes TotalImpact(H)
2) subject to survivability (U(t) > 0 most months)
3) (optional) subject to a minimum visible impact per month threshold

## Notes
- In Phase 1 we keep A(t) constant (A(t)=A0) to isolate the effect of α.
- In Phase 2 we will add growth/retention loops and cost scaling with A(t).
