from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.marketplace import MarketplaceAccount as MarketplaceConnectorAccount
from app.models.marketplace import MarketplaceDefinition as MarketplaceConnectorDefinition
from app.models.marketplace_listing import MarketplaceListing
from app.schemas.marketplace_publish import MarketplacePublishRequest
from app.services.marketplace_listings import LISTING_STATUS_READY_TO_PUBLISH, _owner_listing_or_404


@dataclass(frozen=True)
class PublishValidationIssue:
    issue_code: str
    issue_message: str
    severity: str


def _append_issue(issues: list[PublishValidationIssue], *, code: str, message: str, severity: str = "ERROR") -> None:
    issues.append(PublishValidationIssue(issue_code=code, issue_message=message, severity=severity))


def validate_listing_for_publish(session: Session, *, owner_id: int, listing_id: int) -> list[PublishValidationIssue]:
    issues: list[PublishValidationIssue] = []
    try:
        listing = _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    except Exception:
        _append_issue(issues, code="listing_missing", message="Listing must exist and belong to the owner.")
        return issues

    if listing.status != LISTING_STATUS_READY_TO_PUBLISH:
        _append_issue(issues, code="listing_not_ready", message="Listing must be READY_TO_PUBLISH.")
    if not listing.listing_title.strip():
        _append_issue(issues, code="listing_title_missing", message="Listing must have a title.")
    if listing.asking_price is None:
        _append_issue(issues, code="listing_price_missing", message="Listing must have a price.")
    if listing.quantity is None or listing.quantity <= 0:
        _append_issue(issues, code="listing_quantity_invalid", message="Listing must have positive quantity.")
    return issues


def validate_marketplace_target(
    session: Session,
    *,
    owner_id: int,
    marketplace_id: int,
    marketplace_account_id: int | None,
) -> list[PublishValidationIssue]:
    issues: list[PublishValidationIssue] = []
    marketplace = session.get(MarketplaceConnectorDefinition, marketplace_id)
    if marketplace is None:
        _append_issue(issues, code="marketplace_missing", message="Target marketplace must exist.")
        return issues
    if not marketplace.enabled:
        _append_issue(issues, code="marketplace_disabled", message="Target marketplace must be enabled.")
    if marketplace_account_id is not None:
        account = session.get(MarketplaceConnectorAccount, marketplace_account_id)
        if account is None or account.owner_id != owner_id:
            _append_issue(issues, code="marketplace_account_missing", message="Target account must belong to the owner.")
        elif account.marketplace_id != marketplace_id:
            _append_issue(issues, code="marketplace_account_mismatch", message="Target account must match the target marketplace.")
    return issues


def validate_publish_request(session: Session, *, owner_id: int, payload: MarketplacePublishRequest) -> list[PublishValidationIssue]:
    issues = list(validate_listing_for_publish(session, owner_id=owner_id, listing_id=payload.listing_id))
    for index, target in enumerate(payload.targets):
        target_issues = validate_marketplace_target(
            session,
            owner_id=owner_id,
            marketplace_id=target.marketplace_id,
            marketplace_account_id=target.marketplace_account_id,
        )
        for issue in target_issues:
            _append_issue(
                issues,
                code=f"target_{index}_{issue.issue_code}",
                message=issue.issue_message,
                severity=issue.severity,
            )
    return issues
