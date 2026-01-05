# Planet Zero — System Dynamics Simulations

## Overview
This repository contains a series of **system dynamics simulations** designed to study how complex systems behave under different governance rules, feedback loops, and constraints.

The project is part of a broader exploration into **AGI-relevant system design**, focusing on how adaptive rules and internal state variables can produce stable, scalable, and resilient behavior without centralized optimization.

Each simulation represents a **completed stage** of analysis, following strict modeling requirements (stocks, flows, feedback loops, scenarios, dashboards, and written conclusions).

---

## Motivation
Rather than optimizing for a single metric (profit, growth, or impact), this project explores how **systems can self-regulate** when designed with the right internal feedback mechanisms.

This approach is directly relevant to:
- Artificial General Intelligence (AGI)
- Complex adaptive systems
- Organizational and economic system design
- Governance of autonomous agents

The core question across simulations is:

> *How can we design systems that make good decisions automatically, even under uncertainty and growth?*

---

## Completed Simulations

### Simulation 1 — Amazon Deforestation System
**Domain:** Ecological system  

**Goal:**  
Model the long-term behavior of deforestation under different regimes and identify tipping points and irreversible collapse thresholds.

**Key focus:**
- Natural resource as a finite stock
- Reinforcing and balancing feedback loops
- System collapse under unchecked extraction
- Long-term irreversible dynamics

📄 Documentation available in `/docs`.

---

### Simulation 2 — Planet Zero Reinvestment Governance
**Domain:** Socio-economic / organizational system  

**Goal:**  
Design and test a **dynamic reinvestment governance policy** that allows a system to survive, grow, and scale impact without collapsing.

Instead of using a fixed reinvestment rule (e.g. 50/50), the system implements:

\[
p = f(FS)
\]

Where:
- **p** = share of net utility reinvested into capital (BC)
- **FS** = Survival Fund coverage (months of operating costs)

**Key insights:**
- Fixed reinvestment percentages are suboptimal in early-stage systems
- Survival Fund (FS) acts as a global regulating variable
- The system adapts its behavior based on internal state, not targets
- Growth and hiring are enabled only when survival is guaranteed

This simulation introduces:
- Adaptive governance rules
- Automatic decision-making with optional human override
- Emergent stability without explicit optimization

---

## Why This Matters for AGI
These simulations are not about prediction — they are about **designing intelligent behavior**.

Relevance to AGI includes:
- Rule-based self-governance instead of hard-coded objectives
- Emergent intelligence from system structure
- Robustness over short-term optimization
- Transferable design principles for autonomous agents

The same logic can be applied to:
- AGI internal resource allocation
- Autonomous organizations
- Multi-agent coordination systems
- Safety-aware and alignment-focused AI architectures

---

## Repository Structure

```text
planet-zero-system-simulations/
│
├─ src/
│  ├─ pz_model.py              # Core system dynamics model
│  ├─ phase2_p_sweep.py        # Policy experiments and comparisons
│
├─ outputs/
│  ├─ csv/                     # Simulation results
│  ├─ plots/                   # Visual outputs
│
├─ dashboard/
│  └─ pz_dashboard.py          # Interactive parameter exploration
│
├─ docs/
│  ├─ phase1_reinvestment_governance.md
│  ├─ roadmap.md
│
├─ README.md

