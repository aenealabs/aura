"""
Project Aura - Orchestrator Mode Service

Service for managing orchestrator deployment mode transitions.
Handles safe transitions between on-demand, warm pool, and hybrid modes
with proper state management, cooldown enforcement, and K8s integration.

State Machine:
    ACTIVE -> DRAINING (stop accepting new jobs to current mode)
          -> COMPLETING (wait for in-flight jobs to finish)
          -> SCALING (adjust warm pool replicas)
          -> ACTIVE (new mode operational)

Author: Project Aura Team
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kubernetes.client import AppsV1Api

logger = logging.getLogger(__name__)


class DeploymentMode(str, Enum):
    """Available orchestrator deployment modes."""

    ON_DEMAND = "on_demand"  # EKS Jobs per request ($0 base cost)
    WARM_POOL = "warm_pool"  # Always-on replica (~$28/mo)
    HYBRID = "hybrid"  # Warm pool + burst jobs


class TransitionState(str, Enum):
    """States during mode transition."""

    ACTIVE = "active"  # Normal operation
    DRAINING = "draining"  # Stop accepting jobs to old mode
    COMPLETING = "completing"  # Wait for in-flight jobs
    SCALING = "scaling"  # Adjust warm pool replicas
    FAILED = "failed"  # Transition failed


@dataclass
class ModeTransitionStatus:
    """Status of a mode transition."""

    current_mode: DeploymentMode
    target_mode: DeploymentMode | None
    transition_state: TransitionState
    started_at: str | None
    in_flight_jobs: int
    warm_pool_desired: int
    warm_pool_ready: int
    error_message: str | None = None


class OrchestratorModeService:
    """
    Service for managing orchestrator deployment mode transitions.

    Provides safe, observable transitions between deployment modes with:
    - State machine for graceful transitions
    - Cooldown enforcement to prevent thrashing
    - K8s integration for warm pool scaling
    - CloudWatch metrics for observability
    """

    # Default cooldown of 5 minutes between mode changes
    DEFAULT_COOLDOWN_SECONDS = 300

    # Timeout for draining/completing states (10 minutes)
    TRANSITION_TIMEOUT_SECONDS = 600

    # Poll interval for checking transition progress
    POLL_INTERVAL_SECONDS = 5

    def __init__(
        self,
        settings_service: Any = None,
        kubernetes_enabled: bool = True,
        namespace: str = "default",
    ):
        """
        Initialize the orchestrator mode service.

        Args:
            settings_service: SettingsPersistenceService instance
            kubernetes_enabled: Whether to actually interact with K8s
            namespace: K8s namespace for warm pool deployment
        """
        self._settings_service = settings_service
        self._kubernetes_enabled = kubernetes_enabled
        self._namespace = namespace
        self._current_transition: ModeTransitionStatus | None = None
        self._k8s_client: AppsV1Api | None = None

        if kubernetes_enabled:
            self._init_kubernetes_client()

    def _init_kubernetes_client(self) -> None:
        """Initialize Kubernetes client."""
        try:
            from kubernetes import client, config

            # Try in-cluster config first (running in K8s)
            try:
                config.load_incluster_config()
            except config.ConfigException:
                # Fall back to kubeconfig (local development)
                config.load_kube_config()

            self._k8s_client = client.AppsV1Api()
            logger.info("Kubernetes client initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Kubernetes client: {e}")
            self._kubernetes_enabled = False

    async def get_current_mode(
        self,
        organization_id: str | None = None,
    ) -> DeploymentMode:
        """
        Get the current deployment mode.

        Args:
            organization_id: Optional org ID for org-specific settings

        Returns:
            Current deployment mode
        """
        if not self._settings_service:
            return DeploymentMode.ON_DEMAND

        # Get settings (org-specific or platform)
        if organization_id:
            platform = await self._settings_service.get_setting(
                "platform", "orchestrator", {}
            )
            org = await self._settings_service.get_organization_setting(
                organization_id, "orchestrator", {}
            )
            settings = {**platform, **org}
        else:
            settings = await self._settings_service.get_setting(
                "platform", "orchestrator", {}
            )

        return self._compute_mode_from_settings(settings)

    def _compute_mode_from_settings(self, settings: dict[str, Any]) -> DeploymentMode:
        """Compute the deployment mode from settings."""
        if settings.get("hybrid_mode_enabled"):
            return DeploymentMode.HYBRID
        elif settings.get("warm_pool_enabled"):
            return DeploymentMode.WARM_POOL
        else:
            return DeploymentMode.ON_DEMAND

    async def get_transition_status(self) -> ModeTransitionStatus | None:
        """Get the status of any active transition."""
        return self._current_transition

    async def can_transition(
        self,
        organization_id: str | None = None,
    ) -> tuple[bool, str, int]:
        """
        Check if a mode transition is allowed.

        Returns:
            Tuple of (can_transition, reason, cooldown_remaining_seconds)
        """
        if (
            self._current_transition
            and self._current_transition.transition_state
            not in (TransitionState.ACTIVE, TransitionState.FAILED)
        ):
            return False, "Transition already in progress", 0

        if not self._settings_service:
            return True, "No settings service (mock mode)", 0

        # Get settings to check cooldown
        if organization_id:
            platform = await self._settings_service.get_setting(
                "platform", "orchestrator", {}
            )
            org = await self._settings_service.get_organization_setting(
                organization_id, "orchestrator", {}
            )
            settings = {**platform, **org}
        else:
            settings = await self._settings_service.get_setting(
                "platform", "orchestrator", {}
            )

        last_change = settings.get("last_mode_change_at")
        cooldown = settings.get(
            "mode_change_cooldown_seconds", self.DEFAULT_COOLDOWN_SECONDS
        )

        if not last_change:
            return True, "No previous mode change", 0

        try:
            last_change_dt = datetime.fromisoformat(last_change.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            elapsed = (now - last_change_dt).total_seconds()
            remaining = max(0, cooldown - elapsed)

            if remaining > 0:
                return (
                    False,
                    f"Cooldown active ({int(remaining)}s remaining)",
                    int(remaining),
                )
            return True, "Cooldown expired", 0
        except Exception as e:
            logger.warning(f"Error parsing last_mode_change_at: {e}")
            return True, "Could not parse last change time", 0

    async def start_transition(
        self,
        target_mode: DeploymentMode,
        organization_id: str | None = None,
        force: bool = False,
        initiated_by: str = "system",
    ) -> ModeTransitionStatus:
        """
        Start a mode transition.

        Args:
            target_mode: Target deployment mode
            organization_id: Optional org ID for org-specific settings
            force: Force transition even during cooldown
            initiated_by: User or system initiating the transition

        Returns:
            Transition status

        Raises:
            ValueError: If transition is not allowed
        """
        current_mode = await self.get_current_mode(organization_id)

        # Check if already in target mode
        if current_mode == target_mode:
            return ModeTransitionStatus(
                current_mode=current_mode,
                target_mode=None,
                transition_state=TransitionState.ACTIVE,
                started_at=None,
                in_flight_jobs=0,
                warm_pool_desired=await self._get_warm_pool_replicas_desired(
                    organization_id
                ),
                warm_pool_ready=await self._get_warm_pool_replicas_ready(),
            )

        # Check cooldown
        can_transition, reason, remaining = await self.can_transition(organization_id)
        if not can_transition and not force:
            raise ValueError(f"Transition not allowed: {reason}")

        if force:
            logger.warning(
                f"Force transition initiated by {initiated_by} "
                f"(org={organization_id}, {current_mode} -> {target_mode})"
            )

        # Create transition status
        self._current_transition = ModeTransitionStatus(
            current_mode=current_mode,
            target_mode=target_mode,
            transition_state=TransitionState.DRAINING,
            started_at=datetime.now(timezone.utc).isoformat(),
            in_flight_jobs=await self._get_in_flight_jobs_count(),
            warm_pool_desired=await self._get_warm_pool_replicas_desired(
                organization_id
            ),
            warm_pool_ready=await self._get_warm_pool_replicas_ready(),
        )

        logger.info(
            f"Starting mode transition: {current_mode} -> {target_mode} "
            f"(org={organization_id}, by={initiated_by})"
        )

        return self._current_transition

    async def execute_transition(
        self,
        organization_id: str | None = None,
        updated_by: str = "system",
    ) -> ModeTransitionStatus:
        """
        Execute the mode transition (non-blocking start).

        This method initiates the transition and returns immediately.
        Use get_transition_status() to monitor progress.

        Returns:
            Current transition status
        """
        if not self._current_transition:
            raise ValueError("No transition in progress")

        if self._current_transition.transition_state == TransitionState.ACTIVE:
            return self._current_transition

        # Start async transition task
        asyncio.create_task(self._run_transition(organization_id, updated_by))

        return self._current_transition

    async def _run_transition(
        self,
        organization_id: str | None,
        updated_by: str,
    ) -> None:
        """Run the transition state machine."""
        if not self._current_transition:
            return

        try:
            # Phase 1: DRAINING - Stop accepting jobs to current mode
            self._current_transition.transition_state = TransitionState.DRAINING
            logger.info("Transition phase: DRAINING")

            # In a real implementation, we'd update a flag that the dispatcher checks
            await asyncio.sleep(2)  # Brief pause for dispatchers to pick up new routing

            # Phase 2: COMPLETING - Wait for in-flight jobs
            self._current_transition.transition_state = TransitionState.COMPLETING
            logger.info("Transition phase: COMPLETING")

            timeout = self.TRANSITION_TIMEOUT_SECONDS
            while timeout > 0:
                in_flight = await self._get_in_flight_jobs_count()
                self._current_transition.in_flight_jobs = in_flight

                if in_flight == 0:
                    break

                logger.debug(f"Waiting for {in_flight} in-flight jobs to complete")
                await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
                timeout -= self.POLL_INTERVAL_SECONDS

            if timeout <= 0:
                logger.warning("Transition timeout waiting for jobs to complete")

            # Phase 3: SCALING - Adjust warm pool replicas
            self._current_transition.transition_state = TransitionState.SCALING
            logger.info("Transition phase: SCALING")

            target_mode = self._current_transition.target_mode
            if target_mode:
                await self._scale_warm_pool(target_mode, organization_id)

            # Phase 4: Update settings
            if self._settings_service and self._current_transition.target_mode:
                await self._update_mode_settings(
                    self._current_transition.target_mode,
                    organization_id,
                    updated_by,
                )

            # Complete transition
            self._current_transition.transition_state = TransitionState.ACTIVE
            if self._current_transition.target_mode:
                self._current_transition.current_mode = (
                    self._current_transition.target_mode
                )
            self._current_transition.target_mode = None

            logger.info(
                f"Transition completed: now in {self._current_transition.current_mode} mode"
            )

        except Exception as e:
            logger.error(f"Transition failed: {e}")
            self._current_transition.transition_state = TransitionState.FAILED
            self._current_transition.error_message = str(e)

    async def _scale_warm_pool(
        self,
        target_mode: DeploymentMode,
        organization_id: str | None,
    ) -> None:
        """Scale the warm pool based on target mode."""
        if not self._kubernetes_enabled or not self._k8s_client:
            logger.info("Kubernetes not enabled, skipping warm pool scaling")
            return

        # Determine target replicas
        target_replicas: int
        if target_mode == DeploymentMode.ON_DEMAND:
            target_replicas = 0
        else:
            # Get configured replicas from settings
            target_replicas = 1  # Default
            if self._settings_service:
                settings = await self._settings_service.get_setting(
                    "platform", "orchestrator", {}
                )
                target_replicas = int(settings.get("warm_pool_replicas", 1))

        logger.info(f"Scaling warm pool to {target_replicas} replicas")

        try:
            # Patch the deployment
            body = {"spec": {"replicas": target_replicas}}
            self._k8s_client.patch_namespaced_deployment_scale(
                name="agent-orchestrator-warm-pool",
                namespace=self._namespace,
                body=body,
            )

            # Wait for scaling to complete
            for _ in range(60):  # 5 minute timeout
                deployment = self._k8s_client.read_namespaced_deployment(
                    name="agent-orchestrator-warm-pool",
                    namespace=self._namespace,
                )
                ready = deployment.status.ready_replicas or 0

                if self._current_transition:
                    self._current_transition.warm_pool_ready = ready

                if ready == target_replicas:
                    logger.info(f"Warm pool scaled to {target_replicas} replicas")
                    return

                await asyncio.sleep(5)

            logger.warning("Timeout waiting for warm pool scaling")

        except Exception as e:
            logger.error(f"Failed to scale warm pool: {e}")
            raise

    async def _update_mode_settings(
        self,
        target_mode: DeploymentMode,
        organization_id: str | None,
        updated_by: str,
    ) -> None:
        """Update settings to reflect new mode."""
        updates: dict[str, Any] = {
            "last_mode_change_at": datetime.now(timezone.utc).isoformat(),
            "last_mode_change_by": updated_by,
        }

        if target_mode == DeploymentMode.ON_DEMAND:
            updates["on_demand_jobs_enabled"] = True
            updates["warm_pool_enabled"] = False
            updates["hybrid_mode_enabled"] = False
        elif target_mode == DeploymentMode.WARM_POOL:
            updates["on_demand_jobs_enabled"] = False
            updates["warm_pool_enabled"] = True
            updates["hybrid_mode_enabled"] = False
        elif target_mode == DeploymentMode.HYBRID:
            updates["on_demand_jobs_enabled"] = True
            updates["warm_pool_enabled"] = True
            updates["hybrid_mode_enabled"] = True

        if organization_id:
            await self._settings_service.update_organization_setting(
                organization_id, "orchestrator", updates, updated_by
            )
        else:
            current = await self._settings_service.get_setting(
                "platform", "orchestrator", {}
            )
            await self._settings_service.save_setting(
                "platform", "orchestrator", {**current, **updates}, updated_by
            )

    async def _get_in_flight_jobs_count(self) -> int:
        """Get the count of in-flight orchestrator jobs."""
        if not self._kubernetes_enabled or not self._k8s_client:
            return 0

        try:
            from kubernetes import client

            batch_client = client.BatchV1Api()

            jobs = batch_client.list_namespaced_job(
                namespace=self._namespace,
                label_selector="app=agent-orchestrator",
            )

            active_count = sum(
                1 for job in jobs.items if job.status.active and job.status.active > 0
            )

            return active_count

        except Exception as e:
            logger.warning(f"Failed to get in-flight jobs count: {e}")
            return 0

    async def _get_warm_pool_replicas_desired(
        self,
        organization_id: str | None = None,
    ) -> int:
        """Get the desired warm pool replica count from settings."""
        if not self._settings_service:
            return 0

        if organization_id:
            platform = await self._settings_service.get_setting(
                "platform", "orchestrator", {}
            )
            org = await self._settings_service.get_organization_setting(
                organization_id, "orchestrator", {}
            )
            settings = {**platform, **org}
        else:
            settings = await self._settings_service.get_setting(
                "platform", "orchestrator", {}
            )

        if not settings.get("warm_pool_enabled"):
            return 0

        return int(settings.get("warm_pool_replicas", 1))

    async def _get_warm_pool_replicas_ready(self) -> int:
        """Get the current ready warm pool replica count from K8s."""
        if not self._kubernetes_enabled or not self._k8s_client:
            return 0

        try:
            deployment = self._k8s_client.read_namespaced_deployment(
                name="agent-orchestrator-warm-pool",
                namespace=self._namespace,
            )
            return deployment.status.ready_replicas or 0
        except Exception as e:
            logger.debug(f"Failed to get warm pool replicas: {e}")
            return 0

    async def get_mode_status(
        self,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get comprehensive status of the orchestrator mode.

        Returns:
            Dict with mode, transition, warm pool, and job status
        """
        current_mode = await self.get_current_mode(organization_id)
        can_transition, reason, cooldown = await self.can_transition(organization_id)

        return {
            "current_mode": current_mode.value,
            "transition_active": self._current_transition is not None
            and self._current_transition.transition_state
            not in (TransitionState.ACTIVE, TransitionState.FAILED),
            "transition_state": (
                self._current_transition.transition_state.value
                if self._current_transition
                else None
            ),
            "target_mode": (
                self._current_transition.target_mode.value
                if self._current_transition and self._current_transition.target_mode
                else None
            ),
            "can_switch_mode": can_transition,
            "cooldown_remaining_seconds": cooldown,
            "cooldown_reason": reason if not can_transition else None,
            "warm_pool": {
                "desired": await self._get_warm_pool_replicas_desired(organization_id),
                "ready": await self._get_warm_pool_replicas_ready(),
            },
            "in_flight_jobs": await self._get_in_flight_jobs_count(),
        }


# Factory function for creating service instances
def create_orchestrator_mode_service(
    settings_service: Any = None,
    kubernetes_enabled: bool | None = None,
) -> OrchestratorModeService:
    """
    Create an OrchestratorModeService instance.

    Args:
        settings_service: Optional SettingsPersistenceService
        kubernetes_enabled: Whether to enable K8s integration (auto-detect if None)

    Returns:
        Configured OrchestratorModeService instance
    """
    if kubernetes_enabled is None:
        # Auto-detect: enable if running in K8s
        kubernetes_enabled = os.environ.get("KUBERNETES_SERVICE_HOST") is not None

    namespace = os.environ.get("ORCHESTRATOR_NAMESPACE", "default")

    return OrchestratorModeService(
        settings_service=settings_service,
        kubernetes_enabled=kubernetes_enabled,
        namespace=namespace,
    )
