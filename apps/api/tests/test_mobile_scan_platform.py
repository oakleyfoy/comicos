"""Backward-compatible alias for P80-01 tests in test_mobile_scanning.py."""

from test_mobile_scanning import (  # noqa: F401
    test_mobile_scan_isolation,
    test_mobile_scan_p79_qr_storage_entity,
    test_mobile_scan_upc_identification_and_intelligence,
)
