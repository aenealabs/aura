"""Tests that sandbox isolation levels are enforced or refused, never faked.

`NetworkIsolationLevel` declares four levels. Only some are enforced by the
live provisioning path. Before this, requesting an unenforced level returned
success and produced container-level networking -- the `isolation_level`
argument reached exactly one place, an `ISOLATION_LEVEL` environment variable
on the container, while `networkConfiguration` stayed identical across levels.

A sandbox whose boundary is weaker than its caller believes is worse than no
sandbox, because the belief is what the caller acts on.
"""

import pytest

from src.services.sandbox_network_service import (
    ENFORCED_ISOLATION_LEVELS,
    DnsmasqConfig,
    FargateSandboxOrchestrator,
    NetworkIsolationLevel,
    SandboxNetwork,
    SandboxNetworkOrchestrator,
    SandboxNetworkStatus,
    UnsupportedIsolationLevelError,
)

pytestmark = pytest.mark.unit


class TestEnforcedIsolationLevels:
    """The declared set and the enforced set are deliberately different."""

    def test_enforced_is_a_strict_subset_of_declared(self):
        declared = set(NetworkIsolationLevel)
        assert ENFORCED_ISOLATION_LEVELS < declared

    def test_container_is_enforced(self):
        assert NetworkIsolationLevel.CONTAINER in ENFORCED_ISOLATION_LEVELS

    def test_vpc_and_full_are_not_claimed_as_enforced(self):
        """Guards against someone adding these without implementing them."""
        assert NetworkIsolationLevel.VPC not in ENFORCED_ISOLATION_LEVELS
        assert NetworkIsolationLevel.FULL not in ENFORCED_ISOLATION_LEVELS


class TestFargateRefusesUnenforcedLevels:
    """The live path refuses rather than silently downgrading."""

    @pytest.fixture
    def orchestrator(self):
        return FargateSandboxOrchestrator(environment="dev")

    @pytest.mark.parametrize("level", ["vpc", "full"])
    async def test_unenforced_level_raises(self, orchestrator, level):
        with pytest.raises(UnsupportedIsolationLevelError) as exc:
            await orchestrator.create_sandbox(
                sandbox_id="s1",
                patch_id="p1",
                test_suite="t",
                isolation_level=level,
            )

        message = str(exc.value)
        # The error must say what actually happens, not just "unsupported".
        assert "not enforced" in message
        assert "container" in message

    async def test_unknown_level_raises_value_error(self, orchestrator):
        with pytest.raises(ValueError, match="Unknown isolation level"):
            await orchestrator.create_sandbox(
                sandbox_id="s1",
                patch_id="p1",
                test_suite="t",
                isolation_level="banana",
            )

    def test_enforced_levels_pass_validation(self, orchestrator):
        """Validation itself must not reject the levels that do work."""
        for level in ENFORCED_ISOLATION_LEVELS:
            orchestrator._require_enforced_isolation(level.value)

    def test_validation_happens_before_any_aws_call(self, orchestrator):
        """The refusal must not depend on reaching ECS.

        Validation is a pure check, so it holds without credentials -- which is
        the environment where this test runs.
        """
        with pytest.raises(UnsupportedIsolationLevelError):
            orchestrator._require_enforced_isolation("full")


class TestSimulationIsLabelled:
    """The simulation harness must not be mistakable for real provisioning."""

    @pytest.fixture
    def orchestrator(self):
        return SandboxNetworkOrchestrator()

    def test_default_record_is_not_marked_simulated(self):
        network = SandboxNetwork(
            sandbox_id="s1",
            status=SandboxNetworkStatus.PENDING,
            isolation_level=NetworkIsolationLevel.CONTAINER,
            dnsmasq_config=DnsmasqConfig(),
        )
        assert network.simulated is False
        assert network.to_dict()["simulated"] is False

    @pytest.mark.parametrize(
        "level",
        [
            NetworkIsolationLevel.CONTAINER,
            NetworkIsolationLevel.VPC,
            NetworkIsolationLevel.FULL,
            NetworkIsolationLevel.NONE,
        ],
        ids=lambda lv: lv.value,
    )
    async def test_every_simulated_provision_is_flagged(self, orchestrator, level):
        """No level of this orchestrator provisions anything real."""
        network = await orchestrator.provision_sandbox_network(
            sandbox_id=f"sim-{level.value}",
            isolation_level=level,
        )

        assert network.simulated is True, (
            f"{level.value} produced an unflagged record -- a consumer would "
            "read fabricated identifiers as real AWS resources"
        )
        assert network.to_dict()["simulated"] is True

    async def test_fabricated_ids_are_visibly_fake(self, orchestrator):
        network = await orchestrator.provision_sandbox_network(
            sandbox_id="sim-vpc",
            isolation_level=NetworkIsolationLevel.VPC,
        )
        assert network.simulated is True
        assert "simulated" in (network.vpc_id or "")

    def test_class_docstring_states_it_is_a_simulation(self):
        """Cheap guard against the warning being edited away silently."""
        doc = SandboxNetworkOrchestrator.__doc__ or ""
        assert "SIMULATION" in doc.upper()
        assert "FargateSandboxOrchestrator" in doc


class TestSettingsDefaultIsEnforceable:
    """The operator-facing default must name a level that actually works."""

    def test_persistence_default_is_enforced(self):
        from src.services.settings_persistence_service import DEFAULT_PLATFORM_SETTINGS

        level = DEFAULT_PLATFORM_SETTINGS["security"]["sandbox_isolation_level"]
        assert NetworkIsolationLevel(level) in ENFORCED_ISOLATION_LEVELS

    def test_api_default_is_enforced(self):
        from src.api.settings_endpoints import SecuritySettingsModel

        level = SecuritySettingsModel().sandbox_isolation_level
        assert NetworkIsolationLevel(level) in ENFORCED_ISOLATION_LEVELS
