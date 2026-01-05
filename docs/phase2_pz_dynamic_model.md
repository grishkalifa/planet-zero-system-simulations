# Phase 2 — Planet Zero Dynamic Model (BC vs BPZ + Survival Fund + Growth)

## Objective
Find the best split of positive net utility U(t) between:
- BC (bond capital) and
- BPZ (impact + internal operations)

We sweep p = share of U allocated to BC.

## Key mechanisms
- U(t) = A(t)*m(t) + interest(BC+FS) - operating_costs(t)
- If U(t) <= 0: conservative freeze (no split, no impact)
- If U(t) > 0:
  - BC_in = p * U(t)
  - BPZ_in = (1-p) * U(t)

### Inside BPZ (fixed rules)
- FS_in = 30% of BPZ_in (always)
- BPZ_remaining = 70% of BPZ_in
  - Impact = 60% of BPZ_remaining
  - Internal = 40% of BPZ_remaining
    - RD = 60% of Internal

### Survival Fund (FS) maturity rule
FS target is dynamic:
- employees <= 2  -> 3 months of costs
- employees 3..6  -> 6 months of costs
- employees > 6   -> 12 months of costs

FS is invested in low-risk liquid assets (modeled with same rate as BC for simplicity).

### Growth feedbacks (both enabled)
- A(t) increases with impact (acquisition) and decreases with churn
- m(t) increases with impact and RD, capped per month

## Outputs
- cumulative impact (community)
- BC end, FS end
- FS coverage in months
- employees/hires, A_end, m_end
- best p per horizon (6/12/18/24/60/120 months)
