# P66 Phase 2 — Quantity Intelligence

Splits buy guidance into `collection_quantity`, `spec_quantity`, `flip_quantity`, and `total_quantity` using P62 buy-queue scores (not rewritten in P62).

Rules: cap spec when demand is low; allow expansion when demand and priority are high; reduce totals when confidence is low.

Endpoints: `GET/POST /api/v1/quantity-intelligence/latest|build`
