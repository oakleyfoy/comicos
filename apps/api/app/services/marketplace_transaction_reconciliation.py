from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.models import MarketplaceOrder, MarketplaceTransaction
from app.schemas.marketplace_orders import (
    MarketplaceTransactionMismatchResponse,
    MarketplaceTransactionReconciliationReportResponse,
)

RECONCILIATION_AMOUNT_MISMATCH = "amount_mismatch"
RECONCILIATION_MISSING_TRANSACTION = "missing_transaction"
RECONCILIATION_DUPLICATE_TRANSACTION = "duplicate_transaction"
RECONCILIATION_FEE_MISMATCH = "fee_mismatch"
RECONCILIATION_CURRENCY_MISMATCH = "currency_mismatch"


def _normalize_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


@dataclass(frozen=True)
class TransactionTotals:
    gross_amount: Decimal
    fee_amount: Decimal
    net_amount: Decimal


def calculate_order_totals(transactions: list[MarketplaceTransaction]) -> TransactionTotals:
    relevant = [row for row in transactions if row.transaction_status != "failed"]
    gross_amount = sum((_normalize_decimal(row.gross_amount) for row in relevant), Decimal("0.00"))
    fee_amount = sum((_normalize_decimal(row.fee_amount) for row in relevant), Decimal("0.00"))
    net_amount = sum((_normalize_decimal(row.net_amount) for row in relevant), Decimal("0.00"))
    return TransactionTotals(
        gross_amount=_normalize_decimal(gross_amount),
        fee_amount=_normalize_decimal(fee_amount),
        net_amount=_normalize_decimal(net_amount),
    )


def detect_transaction_mismatches(
    *,
    order: MarketplaceOrder,
    transactions: list[MarketplaceTransaction],
) -> tuple[MarketplaceTransactionMismatchResponse, ...]:
    mismatches: list[MarketplaceTransactionMismatchResponse] = []
    ordered_transactions = sorted(
        transactions,
        key=lambda row: (row.created_at, row.transaction_reference, row.id or 0),
    )

    if not ordered_transactions:
        mismatches.append(
            MarketplaceTransactionMismatchResponse(
                mismatch_code=RECONCILIATION_MISSING_TRANSACTION,
                message="Order has no imported marketplace transactions.",
                order_id=int(order.id or 0),
                transaction_references=[],
            )
        )
        return tuple(mismatches)

    seen_by_reference: dict[str, list[str]] = {}
    currency_mismatch_refs: list[str] = []
    for row in ordered_transactions:
        seen_by_reference.setdefault(row.transaction_reference, []).append(row.transaction_reference)
        if row.transaction_currency != order.order_currency:
            currency_mismatch_refs.append(row.transaction_reference)

    duplicate_refs = sorted(reference for reference, refs in seen_by_reference.items() if len(refs) > 1)
    if duplicate_refs:
        mismatches.append(
            MarketplaceTransactionMismatchResponse(
                mismatch_code=RECONCILIATION_DUPLICATE_TRANSACTION,
                message="Order has duplicate transaction references.",
                order_id=int(order.id or 0),
                transaction_references=duplicate_refs,
            )
        )

    if currency_mismatch_refs:
        mismatches.append(
            MarketplaceTransactionMismatchResponse(
                mismatch_code=RECONCILIATION_CURRENCY_MISMATCH,
                message="Transaction currency does not match the order currency.",
                order_id=int(order.id or 0),
                transaction_references=sorted(currency_mismatch_refs),
            )
        )

    totals = calculate_order_totals(ordered_transactions)
    if totals.gross_amount != _normalize_decimal(order.order_total):
        mismatches.append(
            MarketplaceTransactionMismatchResponse(
                mismatch_code=RECONCILIATION_AMOUNT_MISMATCH,
                message="Imported gross transaction total does not match the order total.",
                order_id=int(order.id or 0),
                transaction_references=sorted(row.transaction_reference for row in ordered_transactions),
            )
        )

    if totals.net_amount != _normalize_decimal(totals.gross_amount - totals.fee_amount):
        mismatches.append(
            MarketplaceTransactionMismatchResponse(
                mismatch_code=RECONCILIATION_FEE_MISMATCH,
                message="Transaction fee totals do not reconcile to the imported net amount.",
                order_id=int(order.id or 0),
                transaction_references=sorted(row.transaction_reference for row in ordered_transactions),
            )
        )

    return tuple(sorted(mismatches, key=lambda row: (row.mismatch_code, row.order_id, tuple(row.transaction_references))))


def reconcile_order_transactions(
    *,
    orders: list[MarketplaceOrder],
    transactions_by_order_id: dict[int, list[MarketplaceTransaction]],
) -> tuple[MarketplaceTransactionMismatchResponse, ...]:
    mismatches: list[MarketplaceTransactionMismatchResponse] = []
    for order in sorted(orders, key=lambda row: (row.ordered_at, row.id or 0)):
        mismatches.extend(
            detect_transaction_mismatches(
                order=order,
                transactions=transactions_by_order_id.get(int(order.id or 0), []),
            )
        )
    return tuple(sorted(mismatches, key=lambda row: (row.order_id, row.mismatch_code, tuple(row.transaction_references))))


def generate_transaction_report(
    *,
    orders: list[MarketplaceOrder],
    transactions_by_order_id: dict[int, list[MarketplaceTransaction]],
) -> MarketplaceTransactionReconciliationReportResponse:
    total_transactions = sum(len(rows) for rows in transactions_by_order_id.values())
    mismatches = reconcile_order_transactions(
        orders=orders,
        transactions_by_order_id=transactions_by_order_id,
    )
    return MarketplaceTransactionReconciliationReportResponse(
        mismatches=list(mismatches),
        total_orders=len(orders),
        total_transactions=total_transactions,
    )
