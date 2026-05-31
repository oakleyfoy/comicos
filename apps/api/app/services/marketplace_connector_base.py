from __future__ import annotations

from abc import ABC, abstractmethod

from sqlmodel import Session

from app.schemas.marketplace import MarketplaceCapabilityRead, MarketplaceExecutionRead
from app.services.marketplace_execution import complete_execution, fail_execution, start_execution


class MarketplaceConnectorBase(ABC):
    def __init__(self, *, marketplace_id: int, account_id: int | None = None) -> None:
        self.marketplace_id = marketplace_id
        self.account_id = account_id

    @abstractmethod
    def connect(self, session: Session) -> MarketplaceExecutionRead:
        """Reserve a connect contract for future marketplace-specific connectors."""

    @abstractmethod
    def disconnect(self, session: Session) -> MarketplaceExecutionRead:
        """Reserve a disconnect contract for future marketplace-specific connectors."""

    @abstractmethod
    def validate_credentials(self, session: Session) -> bool:
        """Validate stored credentials without performing marketplace actions."""

    @abstractmethod
    def get_capabilities(self, session: Session) -> list[MarketplaceCapabilityRead]:
        """Return supported capabilities for the connector."""

    def create_execution(self, session: Session, *, execution_type: str, execution_uuid: str | None = None) -> MarketplaceExecutionRead:
        return start_execution(
            session,
            marketplace_id=self.marketplace_id,
            account_id=self.account_id,
            execution_type=execution_type,
            execution_uuid=execution_uuid,
        )

    def complete_execution(self, session: Session, *, execution_id: int) -> MarketplaceExecutionRead:
        return complete_execution(session, execution_id=execution_id)

    def fail_execution(self, session: Session, *, execution_id: int) -> MarketplaceExecutionRead:
        return fail_execution(session, execution_id=execution_id)
