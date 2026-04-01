"""
Tests for VS Code Extension API Endpoints

Tests the /api/v1/extension endpoints for vulnerability scanning,
findings retrieval, patch generation, and HITL approval workflow.
"""

import os

import pytest

# Set AWS region before any boto3 imports
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Create isolated test app with only extension endpoints
from src.api.extension_endpoints import (
    PatchStatus,
    ScanStatus,
    _findings,
    _patches,
    _scans,
)
from src.api.extension_endpoints import router as extension_router

# Create isolated test app with only extension endpoints
test_app = FastAPI()
test_app.include_router(extension_router)


@pytest.fixture
def client():
    """Create test client with isolated app."""
    return TestClient(test_app)


@pytest.fixture(autouse=True)
def clear_storage():
    """Clear in-memory storage before each test."""
    _scans.clear()
    _findings.clear()
    _patches.clear()
    yield
    _scans.clear()
    _findings.clear()
    _patches.clear()


class TestGetExtensionConfig:
    """Tests for GET /api/v1/extension/config."""

    def test_returns_config(self, client):
        """Test that config endpoint returns expected structure."""
        response = client.get("/api/v1/extension/config")

        assert response.status_code == 200
        data = response.json()

        assert data["scan_on_save"] is True
        assert data["auto_suggest_patches"] is True
        assert data["severity_threshold"] == "low"
        assert "python" in data["supported_languages"]
        assert data["api_version"] == "2.0.0"
        assert "realtime_scan" in data["features"]
        assert "patch_generation" in data["features"]
        assert "hitl_integration" in data["features"]

    def test_supported_languages(self, client):
        """Test that all expected languages are supported."""
        response = client.get("/api/v1/extension/config")
        data = response.json()

        expected_languages = [
            "python",
            "javascript",
            "typescript",
            "java",
            "go",
            "rust",
        ]
        for lang in expected_languages:
            assert lang in data["supported_languages"]


class TestScanFile:
    """Tests for POST /api/v1/extension/scan."""

    def test_scan_file_success(self, client):
        """Test successful file scan."""
        response = client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "test.py",
                "file_content": "print('hello')",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "scan_id" in data
        assert data["status"] == "completed"
        assert isinstance(data["findings_count"], int)
        assert "message" in data

    def test_scan_detects_eval(self, client):
        """Test that scan detects dangerous eval() usage."""
        response = client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "vulnerable.py",
                "file_content": "result = eval(user_input)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["findings_count"] >= 1

        # Check findings were stored
        findings = _findings.get("vulnerable.py", [])
        assert len(findings) >= 1
        assert any(f.title == "Dangerous eval() usage" for f in findings)

    def test_scan_detects_exec(self, client):
        """Test that scan detects dangerous exec() usage."""
        response = client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "exec_vuln.py",
                "file_content": "exec(code_string)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        assert response.status_code == 200
        findings = _findings.get("exec_vuln.py", [])
        assert any(f.title == "Dangerous exec() usage" for f in findings)

    def test_scan_detects_subprocess(self, client):
        """Test that scan detects potential command injection."""
        response = client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "cmd.py",
                "file_content": "subprocess.call(cmd, shell=True)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        assert response.status_code == 200
        findings = _findings.get("cmd.py", [])
        assert any("command injection" in f.title.lower() for f in findings)

    def test_scan_detects_hardcoded_password(self, client):
        """Test that scan detects hardcoded credentials."""
        response = client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "creds.py",
                "file_content": 'password = "secret123"',
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        assert response.status_code == 200
        findings = _findings.get("creds.py", [])
        assert any(
            "credential" in f.title.lower() or "password" in f.title.lower()
            for f in findings
        )

    def test_scan_detects_todo(self, client):
        """Test that scan detects TODO comments."""
        response = client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "todo.py",
                "file_content": "# TODO: fix this later",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        assert response.status_code == 200
        findings = _findings.get("todo.py", [])
        assert any("todo" in f.title.lower() for f in findings)

    def test_scan_stores_metadata(self, client):
        """Test that scan stores scan metadata."""
        response = client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "test.py",
                "file_content": "x = 1",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        data = response.json()
        scan_id = data["scan_id"]

        assert scan_id in _scans
        assert _scans[scan_id]["file_path"] == "test.py"
        assert _scans[scan_id]["status"] == ScanStatus.COMPLETED


class TestGetFindings:
    """Tests for GET /api/v1/extension/findings/{file_path}."""

    def test_get_findings_for_file(self, client):
        """Test getting findings for a specific file."""
        # First scan a file
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "test.py",
                "file_content": "result = eval(user_input)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        # Then get findings
        response = client.get("/api/v1/extension/findings/test.py")

        assert response.status_code == 200
        data = response.json()

        assert data["file_path"] == "test.py"
        assert isinstance(data["findings"], list)
        assert len(data["findings"]) >= 1
        assert "scan_timestamp" in data
        assert "scan_duration_ms" in data

    def test_get_findings_empty_file(self, client):
        """Test getting findings for a file with no issues."""
        response = client.get("/api/v1/extension/findings/nonexistent.py")

        assert response.status_code == 200
        data = response.json()

        assert data["file_path"] == "nonexistent.py"
        assert data["findings"] == []

    def test_finding_structure(self, client):
        """Test that findings have all required fields."""
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "struct.py",
                "file_content": "eval(x)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        response = client.get("/api/v1/extension/findings/struct.py")
        data = response.json()
        finding = data["findings"][0]

        assert "id" in finding
        assert "file_path" in finding
        assert "line_start" in finding
        assert "line_end" in finding
        assert "severity" in finding
        assert "category" in finding
        assert "title" in finding
        assert "description" in finding


class TestListAllFindings:
    """Tests for GET /api/v1/extension/findings."""

    def test_list_all_findings(self, client):
        """Test listing all findings across files."""
        # Scan multiple files
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "file1.py",
                "file_content": "eval(x)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "file2.py",
                "file_content": "exec(y)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        response = client.get("/api/v1/extension/findings")

        assert response.status_code == 200
        data = response.json()

        assert "total" in data
        assert "findings" in data
        assert data["total"] >= 2

    def test_filter_by_severity(self, client):
        """Test filtering findings by severity."""
        # Scan file with mixed severity findings
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "mixed.py",
                "file_content": "eval(x)\n# TODO: fix",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        # Filter for critical only
        response = client.get("/api/v1/extension/findings?severity=critical")

        assert response.status_code == 200
        data = response.json()

        for finding in data["findings"]:
            assert finding["severity"] == "critical"

    def test_filter_by_category(self, client):
        """Test filtering findings by category."""
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "inject.py",
                "file_content": "eval(x)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        response = client.get("/api/v1/extension/findings?category=injection")

        assert response.status_code == 200
        data = response.json()

        for finding in data["findings"]:
            assert finding["category"] == "injection"


class TestGeneratePatch:
    """Tests for POST /api/v1/extension/patches."""

    def test_generate_patch_success(self, client):
        """Test successful patch generation."""
        # First scan to create a finding
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "vuln.py",
                "file_content": "result = eval(user_input)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        findings = _findings.get("vuln.py", [])
        assert len(findings) >= 1
        finding_id = findings[0].id

        # Generate patch
        response = client.post(
            "/api/v1/extension/patches",
            json={
                "finding_id": finding_id,
                "file_path": "vuln.py",
                "file_content": "result = eval(user_input)",
                "context_lines": 10,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "patch" in data
        assert "message" in data
        assert data["patch"]["finding_id"] == finding_id
        assert data["patch"]["status"] == "ready"
        assert "diff" in data["patch"]
        assert data["patch"]["confidence"] > 0

    def test_generate_patch_not_found(self, client):
        """Test patch generation with invalid finding ID."""
        response = client.post(
            "/api/v1/extension/patches",
            json={
                "finding_id": "nonexistent",
                "file_path": "test.py",
                "file_content": "x = 1",
                "context_lines": 10,
            },
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_patch_updates_finding(self, client):
        """Test that patch generation updates the finding."""
        # Scan to create finding
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "update.py",
                "file_content": "eval(x)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        finding = _findings["update.py"][0]
        assert not finding.has_patch

        # Generate patch
        client.post(
            "/api/v1/extension/patches",
            json={
                "finding_id": finding.id,
                "file_path": "update.py",
                "file_content": "eval(x)",
                "context_lines": 10,
            },
        )

        # Check finding was updated
        assert finding.has_patch
        assert finding.patch_id is not None


class TestGetPatch:
    """Tests for GET /api/v1/extension/patches/{patch_id}."""

    def test_get_patch_success(self, client):
        """Test getting patch details."""
        # Create a finding and patch
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "get.py",
                "file_content": "eval(x)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        finding_id = _findings["get.py"][0].id
        patch_response = client.post(
            "/api/v1/extension/patches",
            json={
                "finding_id": finding_id,
                "file_path": "get.py",
                "file_content": "eval(x)",
                "context_lines": 10,
            },
        )

        patch_id = patch_response.json()["patch"]["id"]

        # Get patch details
        response = client.get(f"/api/v1/extension/patches/{patch_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == patch_id
        assert data["finding_id"] == finding_id
        assert "original_code" in data
        assert "patched_code" in data
        assert "diff" in data

    def test_get_patch_not_found(self, client):
        """Test getting non-existent patch."""
        response = client.get("/api/v1/extension/patches/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestApplyPatch:
    """Tests for POST /api/v1/extension/patches/{patch_id}/apply."""

    def test_apply_patch_success(self, client):
        """Test successful patch application."""
        # Create finding and patch
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "apply.py",
                "file_content": "# TODO: fix",  # Low severity - no approval needed
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        finding = _findings["apply.py"][0]
        patch_response = client.post(
            "/api/v1/extension/patches",
            json={
                "finding_id": finding.id,
                "file_path": "apply.py",
                "file_content": "# TODO: fix",
                "context_lines": 10,
            },
        )

        patch_id = patch_response.json()["patch"]["id"]

        # Apply patch
        response = client.post(
            f"/api/v1/extension/patches/{patch_id}/apply",
            json={"patch_id": patch_id, "confirm": True},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["patch_id"] == patch_id
        assert "applied" in data["message"].lower()

    def test_apply_patch_requires_confirmation(self, client):
        """Test that patch application requires confirmation."""
        # Create finding and patch
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "confirm.py",
                "file_content": "# TODO: fix",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        finding = _findings["confirm.py"][0]
        patch_response = client.post(
            "/api/v1/extension/patches",
            json={
                "finding_id": finding.id,
                "file_path": "confirm.py",
                "file_content": "# TODO: fix",
                "context_lines": 10,
            },
        )

        patch_id = patch_response.json()["patch"]["id"]

        # Try to apply without confirmation
        response = client.post(
            f"/api/v1/extension/patches/{patch_id}/apply",
            json={"patch_id": patch_id, "confirm": False},
        )

        assert response.status_code == 400
        assert "confirm" in response.json()["detail"].lower()

    def test_apply_patch_requires_approval_for_critical(self, client):
        """Test that critical patches require HITL approval."""
        # Create critical finding
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "critical.py",
                "file_content": "eval(x)",  # Critical severity
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        finding = _findings["critical.py"][0]
        patch_response = client.post(
            "/api/v1/extension/patches",
            json={
                "finding_id": finding.id,
                "file_path": "critical.py",
                "file_content": "eval(x)",
                "context_lines": 10,
            },
        )

        patch_id = patch_response.json()["patch"]["id"]
        patch = _patches[patch_id]

        # Verify patch requires approval
        assert patch.requires_approval is True
        assert patch.status == PatchStatus.READY  # Not approved yet

        # Manually set to not approved to test rejection
        patch.status = PatchStatus.PENDING

        # Try to apply without approval
        response = client.post(
            f"/api/v1/extension/patches/{patch_id}/apply",
            json={"patch_id": patch_id, "confirm": True},
        )

        assert response.status_code == 403
        assert (
            "approval" in response.json()["detail"].lower()
            or "status" in response.json()["detail"].lower()
        )

    def test_apply_patch_not_found(self, client):
        """Test applying non-existent patch."""
        response = client.post(
            "/api/v1/extension/patches/nonexistent/apply",
            json={"patch_id": "nonexistent", "confirm": True},
        )

        assert response.status_code == 404


class TestApprovalStatus:
    """Tests for GET /api/v1/extension/approvals/{approval_id}."""

    def test_get_approval_status(self, client):
        """Test getting approval status."""
        # Create critical finding with approval
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "approval.py",
                "file_content": "eval(x)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        finding = _findings["approval.py"][0]
        patch_response = client.post(
            "/api/v1/extension/patches",
            json={
                "finding_id": finding.id,
                "file_path": "approval.py",
                "file_content": "eval(x)",
                "context_lines": 10,
            },
        )

        patch = patch_response.json()["patch"]
        approval_id = patch.get("approval_id")

        if approval_id:
            response = client.get(f"/api/v1/extension/approvals/{approval_id}")

            assert response.status_code == 200
            data = response.json()

            assert data["patch_id"] == patch["id"]
            assert data["approval_id"] == approval_id
            assert "status" in data

    def test_get_approval_not_found(self, client):
        """Test getting non-existent approval."""
        response = client.get("/api/v1/extension/approvals/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestFindingMetadata:
    """Tests for finding metadata (CWE, OWASP)."""

    def test_eval_has_cwe_id(self, client):
        """Test that eval finding has CWE ID."""
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "cwe.py",
                "file_content": "eval(x)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        findings = _findings.get("cwe.py", [])
        eval_finding = next((f for f in findings if "eval" in f.title.lower()), None)

        assert eval_finding is not None
        assert eval_finding.cwe_id == "CWE-95"

    def test_eval_has_owasp_category(self, client):
        """Test that eval finding has OWASP category."""
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "owasp.py",
                "file_content": "eval(x)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        findings = _findings.get("owasp.py", [])
        eval_finding = next((f for f in findings if "eval" in f.title.lower()), None)

        assert eval_finding is not None
        assert eval_finding.owasp_category == "A03:2021"


class TestPatchGeneration:
    """Tests for patch content generation."""

    def test_eval_patch_uses_literal_eval(self, client):
        """Test that eval patch suggests ast.literal_eval."""
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "eval_patch.py",
                "file_content": "result = eval(data)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        finding = _findings["eval_patch.py"][0]
        patch_response = client.post(
            "/api/v1/extension/patches",
            json={
                "finding_id": finding.id,
                "file_path": "eval_patch.py",
                "file_content": "result = eval(data)",
                "context_lines": 10,
            },
        )

        patch = patch_response.json()["patch"]
        assert "literal_eval" in patch["patched_code"]

    def test_subprocess_patch_removes_shell_true(self, client):
        """Test that subprocess patch changes shell=True to False."""
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "subprocess_patch.py",
                "file_content": "subprocess.call(cmd, shell=True)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        finding = next(
            (
                f
                for f in _findings["subprocess_patch.py"]
                if "command" in f.title.lower()
            ),
            None,
        )

        if finding:
            patch_response = client.post(
                "/api/v1/extension/patches",
                json={
                    "finding_id": finding.id,
                    "file_path": "subprocess_patch.py",
                    "file_content": "subprocess.call(cmd, shell=True)",
                    "context_lines": 10,
                },
            )

            patch = patch_response.json()["patch"]
            assert "shell=False" in patch["patched_code"]

    def test_patch_has_diff_format(self, client):
        """Test that patch includes proper diff format."""
        client.post(
            "/api/v1/extension/scan",
            json={
                "file_path": "diff.py",
                "file_content": "eval(x)",
                "language": "python",
                "workspace_path": "/workspace",
            },
        )

        finding = _findings["diff.py"][0]
        patch_response = client.post(
            "/api/v1/extension/patches",
            json={
                "finding_id": finding.id,
                "file_path": "diff.py",
                "file_content": "eval(x)",
                "context_lines": 10,
            },
        )

        patch = patch_response.json()["patch"]
        diff = patch["diff"]

        assert "---" in diff
        assert "+++" in diff
        assert "@@" in diff
        assert "-" in diff  # Removed line
        assert "+" in diff  # Added line
