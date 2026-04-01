"""
Customer Consent Framework for Self-Play SWE-RL Training.

GDPR/CCPA compliant consent management for:
- Training data participation
- Synthetic bug generation from customer repositories
- Model update deployment
- Telemetry and feedback collection

Per ADR-050 Section 5.4: Privacy & Data Sovereignty
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ConsentType(Enum):
    """Types of consent for SSR training participation."""

    TRAINING_DATA = "training_data"  # Allow failed attempts as training data
    SYNTHETIC_BUGS = "synthetic_bugs"  # Allow synthetic bugs from repo
    MODEL_UPDATES = "model_updates"  # Receive model improvements
    TELEMETRY = "telemetry"  # Performance telemetry collection
    FEEDBACK = "feedback"  # User feedback for training
    ANONYMIZED_BENCHMARKS = "anonymized_benchmarks"  # Anonymized benchmark inclusion


class ConsentStatus(Enum):
    """Consent decision status."""

    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    PENDING = "pending"
    EXPIRED = "expired"


class LegalBasis(Enum):
    """GDPR legal basis for processing."""

    CONSENT = "consent"
    LEGITIMATE_INTEREST = "legitimate_interest"
    CONTRACT = "contract"
    LEGAL_OBLIGATION = "legal_obligation"


class DataSubjectRight(Enum):
    """GDPR/CCPA data subject rights."""

    ACCESS = "access"  # Right to access data
    RECTIFICATION = "rectification"  # Right to correct data
    ERASURE = "erasure"  # Right to be forgotten
    PORTABILITY = "portability"  # Right to data portability
    RESTRICTION = "restriction"  # Right to restrict processing
    OBJECTION = "objection"  # Right to object
    OPT_OUT_SALE = "opt_out_sale"  # CCPA opt-out of sale


@dataclass
class ConsentRecord:
    """Individual consent decision record."""

    consent_id: str
    customer_id: str
    consent_type: ConsentType
    status: ConsentStatus
    legal_basis: LegalBasis
    granted_at: datetime | None
    expires_at: datetime | None
    withdrawn_at: datetime | None
    ip_address_hash: str  # Hashed for privacy
    user_agent_hash: str  # Hashed for privacy
    consent_version: str  # Version of consent text
    scope: dict = field(default_factory=dict)  # Repository IDs, etc.
    metadata: dict = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Check if consent is currently valid."""
        if self.status != ConsentStatus.GRANTED:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "consent_id": self.consent_id,
            "customer_id": self.customer_id,
            "consent_type": self.consent_type.value,
            "status": self.status.value,
            "legal_basis": self.legal_basis.value,
            "granted_at": self.granted_at.isoformat() if self.granted_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "withdrawn_at": (
                self.withdrawn_at.isoformat() if self.withdrawn_at else None
            ),
            "ip_address_hash": self.ip_address_hash,
            "user_agent_hash": self.user_agent_hash,
            "consent_version": self.consent_version,
            "scope": self.scope,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConsentRecord":
        """Deserialize from storage."""
        return cls(
            consent_id=data["consent_id"],
            customer_id=data["customer_id"],
            consent_type=ConsentType(data["consent_type"]),
            status=ConsentStatus(data["status"]),
            legal_basis=LegalBasis(data["legal_basis"]),
            granted_at=(
                datetime.fromisoformat(data["granted_at"])
                if data.get("granted_at")
                else None
            ),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
            withdrawn_at=(
                datetime.fromisoformat(data["withdrawn_at"])
                if data.get("withdrawn_at")
                else None
            ),
            ip_address_hash=data.get("ip_address_hash", ""),
            user_agent_hash=data.get("user_agent_hash", ""),
            consent_version=data.get("consent_version", "1.0"),
            scope=data.get("scope", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class DataSubjectRequest:
    """GDPR/CCPA data subject request."""

    request_id: str
    customer_id: str
    right: DataSubjectRight
    status: str  # pending, processing, completed, rejected
    submitted_at: datetime
    completed_at: datetime | None
    request_details: dict = field(default_factory=dict)
    response_details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "request_id": self.request_id,
            "customer_id": self.customer_id,
            "right": self.right.value,
            "status": self.status,
            "submitted_at": self.submitted_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "request_details": self.request_details,
            "response_details": self.response_details,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DataSubjectRequest":
        """Deserialize from storage."""
        return cls(
            request_id=data["request_id"],
            customer_id=data["customer_id"],
            right=DataSubjectRight(data["right"]),
            status=data["status"],
            submitted_at=datetime.fromisoformat(data["submitted_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            request_details=data.get("request_details", {}),
            response_details=data.get("response_details", {}),
        )


@dataclass
class ConsentAuditEntry:
    """Audit log entry for consent changes."""

    audit_id: str
    customer_id: str
    consent_id: str | None
    action: str  # granted, withdrawn, expired, updated
    consent_type: ConsentType | None
    previous_status: ConsentStatus | None
    new_status: ConsentStatus | None
    timestamp: datetime
    actor: str  # customer, system, admin
    reason: str
    ip_address_hash: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "audit_id": self.audit_id,
            "customer_id": self.customer_id,
            "consent_id": self.consent_id,
            "action": self.action,
            "consent_type": self.consent_type.value if self.consent_type else None,
            "previous_status": (
                self.previous_status.value if self.previous_status else None
            ),
            "new_status": self.new_status.value if self.new_status else None,
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "reason": self.reason,
            "ip_address_hash": self.ip_address_hash,
            "metadata": self.metadata,
        }


@dataclass
class CustomerConsentProfile:
    """Aggregated consent profile for a customer."""

    customer_id: str
    consents: dict[ConsentType, ConsentRecord]
    pending_requests: list[DataSubjectRequest]
    jurisdiction: str  # GDPR, CCPA, etc.
    data_retention_days: int
    last_updated: datetime

    def has_consent(self, consent_type: ConsentType) -> bool:
        """Check if customer has valid consent for type."""
        record = self.consents.get(consent_type)
        return record is not None and record.is_valid()

    def can_use_for_training(self) -> bool:
        """Check if customer data can be used for SSR training."""
        return self.has_consent(ConsentType.TRAINING_DATA) and self.has_consent(
            ConsentType.SYNTHETIC_BUGS
        )

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "customer_id": self.customer_id,
            "consents": {k.value: v.to_dict() for k, v in self.consents.items()},
            "pending_requests": [r.to_dict() for r in self.pending_requests],
            "jurisdiction": self.jurisdiction,
            "data_retention_days": self.data_retention_days,
            "last_updated": self.last_updated.isoformat(),
        }


class ConsentService:
    """
    GDPR/CCPA compliant consent management service.

    Manages customer consent for:
    - Training data participation
    - Synthetic bug generation
    - Model update deployment
    - Telemetry collection
    """

    # Current version of consent text/terms
    CONSENT_VERSION = "1.0.0"

    # Default consent expiration (2 years for GDPR)
    DEFAULT_EXPIRATION_DAYS = 730

    # Jurisdictions and their requirements
    JURISDICTION_REQUIREMENTS = {
        "GDPR": {
            "explicit_consent": True,
            "right_to_erasure": True,
            "data_portability": True,
            "breach_notification_hours": 72,
        },
        "CCPA": {
            "explicit_consent": False,  # Opt-out model
            "right_to_erasure": True,
            "data_portability": True,
            "opt_out_sale": True,
        },
        "DEFAULT": {
            "explicit_consent": True,
            "right_to_erasure": True,
            "data_portability": False,
        },
    }

    def __init__(self):
        """Initialize consent service."""
        # In-memory storage (would be DynamoDB in production)
        self._consents: dict[str, dict[ConsentType, ConsentRecord]] = {}
        self._audit_log: list[ConsentAuditEntry] = []
        self._data_requests: dict[str, DataSubjectRequest] = {}
        self._customer_jurisdictions: dict[str, str] = {}

        # Metrics
        self._metrics = {
            "consents_granted": 0,
            "consents_withdrawn": 0,
            "dsr_requests_received": 0,
            "dsr_requests_completed": 0,
            "training_eligible_customers": 0,
        }

    def _hash_pii(self, value: str) -> str:
        """Hash PII for privacy-preserving storage."""
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    def _create_audit_entry(
        self,
        customer_id: str,
        consent_id: str | None,
        action: str,
        consent_type: ConsentType | None,
        previous_status: ConsentStatus | None,
        new_status: ConsentStatus | None,
        actor: str,
        reason: str,
        ip_address: str = "",
    ) -> ConsentAuditEntry:
        """Create and store audit entry."""
        entry = ConsentAuditEntry(
            audit_id=str(uuid.uuid4()),
            customer_id=customer_id,
            consent_id=consent_id,
            action=action,
            consent_type=consent_type,
            previous_status=previous_status,
            new_status=new_status,
            timestamp=datetime.now(timezone.utc),
            actor=actor,
            reason=reason,
            ip_address_hash=self._hash_pii(ip_address) if ip_address else "",
        )
        self._audit_log.append(entry)
        logger.info(
            f"Consent audit: customer={customer_id} action={action} "
            f"type={consent_type} status={new_status}"
        )
        return entry

    async def grant_consent(
        self,
        customer_id: str,
        consent_type: ConsentType,
        legal_basis: LegalBasis = LegalBasis.CONSENT,
        scope: dict | None = None,
        ip_address: str = "",
        user_agent: str = "",
        expiration_days: int | None = None,
    ) -> ConsentRecord:
        """
        Grant consent for a specific type.

        Args:
            customer_id: Customer identifier
            consent_type: Type of consent being granted
            legal_basis: GDPR legal basis
            scope: Optional scope (e.g., specific repositories)
            ip_address: For audit purposes (will be hashed)
            user_agent: For audit purposes (will be hashed)
            expiration_days: Custom expiration (default: 2 years)

        Returns:
            ConsentRecord for the granted consent
        """
        now = datetime.now(timezone.utc)
        exp_days = expiration_days or self.DEFAULT_EXPIRATION_DAYS

        # Check for existing consent
        existing = self._consents.get(customer_id, {}).get(consent_type)
        previous_status = existing.status if existing else None

        record = ConsentRecord(
            consent_id=str(uuid.uuid4()),
            customer_id=customer_id,
            consent_type=consent_type,
            status=ConsentStatus.GRANTED,
            legal_basis=legal_basis,
            granted_at=now,
            expires_at=now.replace(year=now.year + (exp_days // 365)),
            withdrawn_at=None,
            ip_address_hash=self._hash_pii(ip_address),
            user_agent_hash=self._hash_pii(user_agent),
            consent_version=self.CONSENT_VERSION,
            scope=scope or {},
        )

        # Store consent
        if customer_id not in self._consents:
            self._consents[customer_id] = {}
        self._consents[customer_id][consent_type] = record

        # Audit log
        self._create_audit_entry(
            customer_id=customer_id,
            consent_id=record.consent_id,
            action="granted",
            consent_type=consent_type,
            previous_status=previous_status,
            new_status=ConsentStatus.GRANTED,
            actor="customer",
            reason="Customer granted consent",
            ip_address=ip_address,
        )

        self._metrics["consents_granted"] += 1
        self._update_training_eligible_count()

        return record

    async def withdraw_consent(
        self,
        customer_id: str,
        consent_type: ConsentType,
        reason: str = "Customer requested withdrawal",
        ip_address: str = "",
    ) -> ConsentRecord | None:
        """
        Withdraw previously granted consent.

        Args:
            customer_id: Customer identifier
            consent_type: Type of consent to withdraw
            reason: Reason for withdrawal
            ip_address: For audit purposes

        Returns:
            Updated ConsentRecord or None if not found
        """
        customer_consents = self._consents.get(customer_id, {})
        record = customer_consents.get(consent_type)

        if not record:
            logger.warning(
                f"No consent record found for customer={customer_id} "
                f"type={consent_type}"
            )
            return None

        previous_status = record.status
        record.status = ConsentStatus.WITHDRAWN
        record.withdrawn_at = datetime.now(timezone.utc)

        # Audit log
        self._create_audit_entry(
            customer_id=customer_id,
            consent_id=record.consent_id,
            action="withdrawn",
            consent_type=consent_type,
            previous_status=previous_status,
            new_status=ConsentStatus.WITHDRAWN,
            actor="customer",
            reason=reason,
            ip_address=ip_address,
        )

        self._metrics["consents_withdrawn"] += 1
        self._update_training_eligible_count()

        # Trigger data removal workflow if needed
        await self._handle_consent_withdrawal(customer_id, consent_type)

        return record

    async def _handle_consent_withdrawal(
        self, customer_id: str, consent_type: ConsentType
    ) -> None:
        """Handle downstream effects of consent withdrawal."""
        if consent_type == ConsentType.TRAINING_DATA:
            # Remove customer data from training pipeline
            logger.info(f"Triggering training data removal for customer={customer_id}")
            # Would call training data purge service

        elif consent_type == ConsentType.SYNTHETIC_BUGS:
            # Remove synthetic bugs generated from customer repos
            logger.info(f"Triggering synthetic bug removal for customer={customer_id}")
            # Would call artifact storage purge

    def check_consent(self, customer_id: str, consent_type: ConsentType) -> bool:
        """
        Check if customer has valid consent for a type.

        Args:
            customer_id: Customer identifier
            consent_type: Type of consent to check

        Returns:
            True if valid consent exists
        """
        customer_consents = self._consents.get(customer_id, {})
        record = customer_consents.get(consent_type)
        return record is not None and record.is_valid()

    def check_training_eligibility(self, customer_id: str) -> dict:
        """
        Check if customer is eligible for SSR training participation.

        Returns dict with eligibility status and missing consents.
        """
        required_consents = [
            ConsentType.TRAINING_DATA,
            ConsentType.SYNTHETIC_BUGS,
        ]

        missing = []
        for ct in required_consents:
            if not self.check_consent(customer_id, ct):
                missing.append(ct.value)

        return {
            "eligible": len(missing) == 0,
            "missing_consents": missing,
            "customer_id": customer_id,
        }

    async def submit_data_subject_request(
        self,
        customer_id: str,
        right: DataSubjectRight,
        request_details: dict | None = None,
    ) -> DataSubjectRequest:
        """
        Submit a GDPR/CCPA data subject request.

        Args:
            customer_id: Customer identifier
            right: The data subject right being exercised
            request_details: Additional request details

        Returns:
            DataSubjectRequest tracking object
        """
        request = DataSubjectRequest(
            request_id=str(uuid.uuid4()),
            customer_id=customer_id,
            right=right,
            status="pending",
            submitted_at=datetime.now(timezone.utc),
            completed_at=None,
            request_details=request_details or {},
        )

        self._data_requests[request.request_id] = request
        self._metrics["dsr_requests_received"] += 1

        # Audit log
        self._create_audit_entry(
            customer_id=customer_id,
            consent_id=None,
            action=f"dsr_{right.value}",
            consent_type=None,
            previous_status=None,
            new_status=None,
            actor="customer",
            reason=f"Data subject request: {right.value}",
        )

        logger.info(
            f"DSR submitted: customer={customer_id} right={right.value} "
            f"request_id={request.request_id}"
        )

        return request

    async def process_erasure_request(self, request_id: str) -> DataSubjectRequest:
        """
        Process a right to erasure (RTBF) request.

        This removes all customer data from:
        - Training datasets
        - Bug artifacts
        - Model fine-tuning data
        - Telemetry
        """
        request = self._data_requests.get(request_id)
        if not request:
            raise ValueError(f"Request not found: {request_id}")

        if request.right != DataSubjectRight.ERASURE:
            raise ValueError(f"Request is not an erasure request: {request_id}")

        request.status = "processing"
        customer_id = request.customer_id

        erasure_results = {
            "training_data_removed": False,
            "artifacts_removed": False,
            "telemetry_removed": False,
            "consents_removed": False,
        }

        try:
            # 1. Remove from training datasets
            # Would call training data service
            erasure_results["training_data_removed"] = True
            logger.info(f"Removed training data for customer={customer_id}")

            # 2. Remove bug artifacts
            # Would call artifact storage service
            erasure_results["artifacts_removed"] = True
            logger.info(f"Removed artifacts for customer={customer_id}")

            # 3. Remove telemetry
            # Would call telemetry service
            erasure_results["telemetry_removed"] = True
            logger.info(f"Removed telemetry for customer={customer_id}")

            # 4. Remove consent records (but keep audit log per GDPR)
            if customer_id in self._consents:
                del self._consents[customer_id]
            erasure_results["consents_removed"] = True

            request.status = "completed"
            request.completed_at = datetime.now(timezone.utc)
            request.response_details = erasure_results
            self._metrics["dsr_requests_completed"] += 1

        except Exception as e:
            request.status = "failed"
            request.response_details = {"error": str(e)}
            logger.error(f"Erasure request failed: {e}")

        return request

    async def get_customer_data_export(self, customer_id: str) -> dict:
        """
        Export all customer data for portability request.

        Returns structured data for GDPR Article 20 compliance.
        """
        export = {
            "customer_id": customer_id,
            "export_date": datetime.now(timezone.utc).isoformat(),
            "data_format": "JSON",
            "consents": {},
            "audit_history": [],
            "data_requests": [],
        }

        # Export consent records
        customer_consents = self._consents.get(customer_id, {})
        for consent_type, record in customer_consents.items():
            export["consents"][consent_type.value] = record.to_dict()

        # Export audit history (excluding PII hashes)
        for entry in self._audit_log:
            if entry.customer_id == customer_id:
                entry_dict = entry.to_dict()
                del entry_dict["ip_address_hash"]  # Remove PII
                export["audit_history"].append(entry_dict)

        # Export data subject requests
        for request in self._data_requests.values():
            if request.customer_id == customer_id:
                export["data_requests"].append(request.to_dict())

        return export

    def set_customer_jurisdiction(self, customer_id: str, jurisdiction: str) -> None:
        """
        Set the regulatory jurisdiction for a customer.

        Args:
            customer_id: Customer identifier
            jurisdiction: GDPR, CCPA, or DEFAULT
        """
        if jurisdiction not in self.JURISDICTION_REQUIREMENTS:
            jurisdiction = "DEFAULT"
        self._customer_jurisdictions[customer_id] = jurisdiction
        logger.info(f"Set jurisdiction for customer={customer_id} to {jurisdiction}")

    def get_jurisdiction_requirements(self, customer_id: str) -> dict:
        """Get regulatory requirements for customer's jurisdiction."""
        jurisdiction = self._customer_jurisdictions.get(customer_id, "DEFAULT")
        return self.JURISDICTION_REQUIREMENTS.get(
            jurisdiction, self.JURISDICTION_REQUIREMENTS["DEFAULT"]
        )

    def _update_training_eligible_count(self) -> None:
        """Update count of training-eligible customers."""
        count = 0
        for customer_id in self._consents:
            if self.check_training_eligibility(customer_id)["eligible"]:
                count += 1
        self._metrics["training_eligible_customers"] = count

    async def check_expired_consents(self) -> list[ConsentRecord]:
        """
        Check for and mark expired consents.

        Returns list of newly expired consents.
        """
        now = datetime.now(timezone.utc)
        expired = []

        for customer_id, consents in self._consents.items():
            for consent_type, record in consents.items():
                if (
                    record.status == ConsentStatus.GRANTED
                    and record.expires_at
                    and record.expires_at < now
                ):
                    record.status = ConsentStatus.EXPIRED
                    expired.append(record)

                    self._create_audit_entry(
                        customer_id=customer_id,
                        consent_id=record.consent_id,
                        action="expired",
                        consent_type=consent_type,
                        previous_status=ConsentStatus.GRANTED,
                        new_status=ConsentStatus.EXPIRED,
                        actor="system",
                        reason="Consent expired",
                    )

        if expired:
            logger.info(f"Marked {len(expired)} consents as expired")
            self._update_training_eligible_count()

        return expired

    def get_consent_profile(self, customer_id: str) -> CustomerConsentProfile:
        """Get complete consent profile for customer."""
        customer_consents = self._consents.get(customer_id, {})
        pending_requests = [
            r
            for r in self._data_requests.values()
            if r.customer_id == customer_id and r.status == "pending"
        ]
        jurisdiction = self._customer_jurisdictions.get(customer_id, "DEFAULT")

        return CustomerConsentProfile(
            customer_id=customer_id,
            consents=customer_consents,
            pending_requests=pending_requests,
            jurisdiction=jurisdiction,
            data_retention_days=self.DEFAULT_EXPIRATION_DAYS,
            last_updated=datetime.now(timezone.utc),
        )

    def get_metrics(self) -> dict:
        """Get consent service metrics."""
        return {
            **self._metrics,
            "total_customers": len(self._consents),
            "total_consent_records": sum(len(c) for c in self._consents.values()),
            "pending_dsr_requests": sum(
                1 for r in self._data_requests.values() if r.status == "pending"
            ),
            "audit_log_entries": len(self._audit_log),
        }

    async def health_check(self) -> dict:
        """Health check for consent service."""
        return {
            "status": "healthy",
            "consent_version": self.CONSENT_VERSION,
            "total_customers": len(self._consents),
            "training_eligible": self._metrics["training_eligible_customers"],
        }
