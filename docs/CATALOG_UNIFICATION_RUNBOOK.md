# Inventory catalog unification — execution order

After deploying API migrations through **`20260626_0300`** (merge head):

1. **Phase C (data)** — `python scripts/unify_run_phase_c.py` (optional `--email`, `--dry-run`)
2. **Product** — photo import / acquisitions only for new intake (E1–E2 in app)
3. **Wipe (test reset)** — `python scripts/unify_wipe_test_collection.py` (optional `--email`, `--dry-run`)
4. **Phase D** — already in Alembic `20260626_0200` (drops `customer_order`, `order_item`, `variant`, `comic_issue`, `comic_title`)

Master **`catalog_*`** is never wiped by these scripts.

**E3 (catalog OCR)** — batch: `python scripts/p97_generate_catalog_ocr.py` (optional enrichment; photo matching uses fingerprints + OCR metadata when present).
