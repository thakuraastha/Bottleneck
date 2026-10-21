# Deterministic risk model

The risk score is a configurable business index from 0 to 100, not a probability.

- Delivery: `min(100, delay_days / 20 * 100)`.
- Inventory: shortage as a percentage of horizon demand plus up to 30 urgency points when safety stock is breached early, capped at 100.
- Financial: `min(100, modeled_exposure / 250,000 * 100)`.
- Production: `min(100, downtime_days / planning_horizon_days * 100)`.
- Overall: `0.25 delivery + 0.30 inventory + 0.20 financial + 0.25 production`.

Severity boundaries are LOW `[0,30)`, MEDIUM `[30,60)`, HIGH `[60,80)`, and CRITICAL `[80,100]`. Thresholds and weights are initial business policy and require calibration against observed outcomes.

