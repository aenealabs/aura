"""
Tests for PII Detection Service
===============================

ADR-056 Phase 3: Data Flow Analysis

Tests for PII field detection in code.
"""

import platform
import tempfile
from pathlib import Path

import pytest

from src.services.data_flow.pii_detector import PIIDetectionService
from src.services.data_flow.types import (
    ComplianceFramework,
    DataClassification,
    PIICategory,
)

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestPIIDetectionServiceMock:
    """Tests for PIIDetectionService in mock mode."""

    @pytest.fixture
    def detector(self):
        """Create mock detector."""
        return PIIDetectionService(use_mock=True)

    @pytest.mark.asyncio
    async def test_detect_in_file_mock(self, detector):
        """Test mock file detection returns sample data."""
        fields = await detector.detect_in_file("test.py")

        assert len(fields) > 0
        assert all(field.field_id for field in fields)
        assert any(field.pii_category == PIICategory.EMAIL for field in fields)
        assert any(field.pii_category == PIICategory.SSN for field in fields)

    @pytest.mark.asyncio
    async def test_detect_in_directory_mock(self, detector):
        """Test mock directory detection returns sample data."""
        fields = await detector.detect_in_directory("/some/path")

        assert len(fields) > 0


class TestPIIDetectionServiceReal:
    """Tests for PIIDetectionService with real code analysis."""

    @pytest.fixture
    def detector(self):
        """Create real detector."""
        return PIIDetectionService(use_mock=False)

    @pytest.mark.asyncio
    async def test_detect_in_file_nonexistent(self, detector):
        """Test detecting in nonexistent file returns empty list."""
        fields = await detector.detect_in_file("/nonexistent/file.py")
        assert fields == []

    @pytest.mark.asyncio
    async def test_detect_email_field(self, detector):
        """Test detecting email fields."""
        code = """
from dataclasses import dataclass

@dataclass
class User:
    id: int
    email: str
    email_address: str
    user_email: str
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            fields = await detector.detect_in_file(temp_path)
            assert len(fields) >= 1
            assert any(field.pii_category == PIICategory.EMAIL for field in fields)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_detect_name_fields(self, detector):
        """Test detecting name fields."""
        code = """
class Person:
    first_name: str
    last_name: str
    full_name: str
    user_name: str
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            fields = await detector.detect_in_file(temp_path)
            assert len(fields) >= 1
            assert any(field.pii_category == PIICategory.NAME for field in fields)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_detect_ssn_field(self, detector):
        """Test detecting SSN fields."""
        code = """
class Employee:
    employee_id: int
    ssn: str
    social_security_number: str
    tax_id: str
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            fields = await detector.detect_in_file(temp_path)
            assert len(fields) >= 1
            ssn_fields = [f for f in fields if f.pii_category == PIICategory.SSN]
            assert len(ssn_fields) >= 1
            # SSN should have restricted classification
            assert any(
                f.classification == DataClassification.RESTRICTED for f in ssn_fields
            )
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_detect_credit_card_fields(self, detector):
        """Test detecting credit card fields."""
        code = """
class PaymentInfo:
    card_number: str
    credit_card_number: str
    cvv: str
    expiry_date: str
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            fields = await detector.detect_in_file(temp_path)
            assert len(fields) >= 1
            cc_fields = [f for f in fields if f.pii_category == PIICategory.CREDIT_CARD]
            assert len(cc_fields) >= 1
            # Credit card should have PCI-DSS compliance tag
            assert any(
                ComplianceFramework.PCI_DSS in f.compliance_tags for f in cc_fields
            )
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_detect_medical_fields(self, detector):
        """Test detecting medical/HIPAA fields."""
        code = """
class Patient:
    patient_id: str
    medical_record_number: str
    diagnosis_code: str
    insurance_id: str
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            fields = await detector.detect_in_file(temp_path)
            assert len(fields) >= 1
            # Should detect HIPAA compliance
            assert any(ComplianceFramework.HIPAA in f.compliance_tags for f in fields)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_detect_phone_fields(self, detector):
        """Test detecting phone number fields."""
        code = """
class Contact:
    phone: str
    phone_number: str
    mobile_phone: str
    home_phone: str
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            fields = await detector.detect_in_file(temp_path)
            assert len(fields) >= 1
            assert any(field.pii_category == PIICategory.PHONE for field in fields)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_detect_address_fields(self, detector):
        """Test detecting address fields."""
        code = """
class Address:
    street_address: str
    city: str
    state: str
    zip_code: str
    postal_code: str
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            fields = await detector.detect_in_file(temp_path)
            assert len(fields) >= 1
            assert any(field.pii_category == PIICategory.ADDRESS for field in fields)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_detect_password_fields(self, detector):
        """Test detecting password/auth fields."""
        code = """
class Credentials:
    password: str
    password_hash: str
    api_key: str
    secret_token: str
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            fields = await detector.detect_in_file(temp_path)
            assert len(fields) >= 1
            assert any(field.pii_category == PIICategory.PASSWORD for field in fields)
            assert any(field.pii_category == PIICategory.API_KEY for field in fields)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_detect_ip_address_fields(self, detector):
        """Test detecting IP address fields."""
        code = """
class RequestLog:
    ip_address: str
    client_ip: str
    remote_addr: str
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            fields = await detector.detect_in_file(temp_path)
            assert len(fields) >= 1
            assert any(field.pii_category == PIICategory.IP_ADDRESS for field in fields)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_detect_no_pii(self, detector):
        """Test file without PII fields."""
        code = """
class Product:
    id: int
    name: str
    price: float
    quantity: int
    description: str
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            fields = await detector.detect_in_file(temp_path)
            # "name" might trigger as PII, but price/quantity/description shouldn't
            non_name_fields = [f for f in fields if f.pii_category != PIICategory.NAME]
            assert len(non_name_fields) == 0
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_detect_function_arguments(self, detector):
        """Test detecting PII in function arguments."""
        code = """
def create_user(email: str, phone_number: str, ssn: str):
    pass

def update_user(user_id: int, first_name: str, last_name: str):
    pass
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            fields = await detector.detect_in_file(temp_path)
            assert len(fields) >= 3
            categories = {f.pii_category for f in fields}
            assert PIICategory.EMAIL in categories
            assert PIICategory.PHONE in categories
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_detect_encryption_context(self, detector):
        """Test detecting encryption context for PII."""
        code = """
from cryptography.fernet import Fernet

class SecureUser:
    email: str  # encrypted using Fernet

    def encrypt_email(self, email):
        return self.cipher.encrypt(email.encode())
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            fields = await detector.detect_in_file(temp_path)
            email_fields = [f for f in fields if f.pii_category == PIICategory.EMAIL]
            # Should detect encryption context
            assert any(f.is_encrypted for f in email_fields)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_detect_masking_context(self, detector):
        """Test detecting masking context for PII."""
        code = """
class User:
    email: str  # masked in logs

    def mask_email(self, email):
        return email[:3] + "***" + email[-4:]
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            fields = await detector.detect_in_file(temp_path)
            email_fields = [f for f in fields if f.pii_category == PIICategory.EMAIL]
            # Should detect masking context
            assert any(f.is_masked for f in email_fields)
        finally:
            Path(temp_path).unlink()


class TestPIIDetectionServiceComplianceSummary:
    """Tests for compliance summary methods."""

    @pytest.fixture
    def detector(self):
        """Create mock detector."""
        return PIIDetectionService(use_mock=True)

    @pytest.mark.asyncio
    async def test_get_compliance_summary(self, detector):
        """Test compliance summary generation."""
        fields = await detector.detect_in_file("test.py")
        summary = detector.get_compliance_summary(fields)

        assert isinstance(summary, dict)
        # Mock data should have various compliance frameworks
        assert len(summary) > 0

    @pytest.mark.asyncio
    async def test_get_classification_summary(self, detector):
        """Test classification summary generation."""
        fields = await detector.detect_in_file("test.py")
        summary = detector.get_classification_summary(fields)

        assert isinstance(summary, dict)
        # Should have counts for various classifications
        assert DataClassification.RESTRICTED in summary
        assert DataClassification.CONFIDENTIAL in summary


class TestPIIDetectionServiceEdgeCases:
    """Edge case tests for PIIDetectionService."""

    @pytest.fixture
    def detector(self):
        """Create real detector."""
        return PIIDetectionService(use_mock=False)

    @pytest.mark.asyncio
    async def test_syntax_error_file(self, detector):
        """Test handling of files with syntax errors."""
        code = """
class User:
    email: str
    # Missing closing bracket
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            fields = await detector.detect_in_file(temp_path)
            # Should still detect via regex fallback
            assert isinstance(fields, list)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_empty_file(self, detector):
        """Test handling of empty files."""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            fields = await detector.detect_in_file(temp_path)
            assert fields == []
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_example_values_skipped(self, detector):
        """Test that example/test values are skipped."""
        code = """
# Example email for documentation
example_email = "test@example.com"
test_email = "user@test.com"
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            fields = await detector.detect_in_file(temp_path)
            # Example values should be filtered
            # Only field names should be detected, not the values
            assert all("example.com" not in f.field_name for f in fields)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_directory_detection(self, detector):
        """Test directory-wide PII detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            user_file = Path(tmpdir) / "models" / "user.py"
            user_file.parent.mkdir(parents=True)
            user_file.write_text(
                """
class User:
    email: str
    ssn: str
"""
            )
            order_file = Path(tmpdir) / "models" / "order.py"
            order_file.write_text(
                """
class Order:
    order_id: int
    total: float
"""
            )

            fields = await detector.detect_in_directory(tmpdir)
            assert len(fields) >= 2
            # Should find email and SSN from user.py
            assert any(f.pii_category == PIICategory.EMAIL for f in fields)
            assert any(f.pii_category == PIICategory.SSN for f in fields)
