# P63 Phase 2 — Sell Signal Intelligence

**Service:** `sell_signal_service.py`  
**Tables:** `sell_signal_snapshot`, `sell_signal_item`

Uses sell-candidate heuristics plus inventory FMV context to produce `SELL_NOW`, `CONSIDER_SELLING`, `HOLD`, `GRADE_FIRST`, and `WATCH` actions with item statuses (`NEW`, `REVIEWED`, `LISTED`, `SOLD`, `DISMISSED`).
