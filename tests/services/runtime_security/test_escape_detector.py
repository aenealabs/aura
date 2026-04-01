"""
Tests for container escape detector service.
"""

from src.services.runtime_security import (
    ContainerEscapeDetector,
    EscapeTechnique,
    FalcoRule,
    Severity,
    get_escape_detector,
    reset_escape_detector,
)


class TestEscapeDetectorInitialization:
    """Tests for escape detector initialization."""

    def test_initialize_detector(self, test_config):
        """Test initializing escape detector."""
        detector = ContainerEscapeDetector()
        assert detector is not None

    def test_default_falco_rules(self, test_config):
        """Test that default Falco rules are created."""
        detector = ContainerEscapeDetector()
        rules = detector.get_falco_rules()

        assert len(rules) > 0
        rule_names = [r.name for r in rules]
        assert "Container Privilege Escalation" in rule_names

    def test_singleton_instance(self, test_config):
        """Test getting singleton instance."""
        detector1 = get_escape_detector()
        detector2 = get_escape_detector()
        assert detector1 is detector2

    def test_reset_singleton(self, test_config):
        """Test resetting singleton."""
        detector1 = get_escape_detector()
        reset_escape_detector()
        detector2 = get_escape_detector()
        assert detector1 is not detector2


class TestFalcoRuleManagement:
    """Tests for Falco rule management."""

    def test_add_falco_rule(self, test_config):
        """Test adding a custom Falco rule."""
        detector = ContainerEscapeDetector()

        rule = FalcoRule(
            rule_id="custom-rule-001",
            name="Custom Detection Rule",
            description="Test rule",
            condition="container and proc.name=suspicious",
            output="Suspicious process detected",
            priority="WARNING",
            tags=["custom", "test"],
            mitre_attack_ids=["T1059"],
        )

        detector.add_falco_rule(rule)

        rules = detector.get_falco_rules()
        rule_ids = [r.rule_id for r in rules]
        assert "custom-rule-001" in rule_ids

    def test_remove_falco_rule(self, test_config):
        """Test removing a Falco rule."""
        detector = ContainerEscapeDetector()

        # Add then remove
        rule = FalcoRule(
            rule_id="temp-rule",
            name="Temporary Rule",
            description="Test",
            condition="true",
            output="Test output",
        )
        detector.add_falco_rule(rule)

        result = detector.remove_falco_rule("temp-rule")
        assert result is True

        rules = detector.get_falco_rules()
        rule_ids = [r.rule_id for r in rules]
        assert "temp-rule" not in rule_ids

    def test_remove_nonexistent_rule(self, test_config):
        """Test removing non-existent rule."""
        detector = ContainerEscapeDetector()
        result = detector.remove_falco_rule("nonexistent")
        assert result is False

    def test_export_falco_rules(self, test_config):
        """Test exporting Falco rules as YAML."""
        detector = ContainerEscapeDetector()
        yaml_output = detector.export_falco_rules()

        assert yaml_output is not None
        assert "rule:" in yaml_output
        assert "condition:" in yaml_output


class TestEBPFEventProcessing:
    """Tests for eBPF event processing."""

    def test_process_setuid_event(self, test_config, sample_ebpf_event):
        """Test processing setuid syscall event."""
        detector = ContainerEscapeDetector()
        escape_event = detector.process_ebpf_event(sample_ebpf_event)

        assert escape_event is not None
        assert escape_event.technique == EscapeTechnique.PRIVILEGE_ESCALATION
        assert escape_event.syscall == "setuid"
        assert escape_event.mitre_attack_id == "T1611"

    def test_process_ptrace_event(self, test_config):
        """Test processing ptrace syscall event."""
        detector = ContainerEscapeDetector()

        event = {
            "syscall": "ptrace",
            "comm": "gdb",
            "container_id": "container-ptrace",
            "node_id": "node-1",
            "cluster": "test-cluster",
        }

        escape_event = detector.process_ebpf_event(event)
        assert escape_event is not None
        assert escape_event.technique == EscapeTechnique.PTRACE_ABUSE
        assert escape_event.mitre_attack_id == "T1055"

    def test_process_mount_event(self, test_config):
        """Test processing mount syscall event."""
        detector = ContainerEscapeDetector()

        event = {
            "syscall": "mount",
            "comm": "mount",
            "container_id": "container-mount",
            "node_id": "node-1",
            "cluster": "test-cluster",
        }

        escape_event = detector.process_ebpf_event(event)
        assert escape_event is not None
        assert escape_event.technique == EscapeTechnique.MOUNT_ABUSE

    def test_process_namespace_event(self, test_config):
        """Test processing namespace manipulation event."""
        detector = ContainerEscapeDetector()

        event = {
            "syscall": "unshare",
            "comm": "nsenter",
            "container_id": "container-ns",
            "node_id": "node-1",
            "cluster": "test-cluster",
        }

        escape_event = detector.process_ebpf_event(event)
        assert escape_event is not None
        assert escape_event.technique == EscapeTechnique.NAMESPACE_ESCAPE

    def test_process_safe_event(self, test_config):
        """Test processing a safe syscall (no escape detected)."""
        detector = ContainerEscapeDetector()

        event = {
            "syscall": "read",
            "comm": "cat",
            "container_id": "container-safe",
            "node_id": "node-1",
            "cluster": "test-cluster",
        }

        escape_event = detector.process_ebpf_event(event)
        assert escape_event is None


class TestFalcoAlertProcessing:
    """Tests for Falco alert processing."""

    def test_process_privilege_escalation_alert(self, test_config, sample_falco_alert):
        """Test processing privilege escalation Falco alert."""
        detector = ContainerEscapeDetector()
        escape_event = detector.process_falco_alert(sample_falco_alert)

        assert escape_event is not None
        assert escape_event.technique == EscapeTechnique.PRIVILEGE_ESCALATION
        assert escape_event.falco_rule == "Container Privilege Escalation"

    def test_process_namespace_alert(self, test_config):
        """Test processing namespace manipulation alert."""
        detector = ContainerEscapeDetector()

        alert = {
            "rule": "Container Namespace Manipulation",
            "priority": "WARNING",
            "output": "Namespace manipulation detected",
            "output_fields": {
                "container.id": "ns-container",
                "k8s.pod.name": "test-pod",
                "k8s.ns.name": "default",
                "proc.name": "nsenter",
                "syscall.type": "setns",
            },
        }

        escape_event = detector.process_falco_alert(alert)
        assert escape_event is not None
        assert escape_event.technique == EscapeTechnique.NAMESPACE_ESCAPE

    def test_process_unrelated_alert(self, test_config):
        """Test processing an unrelated Falco alert."""
        detector = ContainerEscapeDetector()

        alert = {
            "rule": "HTTP Request Logged",
            "priority": "INFO",
            "output": "HTTP request logged",
            "output_fields": {},
        }

        escape_event = detector.process_falco_alert(alert)
        # Should return None for unrelated alerts
        assert escape_event is None


class TestEscapeEventManagement:
    """Tests for escape event management."""

    def test_get_event(self, test_config, sample_ebpf_event):
        """Test getting an event by ID."""
        detector = ContainerEscapeDetector()
        escape_event = detector.process_ebpf_event(sample_ebpf_event)

        retrieved = detector.get_event(escape_event.event_id)
        assert retrieved is not None
        assert retrieved.event_id == escape_event.event_id

    def test_get_nonexistent_event(self, test_config):
        """Test getting non-existent event."""
        detector = ContainerEscapeDetector()
        retrieved = detector.get_event("nonexistent-id")
        assert retrieved is None

    def test_list_events(self, test_config):
        """Test listing escape events."""
        detector = ContainerEscapeDetector()

        # Create several events
        events = [
            {
                "syscall": "setuid",
                "comm": "bash",
                "container_id": "c1",
                "node_id": "n1",
                "cluster": "cluster-a",
                "namespace": "default",
            },
            {
                "syscall": "ptrace",
                "comm": "gdb",
                "container_id": "c2",
                "node_id": "n1",
                "cluster": "cluster-a",
                "namespace": "kube-system",
            },
            {
                "syscall": "mount",
                "comm": "mount",
                "container_id": "c3",
                "node_id": "n2",
                "cluster": "cluster-b",
                "namespace": "default",
            },
        ]

        for e in events:
            detector.process_ebpf_event(e)

        # List all
        all_events = detector.list_events()
        assert len(all_events) == 3

        # Filter by cluster
        cluster_a_events = detector.list_events(cluster="cluster-a")
        assert len(cluster_a_events) == 2

        # Filter by namespace
        kube_events = detector.list_events(namespace="kube-system")
        assert len(kube_events) == 1

        # Filter by technique
        escalation_events = detector.list_events(
            technique=EscapeTechnique.PRIVILEGE_ESCALATION
        )
        assert len(escalation_events) == 1

    def test_get_technique_stats(self, test_config):
        """Test getting technique statistics."""
        detector = ContainerEscapeDetector()

        events = [
            {
                "syscall": "setuid",
                "comm": "bash",
                "container_id": "c1",
                "node_id": "n1",
                "cluster": "test",
            },
            {
                "syscall": "setuid",
                "comm": "su",
                "container_id": "c2",
                "node_id": "n1",
                "cluster": "test",
            },
            {
                "syscall": "ptrace",
                "comm": "gdb",
                "container_id": "c3",
                "node_id": "n1",
                "cluster": "test",
            },
        ]

        for e in events:
            detector.process_ebpf_event(e)

        stats = detector.get_technique_stats()
        assert stats["privilege-escalation"] == 2
        assert stats["ptrace-abuse"] == 1


class TestEscapeEventSeverity:
    """Tests for escape event severity derivation."""

    def test_critical_technique_severity(self, test_config):
        """Test that critical techniques get CRITICAL severity."""
        detector = ContainerEscapeDetector()

        # Kernel exploit
        from src.services.runtime_security import EscapeEvent

        event = EscapeEvent(
            event_id="test-001",
            cluster="test",
            node_id="node-1",
            container_id="container-1",
            pod_name="pod",
            namespace="default",
            technique=EscapeTechnique.KERNEL_EXPLOIT,
        )
        assert event.severity == Severity.CRITICAL

        # Dirty pipe
        event.technique = EscapeTechnique.DIRTY_PIPE
        assert event.severity == Severity.CRITICAL

    def test_high_technique_severity(self, test_config):
        """Test that high-risk techniques get HIGH severity."""
        from src.services.runtime_security import EscapeEvent

        event = EscapeEvent(
            event_id="test-002",
            cluster="test",
            node_id="node-1",
            container_id="container-1",
            pod_name="pod",
            namespace="default",
            technique=EscapeTechnique.PRIVILEGE_ESCALATION,
        )
        assert event.severity == Severity.HIGH


class TestAlertHandlers:
    """Tests for alert handler functionality."""

    def test_add_alert_handler(self, test_config, sample_ebpf_event):
        """Test adding custom alert handler."""
        detector = ContainerEscapeDetector()
        alerts_received = []

        def custom_handler(event):
            alerts_received.append(event)

        detector.add_alert_handler(custom_handler)
        detector.process_ebpf_event(sample_ebpf_event)

        assert len(alerts_received) == 1
        assert alerts_received[0].technique == EscapeTechnique.PRIVILEGE_ESCALATION

    def test_multiple_alert_handlers(self, test_config, sample_ebpf_event):
        """Test multiple alert handlers are called."""
        detector = ContainerEscapeDetector()
        handler1_calls = []
        handler2_calls = []

        detector.add_alert_handler(lambda e: handler1_calls.append(e))
        detector.add_alert_handler(lambda e: handler2_calls.append(e))

        detector.process_ebpf_event(sample_ebpf_event)

        assert len(handler1_calls) == 1
        assert len(handler2_calls) == 1


class TestFalcoRuleExport:
    """Tests for Falco rule export functionality."""

    def test_falco_rule_to_yaml(self, test_config):
        """Test converting rule to Falco YAML format."""
        rule = FalcoRule(
            rule_id="test-rule",
            name="Test Rule",
            description="A test detection rule",
            condition="container and proc.name=test",
            output="Test process detected",
            priority="WARNING",
            tags=["test", "container"],
            mitre_attack_ids=["T1059"],
            enabled=True,
        )

        yaml_dict = rule.to_falco_yaml()

        assert yaml_dict["rule"] == "Test Rule"
        assert yaml_dict["desc"] == "A test detection rule"
        assert yaml_dict["condition"] == "container and proc.name=test"
        assert yaml_dict["priority"] == "WARNING"
        assert "mitre_T1059" in yaml_dict["tags"]
