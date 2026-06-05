# P63 Phase 3 — Acquisition Opportunity Intelligence

**Service:** `p63_acquisition_opportunity_service.py`  
**Tables:** `acquisition_opportunity_snapshot`, `acquisition_opportunity_item`

Merges active want-list rows and forward release issues not already owned, scored with P62/P61-style issue intelligence (read-only). Actions: `BUY_NOW`, `WATCH_PRICE`, `ADD_TO_WANT_LIST`, `WAIT`, `PASS`.
