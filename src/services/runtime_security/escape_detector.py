"""
Project Aura - Container Escape Detector Service

Detects container escape attempts using eBPF monitoring and Falco integration.
Maps escape techniques to MITRE ATT&CK framework.

Based on ADR-077: Cloud Runtime Security Integration
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .config import RuntimeSecurityConfig, get_runtime_security_config
from .contracts import EscapeEvent, EscapeTechnique, FalcoRule
from .metrics import get_runtime_security_metrics

logger = logging.getLogger(__name__)


# MITRE ATT&CK mappings for escape techniques
MITRE_MAPPING = {
    EscapeTechnique.PRIVILEGE_ESCALATION: "T1611",
    EscapeTechnique.NAMESPACE_ESCAPE: "T1611.001",
    EscapeTechnique.KERNEL_EXPLOIT: "T1068",
    EscapeTechnique.SYMLINK_ATTACK: "T1068",
    EscapeTechnique.CGROUP_ESCAPE: "T1611",
    EscapeTechnique.MOUNT_ABUSE: "T1611",
    EscapeTechnique.PTRACE_ABUSE: "T1055",
    EscapeTechnique.CAPABILITY_ABUSE: "T1611",
    EscapeTechnique.DIRTY_PIPE: "T1068",
    EscapeTechnique.OVERLAYFS: "T1068",
}


# Syscall to escape technique mapping
SYSCALL_TECHNIQUE_MAP = {
    "setuid": EscapeTechnique.PRIVILEGE_ESCALATION,
    "setgid": EscapeTechnique.PRIVILEGE_ESCALATION,
    "setresuid": EscapeTechnique.PRIVILEGE_ESCALATION,
    "setresgid": EscapeTechnique.PRIVILEGE_ESCALATION,
    "ptrace": EscapeTechnique.PTRACE_ABUSE,
    "mount": EscapeTechnique.MOUNT_ABUSE,
    "umount": EscapeTechnique.MOUNT_ABUSE,
    "unshare": EscapeTechnique.NAMESPACE_ESCAPE,
    "clone": EscapeTechnique.NAMESPACE_ESCAPE,
    "setns": EscapeTechnique.NAMESPACE_ESCAPE,
    "pivot_root": EscapeTechnique.NAMESPACE_ESCAPE,
}


@dataclass
class EscapeSignature:
    """A pattern for detecting container escape attempts."""

    name: str
    technique: EscapeTechnique
    syscalls: list[str] = field(default_factory=list)
    process_patterns: list[str] = field(default_factory=list)
    capability_requirements: list[str] = field(default_factory=list)
    description: str = ""
    cve_ids: list[str] = field(default_factory=list)


# Built-in escape signatures
ESCAPE_SIGNATURES = [
    EscapeSignature(
        name="setuid_privilege_escalation",
        technique=EscapeTechnique.PRIVILEGE_ESCALATION,
        syscalls=["setuid", "setgid", "setresuid", "setresgid"],
        description="Process attempting to change UID/GID to gain privileges",
    ),
    EscapeSignature(
        name="ptrace_injection",
        technique=EscapeTechnique.PTRACE_ABUSE,
        syscalls=["ptrace"],
        capability_requirements=["CAP_SYS_PTRACE"],
        description="Process using ptrace to attach to other processes",
    ),
    EscapeSignature(
        name="namespace_escape",
        technique=EscapeTechnique.NAMESPACE_ESCAPE,
        syscalls=["unshare", "setns", "clone"],
        description="Process manipulating namespaces to escape container",
    ),
    EscapeSignature(
        name="mount_escape",
        technique=EscapeTechnique.MOUNT_ABUSE,
        syscalls=["mount", "umount2"],
        capability_requirements=["CAP_SYS_ADMIN"],
        description="Process manipulating mount points to access host filesystem",
    ),
    EscapeSignature(
        name="cgroup_escape",
        technique=EscapeTechnique.CGROUP_ESCAPE,
        process_patterns=["*/release_agent", "*cgroup*notify_on_release*"],
        description="Exploitation of cgroup release_agent for container escape",
    ),
    EscapeSignature(
        name="dirty_pipe",
        technique=EscapeTechnique.DIRTY_PIPE,
        syscalls=["splice"],
        cve_ids=["CVE-2022-0847"],
        description="Dirty Pipe kernel vulnerability exploitation",
    ),
    EscapeSignature(
        name="overlayfs_escape",
        technique=EscapeTechnique.OVERLAYFS,
        process_patterns=["*overlayfs*", "*overlay2*"],
        cve_ids=["CVE-2021-3493", "CVE-2023-0386"],
        description="OverlayFS vulnerability exploitation",
    ),
]


class ContainerEscapeDetector:
    """
    Detects container escape attempts using eBPF and Falco.

    Detection Categories:
    - Privilege escalation (CAP_SYS_ADMIN abuse)
    - Namespace escape (mount, PID, network)
    - Kernel exploits (dirty pipe, overlayfs)
    - Symlink attacks (CVE-style container escapes)
    - Resource abuse (cgroups escape)
    """

    def __init__(self, config: Optional[RuntimeSecurityConfig] = None):
        """Initialize escape detector with configuration."""
        self._config = config or get_runtime_security_config()
        self._metrics = get_runtime_security_metrics()
        self._events: dict[str, EscapeEvent] = {}
        self._falco_rules: dict[str, FalcoRule] = {}
        self._signatures: list[EscapeSignature] = ESCAPE_SIGNATURES.copy()
        self._alert_handlers: list[Callable[[EscapeEvent], None]] = []
        self._connected_to_falco = False

        # Initialize default Falco rules
        self._init_default_falco_rules()

    def _init_default_falco_rules(self) -> None:
        """Initialize default Falco detection rules."""
        rules = [
            FalcoRule(
                rule_id="aura-privilege-escalation",
                name="Container Privilege Escalation",
                description="Detect privilege escalation attempts in containers",
                condition="container and proc.name in (su, sudo) and not user.name=root",
                output="Privilege escalation attempt (user=%user.name command=%proc.cmdline container=%container.id)",
                priority="CRITICAL",
                tags=["container", "privilege_escalation"],
                mitre_attack_ids=["T1611"],
                enabled=True,
            ),
            FalcoRule(
                rule_id="aura-namespace-manipulation",
                name="Container Namespace Manipulation",
                description="Detect namespace manipulation for container escape",
                condition="container and (syscall.type=unshare or syscall.type=setns)",
                output="Namespace manipulation (syscall=%syscall.type proc=%proc.name container=%container.id)",
                priority="WARNING",
                tags=["container", "namespace"],
                mitre_attack_ids=["T1611.001"],
                enabled=True,
            ),
            FalcoRule(
                rule_id="aura-mount-abuse",
                name="Container Mount Abuse",
                description="Detect suspicious mount operations in containers",
                condition="container and syscall.type=mount and not proc.name in (kubelet, dockerd, containerd)",
                output="Mount operation in container (proc=%proc.name mount_target=%evt.arg.target container=%container.id)",
                priority="WARNING",
                tags=["container", "mount"],
                mitre_attack_ids=["T1611"],
                enabled=True,
            ),
            FalcoRule(
                rule_id="aura-sensitive-file-access",
                name="Sensitive File Access in Container",
                description="Detect access to sensitive host files from containers",
                condition="container and fd.name startswith /etc/shadow or fd.name startswith /etc/passwd",
                output="Sensitive file access (file=%fd.name proc=%proc.name container=%container.id)",
                priority="CRITICAL",
                tags=["container", "file_access"],
                mitre_attack_ids=["T1003"],
                enabled=True,
            ),
            FalcoRule(
                rule_id="aura-ptrace-container",
                name="Ptrace in Container",
                description="Detect ptrace syscall usage in containers",
                condition="container and syscall.type=ptrace",
                output="Ptrace detected (proc=%proc.name target=%evt.arg.request container=%container.id)",
                priority="WARNING",
                tags=["container", "ptrace"],
                mitre_attack_ids=["T1055"],
                enabled=True,
            ),
            FalcoRule(
                rule_id="aura-cgroup-escape",
                name="Cgroup Escape Attempt",
                description="Detect potential cgroup-based container escape",
                condition="container and fd.name contains release_agent",
                output="Cgroup escape attempt (file=%fd.name proc=%proc.name container=%container.id)",
                priority="CRITICAL",
                tags=["container", "cgroup", "escape"],
                mitre_attack_ids=["T1611"],
                enabled=True,
            ),
        ]

        for rule in rules:
            self._falco_rules[rule.rule_id] = rule

    def add_falco_rule(self, rule: FalcoRule) -> None:
        """Add a custom Falco detection rule."""
        self._falco_rules[rule.rule_id] = rule
        logger.info(f"Added Falco rule: {rule.rule_id}")

    def remove_falco_rule(self, rule_id: str) -> bool:
        """Remove a Falco rule."""
        if rule_id in self._falco_rules:
            del self._falco_rules[rule_id]
            logger.info(f"Removed Falco rule: {rule_id}")
            return True
        return False

    def get_falco_rules(self) -> list[FalcoRule]:
        """Get all configured Falco rules."""
        return list(self._falco_rules.values())

    def add_signature(self, signature: EscapeSignature) -> None:
        """Add a custom escape signature."""
        self._signatures.append(signature)
        logger.info(f"Added escape signature: {signature.name}")

    def add_alert_handler(self, handler: Callable[[EscapeEvent], None]) -> None:
        """Add a handler to be called on escape detection."""
        self._alert_handlers.append(handler)

    def process_ebpf_event(self, raw_event: dict[str, Any]) -> Optional[EscapeEvent]:
        """
        Process an eBPF-captured event for escape detection.

        Args:
            raw_event: Raw eBPF event data

        Returns:
            EscapeEvent if escape detected, None otherwise
        """
        try:
            syscall = raw_event.get("syscall", "")
            process_name = raw_event.get("comm", "")
            container_id = raw_event.get("container_id", "")
            node_id = raw_event.get("node_id", "")
            cluster = raw_event.get("cluster", self._config.cluster_name)
            user_id = raw_event.get("uid")
            args = raw_event.get("args", "")

            # Record eBPF event metric
            self._metrics.record_ebpf_event(syscall=syscall, cluster=cluster)

            # Check against signatures
            technique = self._detect_technique(syscall, process_name, args)

            if technique == EscapeTechnique.NONE:
                return None

            # Create escape event
            event_id = f"esc-{uuid.uuid4().hex[:12]}"
            mitre_id = MITRE_MAPPING.get(technique)

            event = EscapeEvent(
                event_id=event_id,
                cluster=cluster,
                node_id=node_id,
                container_id=container_id,
                pod_name=raw_event.get("pod_name", ""),
                namespace=raw_event.get("namespace", "default"),
                image_digest=raw_event.get("image_digest"),
                technique=technique,
                syscall=syscall,
                process_name=process_name,
                process_args=args,
                user_id=user_id,
                blocked=self._config.escape_detector.block_escapes,
                mitre_attack_id=mitre_id,
                raw_event=raw_event,
            )

            self._events[event.event_id] = event
            self._record_escape_metrics(event)
            self._trigger_alerts(event)

            logger.warning(
                f"Container escape attempt detected: {technique.value} "
                f"in container {container_id} on node {node_id}"
            )

            return event

        except Exception as e:
            logger.error(f"Failed to process eBPF event: {e}")
            return None

    def process_falco_alert(self, raw_alert: dict[str, Any]) -> Optional[EscapeEvent]:
        """
        Process a Falco alert for escape detection.

        Args:
            raw_alert: Raw Falco alert data

        Returns:
            EscapeEvent if escape-related, None otherwise
        """
        try:
            rule_name = raw_alert.get("rule", "")
            priority = raw_alert.get("priority", "WARNING")
            raw_alert.get("output", "")  # Consumed by downstream processors
            output_fields = raw_alert.get("output_fields", {})

            # Record Falco alert metric
            self._metrics.record_falco_alert(
                rule=rule_name,
                priority=priority,
                cluster=self._config.cluster_name,
            )

            # Find matching rule
            matched_rule = None
            for rule in self._falco_rules.values():
                if rule.name == rule_name or rule_name in rule.tags:
                    matched_rule = rule
                    break

            if not matched_rule:
                # Check if rule name indicates escape attempt
                escape_keywords = [
                    "escape",
                    "privilege",
                    "namespace",
                    "mount",
                    "ptrace",
                    "cgroup",
                ]
                if not any(kw in rule_name.lower() for kw in escape_keywords):
                    return None

            # Extract container info from output fields
            container_id = output_fields.get("container.id", "")
            pod_name = output_fields.get("k8s.pod.name", "")
            namespace = output_fields.get("k8s.ns.name", "default")
            process_name = output_fields.get("proc.name", "")
            syscall = output_fields.get("syscall.type", "")

            # Determine technique from rule
            technique = self._technique_from_falco_rule(matched_rule, rule_name)

            if technique == EscapeTechnique.NONE:
                return None

            event_id = f"esc-falco-{uuid.uuid4().hex[:12]}"
            mitre_ids = matched_rule.mitre_attack_ids if matched_rule else []
            mitre_id = mitre_ids[0] if mitre_ids else MITRE_MAPPING.get(technique)

            event = EscapeEvent(
                event_id=event_id,
                cluster=self._config.cluster_name,
                node_id=output_fields.get("node", ""),
                container_id=container_id,
                pod_name=pod_name,
                namespace=namespace,
                technique=technique,
                syscall=syscall,
                process_name=process_name,
                blocked=self._config.escape_detector.block_escapes,
                mitre_attack_id=mitre_id,
                falco_rule=rule_name,
                raw_event=raw_alert,
            )

            self._events[event.event_id] = event
            self._record_escape_metrics(event)
            self._trigger_alerts(event)

            logger.warning(
                f"Falco detected escape attempt: {technique.value} "
                f"(rule: {rule_name}) in container {container_id}"
            )

            return event

        except Exception as e:
            logger.error(f"Failed to process Falco alert: {e}")
            return None

    def get_event(self, event_id: str) -> Optional[EscapeEvent]:
        """Get an escape event by ID."""
        return self._events.get(event_id)

    def list_events(
        self,
        cluster: Optional[str] = None,
        namespace: Optional[str] = None,
        technique: Optional[EscapeTechnique] = None,
        limit: int = 100,
    ) -> list[EscapeEvent]:
        """
        List escape events with optional filters.

        Args:
            cluster: Filter by cluster name
            namespace: Filter by namespace
            technique: Filter by escape technique
            limit: Maximum number of events to return

        Returns:
            List of matching escape events
        """
        events = list(self._events.values())

        if cluster:
            events = [e for e in events if e.cluster == cluster]

        if namespace:
            events = [e for e in events if e.namespace == namespace]

        if technique:
            events = [e for e in events if e.technique == technique]

        # Sort by timestamp descending
        events.sort(key=lambda e: e.timestamp, reverse=True)

        return events[:limit]

    def get_technique_stats(self) -> dict[str, int]:
        """Get statistics on detected escape techniques."""
        stats: dict[str, int] = {}
        for event in self._events.values():
            technique_name = event.technique.value
            stats[technique_name] = stats.get(technique_name, 0) + 1
        return stats

    def _detect_technique(
        self, syscall: str, process_name: str, args: str
    ) -> EscapeTechnique:
        """Detect escape technique from syscall and process info."""
        # Check syscall mapping
        if syscall in SYSCALL_TECHNIQUE_MAP:
            return SYSCALL_TECHNIQUE_MAP[syscall]

        # Check signatures
        for sig in self._signatures:
            if syscall in sig.syscalls:
                return sig.technique

            for pattern in sig.process_patterns:
                if (
                    pattern.replace("*", "") in process_name
                    or pattern.replace("*", "") in args
                ):
                    return sig.technique

        return EscapeTechnique.NONE

    def _technique_from_falco_rule(
        self, rule: Optional[FalcoRule], rule_name: str
    ) -> EscapeTechnique:
        """Determine escape technique from Falco rule."""
        rule_lower = rule_name.lower()

        if "privilege" in rule_lower or "escalat" in rule_lower:
            return EscapeTechnique.PRIVILEGE_ESCALATION
        elif "namespace" in rule_lower:
            return EscapeTechnique.NAMESPACE_ESCAPE
        elif "mount" in rule_lower:
            return EscapeTechnique.MOUNT_ABUSE
        elif "ptrace" in rule_lower:
            return EscapeTechnique.PTRACE_ABUSE
        elif "cgroup" in rule_lower:
            return EscapeTechnique.CGROUP_ESCAPE
        elif "kernel" in rule_lower or "exploit" in rule_lower:
            return EscapeTechnique.KERNEL_EXPLOIT

        # Check rule's MITRE mappings
        if rule and rule.mitre_attack_ids:
            for mitre_id in rule.mitre_attack_ids:
                for technique, mapped_id in MITRE_MAPPING.items():
                    if mitre_id == mapped_id:
                        return technique

        return EscapeTechnique.NONE

    def _record_escape_metrics(self, event: EscapeEvent) -> None:
        """Record metrics for an escape event."""
        self._metrics.record_escape_attempt(
            technique=event.technique.value,
            cluster=event.cluster,
            blocked=event.blocked,
        )

    def _trigger_alerts(self, event: EscapeEvent) -> None:
        """Trigger alerts for an escape event."""
        for handler in self._alert_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")

        # Would send SNS/EventBridge alerts here in production
        if self._config.escape_detector.alert_sns_topic:
            self._send_sns_alert(event)

        if self._config.escape_detector.alert_eventbridge_bus:
            self._send_eventbridge_alert(event)

    def _send_sns_alert(self, event: EscapeEvent) -> None:
        """Send SNS notification for escape event."""
        # In production, would use boto3 SNS client
        logger.info(f"Would send SNS alert for escape event {event.event_id}")

    def _send_eventbridge_alert(self, event: EscapeEvent) -> None:
        """Send EventBridge event for escape event."""
        # In production, would use boto3 EventBridge client
        logger.info(f"Would send EventBridge event for escape event {event.event_id}")

    def export_falco_rules(self) -> str:
        """Export all Falco rules as YAML."""
        import yaml

        rules_list = [
            rule.to_falco_yaml() for rule in self._falco_rules.values() if rule.enabled
        ]
        return yaml.dump(rules_list, default_flow_style=False)


# Singleton instance
_detector_instance: Optional[ContainerEscapeDetector] = None


def get_escape_detector() -> ContainerEscapeDetector:
    """Get singleton escape detector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = ContainerEscapeDetector()
    return _detector_instance


def reset_escape_detector() -> None:
    """Reset escape detector singleton (for testing)."""
    global _detector_instance
    _detector_instance = None
