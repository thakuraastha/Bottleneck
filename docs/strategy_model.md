# Deterministic strategy model

Every candidate is simulated over the same horizon before scoring. The scoring dimensions are normalized as 0–100 benefits:

- Cost benefit: `100 - total_modeled_impact / comparison_ceiling * 100`.
- Delivery benefit: `100 - quantity-weighted expected_delivery_days / planning_horizon_days * 100`.
- Quality benefit: allocation-weighted supplier quality.
- Risk benefit: `100 - residual_risk`.

Values are clamped to 0–100. The default weighted score is 30% cost, 30% delivery, 20% quality, and 20% risk. Constraint-invalid candidates remain visible for audit but are never eligible for recommendation.

Additional procurement cost is the non-negative unit-price premium over the existing primary commitment plus any explicit expedite surcharge; the existing committed base spend is not counted twice. Hard validation covers exact allocation quantity, authorized supplier existence, active status, component qualification, aggregate capacity, minimum quality, explicit expedite support, planning-horizon delivery, and budget. Inventory, production, and contractual constraints will be expanded as their source fields are added in later phases.
