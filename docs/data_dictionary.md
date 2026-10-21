# Data dictionary

The fixed simulation date is **2026-01-15**. Quantities are component units, prices are modeled in a single configurable business currency, and rates are fractions from 0 to 1.

- `suppliers.csv`: component-qualified supplier offers, performance, capacity, status, and explicit expedite capability.
- `orders.csv`: purchase commitments linked to suppliers and components.
- `inventory.csv`: warehouse stock, reservations, and safety stock. Available stock is `max(0, on_hand_quantity - reserved_quantity)`.
- `shipments.csv`: dispatched and received quantities with original and revised arrival dates.
- `production.csv`: component usage, planned output, capacity, priority, and downtime cost by line.
- `demand.csv`: daily component demand over a reproducible 31-day horizon.

The Motor X7 demo starts with 650 on hand and 50 reserved (600 available), approximately 100 units of daily demand, a 1,000-unit delayed order, and a revised arrival ten days after its original ETA. Alternatives deliberately vary in price, speed, capacity, quality, and status.

