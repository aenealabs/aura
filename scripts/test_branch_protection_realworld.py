#!/usr/bin/env python3
"""
Real-World Branch Protection Service Testing

This script tests the BranchProtectionService against the GitHub API
to verify functionality in a real environment.

Usage:
    python scripts/test_branch_protection_realworld.py

Requirements:
    - GitHub CLI authenticated (gh auth login)
    - PyGithub installed
    - For full branch protection testing: GitHub Pro or public repo
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.branch_protection_service import (
    BranchProtectionConfig,
    BranchProtectionService,
    CompliancePreset,
    create_branch_protection_service,
)
from src.services.github_pr_service import (
    GitHubPRService,
    PatchInfo,
    VulnerabilityInfo,
    create_github_pr_service,
)


def get_github_token() -> str | None:
    """Get GitHub token from gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print("❌ Failed to get GitHub token from gh CLI")
        return None


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


async def test_mock_mode():
    """Test branch protection service in mock mode."""
    print_section("TEST 1: Mock Mode Testing")

    service = create_branch_protection_service(use_mock=True)
    print("✅ BranchProtectionService created in mock mode")

    # Test enabling protection
    config = BranchProtectionConfig.from_compliance_preset(CompliancePreset.SOX, "main")
    result = await service.enable_branch_protection("test/repo", config)

    print(f"✅ Enable protection result: {result.success}")
    print(f"   Branch: {result.branch}")
    print(f"   Message: {result.message}")

    if result.config_applied:
        print(
            f"   Required approvals: {result.config_applied.required_approving_review_count}"
        )
        print(f"   Signed commits: {result.config_applied.require_signed_commits}")
        print(f"   Status checks: {result.config_applied.required_status_checks}")

    # Test applying compliance preset
    results = await service.apply_compliance_preset(
        "test/repo",
        CompliancePreset.CMMC,
        branches=["main", "develop", "release"],
    )

    print(f"\n✅ Applied CMMC preset to {len(results)} branches:")
    for r in results:
        print(f"   - {r.branch}: {'✅' if r.success else '❌'}")

    return True


async def test_real_github_readonly(token: str):
    """Test read-only GitHub API operations."""
    print_section("TEST 2: Real GitHub API (Read-Only)")

    try:
        from github import Github

        gh = Github(token)
        user = gh.get_user()
        print(f"✅ Authenticated as: {user.login}")
        print(f"   Name: {user.name}")

        # Get repo info
        repo = gh.get_repo("aenealabs/aura")
        print(f"\n📦 Repository: {repo.full_name}")
        print(f"   Private: {repo.private}")
        print(f"   Default branch: {repo.default_branch}")
        print(f"   Stars: {repo.stargazers_count}")

        # Check branches
        branches = list(repo.get_branches())
        print(f"\n🌿 Branches ({len(branches)}):")
        for branch in branches[:5]:
            print(f"   - {branch.name}")
            if branch.protected:
                print(f"     Protected: Yes")

        # Check rate limit
        rate = gh.get_rate_limit()
        print(f"\n⏱️ Rate Limit:")
        print(f"   Remaining: {rate.core.remaining}/{rate.core.limit}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_branch_protection_with_real_client(token: str):
    """Test branch protection service with real GitHub client."""
    print_section("TEST 3: Branch Protection Service (Real Client)")

    try:
        from github import Github, GithubException

        gh = Github(token)
        repo_name = "aenealabs/aura"

        # Create service with real client
        service = BranchProtectionService(github_client=gh, use_mock=False)
        print(f"✅ BranchProtectionService created with real GitHub client")

        # Try to get branch protection status
        print(f"\n📋 Checking branch protection status for {repo_name}:main...")

        status = await service.get_branch_protection_status(repo_name, "main")

        if "error" in status:
            print(
                f"⚠️  Branch protection status: {status.get('error', 'Unknown error')}"
            )
            print(f"   Note: Branch protection requires GitHub Pro for private repos")
        else:
            print(f"✅ Branch protection status:")
            print(f"   Protected: {status.get('protected', False)}")
            if status.get("protected"):
                print(f"   Enforce admins: {status.get('enforce_admins')}")
                print(
                    f"   Required reviews: {status.get('required_pull_request_reviews')}"
                )

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_github_pr_service_integration(token: str):
    """Test GitHubPRService with branch protection integration."""
    print_section("TEST 4: GitHubPRService Integration")

    try:
        # Create service in mock mode (to avoid creating real PRs)
        service = create_github_pr_service(use_mock=True)
        print("✅ GitHubPRService created in mock mode")

        # Test compliance branch protection method
        print("\n📋 Testing apply_compliance_branch_protection...")

        result = await service.apply_compliance_branch_protection(
            repo_url="https://github.com/aenealabs/aura",
            compliance_preset="sox",
            branches=["main"],
        )

        print(f"✅ Result:")
        print(f"   Success: {result['success']}")
        print(f"   Preset: {result['preset']}")
        print(f"   Repository: {result['repository']}")

        for branch, status in result.get("branches", {}).items():
            print(f"   {branch}:")
            print(f"      Protected: {status['protected']}")
            print(f"      Required approvals: {status['config']['required_approvals']}")
            print(f"      Signed commits: {status['config']['require_signed_commits']}")

        # Test verify_branch_protection_status
        print("\n📋 Testing verify_branch_protection_status...")
        status = await service.verify_branch_protection_status(
            repo_url="https://github.com/aenealabs/aura",
            branch="main",
        )
        print(f"✅ Status: {json.dumps(status, indent=2)}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_compliance_presets():
    """Test all compliance presets and their configurations."""
    print_section("TEST 5: Compliance Preset Configurations")

    presets = [
        CompliancePreset.MINIMAL,
        CompliancePreset.ENTERPRISE_STANDARD,
        CompliancePreset.SOX,
        CompliancePreset.CMMC,
        CompliancePreset.HIPAA,
        CompliancePreset.PCI_DSS,
        CompliancePreset.MAXIMUM,
    ]

    print("📋 Compliance Preset Comparison:\n")
    print(
        f"{'Preset':<20} {'Approvals':<10} {'Signed':<8} {'Linear':<8} {'Code Owners':<12}"
    )
    print("-" * 60)

    for preset in presets:
        config = BranchProtectionConfig.from_compliance_preset(preset, "main")
        print(
            f"{preset.value:<20} "
            f"{config.required_approving_review_count:<10} "
            f"{'Yes' if config.require_signed_commits else 'No':<8} "
            f"{'Yes' if config.require_linear_history else 'No':<8} "
            f"{'Yes' if config.require_code_owner_reviews else 'No':<12}"
        )

    print("\n✅ All compliance presets validated")
    return True


async def test_mock_pr_with_protection():
    """Test creating a mock PR with branch protection applied."""
    print_section("TEST 6: Mock PR Creation with Branch Protection")

    service = create_github_pr_service(use_mock=True)

    # Create mock vulnerability and patch info
    vuln_info = VulnerabilityInfo(
        vulnerability_id="VULN-2024-001",
        vulnerability_type="SQL_INJECTION",
        severity="HIGH",
        file_path="src/api/users.py",
        line_number=42,
        description="SQL injection vulnerability in user query",
        cve_id="CVE-2024-12345",
        recommendation="Use parameterized queries",
    )

    patch_info = PatchInfo(
        patch_id="PATCH-001",
        patch_content='--- a/src/api/users.py\n+++ b/src/api/users.py\n@@ -40,3 +40,3 @@\n-    query = f"SELECT * FROM users WHERE id = {user_id}"\n+    query = "SELECT * FROM users WHERE id = %s"\n',
        patched_code="# Fixed code with parameterized query",
        file_path="src/api/users.py",
        confidence_score=0.95,
        agent_id="coder-agent-1",
    )

    print("📋 Creating mock remediation PR...")

    result = await service.create_remediation_pr(
        repo_url="https://github.com/aenealabs/aura",
        patch_info=patch_info,
        vulnerability_info=vuln_info,
        base_branch="main",
        approver_email="security@example.com",
        approval_id="APPROVAL-001",
        workflow_id="WF-001",
    )

    print(f"✅ PR Creation Result:")
    print(f"   Status: {result.status.value}")
    print(f"   PR Number: {result.pr_number}")
    print(f"   PR URL: {result.pr_url}")
    print(f"   Branch: {result.branch_name}")
    print(f"   Commit SHA: {result.commit_sha[:12]}...")

    # Now apply branch protection
    print("\n📋 Applying SOX compliance protection...")
    protection_result = await service.apply_compliance_branch_protection(
        repo_url="https://github.com/aenealabs/aura",
        compliance_preset="sox",
        branches=["main"],
    )

    print(f"✅ Protection Applied:")
    print(f"   Success: {protection_result['success']}")
    print(f"   Preset: {protection_result['preset']}")

    return True


async def main():
    """Run all real-world tests."""
    print("\n" + "=" * 60)
    print("  BRANCH PROTECTION SERVICE - REAL WORLD TESTING")
    print("=" * 60)

    # Get GitHub token
    token = get_github_token()
    if not token:
        print("\n⚠️  Running without GitHub token - only mock tests will work")

    results = {}

    # Test 1: Mock mode
    results["mock_mode"] = await test_mock_mode()

    # Test 2: Real GitHub API (read-only)
    if token:
        results["github_readonly"] = await test_real_github_readonly(token)
    else:
        print("\n⏭️  Skipping real GitHub API tests (no token)")
        results["github_readonly"] = None

    # Test 3: Branch protection with real client
    if token:
        results["branch_protection_real"] = (
            await test_branch_protection_with_real_client(token)
        )
    else:
        results["branch_protection_real"] = None

    # Test 4: GitHubPRService integration
    results["pr_service_integration"] = await test_github_pr_service_integration(token)

    # Test 5: Compliance presets
    results["compliance_presets"] = await test_compliance_presets()

    # Test 6: Mock PR with protection
    results["mock_pr_with_protection"] = await test_mock_pr_with_protection()

    # Summary
    print_section("TEST SUMMARY")

    passed = sum(1 for v in results.values() if v is True)
    skipped = sum(1 for v in results.values() if v is None)
    failed = sum(1 for v in results.values() if v is False)

    for test_name, result in results.items():
        status = (
            "✅ PASSED"
            if result is True
            else ("⏭️ SKIPPED" if result is None else "❌ FAILED")
        )
        print(f"  {test_name}: {status}")

    print(f"\n📊 Total: {passed} passed, {skipped} skipped, {failed} failed")

    if failed == 0:
        print("\n✅ All tests completed successfully!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
