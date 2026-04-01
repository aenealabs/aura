"""
Hardware Fingerprint Generation for Offline License Validation.

Generates a stable hardware identifier used to bind licenses to specific
deployments. Supports both physical machines and containerized environments.
"""

import hashlib
import logging
import os
import platform
import re
import socket
import subprocess
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class HardwareFingerprint:
    """Container for hardware identification data."""

    machine_id: Optional[str] = None
    hostname: Optional[str] = None
    cpu_info: Optional[str] = None
    mac_addresses: list[str] = None
    platform_info: Optional[str] = None
    container_id: Optional[str] = None
    kubernetes_info: Optional[str] = None

    def __post_init__(self):
        if self.mac_addresses is None:
            self.mac_addresses = []

    def to_hash(self) -> str:
        """
        Generate stable SHA-256 hash of hardware identifiers.

        Uses multiple identifiers to create a stable fingerprint that
        survives minor hardware changes.
        """
        # Combine stable identifiers
        components = []

        # Machine ID is most stable
        if self.machine_id:
            components.append(f"machine:{self.machine_id}")

        # Kubernetes pod info for container deployments
        if self.kubernetes_info:
            components.append(f"k8s:{self.kubernetes_info}")

        # CPU info provides hardware baseline
        if self.cpu_info:
            components.append(f"cpu:{self.cpu_info}")

        # MAC addresses (sorted for consistency)
        if self.mac_addresses:
            sorted_macs = sorted(self.mac_addresses)
            components.append(f"macs:{','.join(sorted_macs[:3])}")

        # Platform as fallback
        if self.platform_info:
            components.append(f"platform:{self.platform_info}")

        # Generate hash
        fingerprint_string = "|".join(components)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()

    def to_dict(self) -> dict:
        """Convert to dictionary for debugging/logging."""
        return {
            "machine_id": self.machine_id,
            "hostname": self.hostname,
            "cpu_info": self.cpu_info,
            "mac_addresses": self.mac_addresses,
            "platform_info": self.platform_info,
            "container_id": self.container_id,
            "kubernetes_info": self.kubernetes_info,
        }


def _get_machine_id() -> Optional[str]:
    """
    Get system machine ID.

    Checks multiple sources for a stable machine identifier:
    - /etc/machine-id (Linux systemd)
    - /var/lib/dbus/machine-id (Linux fallback)
    - IOPlatformUUID (macOS)
    - MachineGuid (Windows registry)
    """
    # Linux: systemd machine-id
    for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
        try:
            with open(path, "r") as f:
                machine_id = f.read().strip()
                if machine_id:
                    return machine_id
        except (FileNotFoundError, PermissionError):
            continue

    # macOS: IOPlatformUUID
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                [
                    "ioreg",
                    "-rd1",
                    "-c",
                    "IOPlatformExpertDevice",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            match = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', result.stdout)
            if match:
                return match.group(1)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Windows: MachineGuid
    if platform.system() == "Windows":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            )
            machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            return machine_guid
        except (ImportError, OSError):
            pass

    return None


def _get_cpu_info() -> Optional[str]:
    """Get CPU model information."""
    system = platform.system()

    if system == "Linux":
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":")[1].strip()
        except (FileNotFoundError, PermissionError):
            pass

    elif system == "Darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    elif system == "Windows":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            cpu_name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            return cpu_name
        except (ImportError, OSError):
            pass

    return platform.processor() or None


def _get_mac_addresses() -> list[str]:
    """
    Get network interface MAC addresses.

    Filters out virtual/docker interfaces for stability.
    """
    macs = []

    try:
        import uuid

        # Get MAC from uuid module (cross-platform)
        mac = uuid.getnode()
        if mac != uuid.getnode():  # Check if it's a random MAC
            mac_str = ":".join(f"{(mac >> i) & 0xff:02x}" for i in range(0, 48, 8))
            macs.append(mac_str)
    except Exception:
        pass

    # Linux: Read from /sys/class/net
    if platform.system() == "Linux":
        try:
            net_path = "/sys/class/net"
            for iface in os.listdir(net_path):
                # Skip virtual interfaces
                if iface.startswith(("lo", "docker", "veth", "br-", "virbr")):
                    continue

                addr_path = os.path.join(net_path, iface, "address")
                try:
                    with open(addr_path, "r") as f:
                        mac = f.read().strip()
                        if mac and mac != "00:00:00:00:00:00":
                            macs.append(mac)
                except (FileNotFoundError, PermissionError):
                    continue
        except (FileNotFoundError, PermissionError):
            pass

    return list(set(macs))  # Deduplicate


def _get_container_id() -> Optional[str]:
    """Get container ID if running in a container."""
    # Check cgroup for container ID
    try:
        with open("/proc/1/cgroup", "r") as f:
            for line in f:
                # Docker: /docker/<container_id>
                # Kubernetes: /kubepods/.../<container_id>
                match = re.search(r"docker[/-]([a-f0-9]{64})", line)
                if match:
                    return match.group(1)[:12]

                match = re.search(r"/kubepods[^/]*/[^/]*/([a-f0-9]{64})", line)
                if match:
                    return match.group(1)[:12]
    except (FileNotFoundError, PermissionError):
        pass

    # Check for container environment variable
    return os.getenv("CONTAINER_ID") or os.getenv("HOSTNAME")


def _get_kubernetes_info() -> Optional[str]:
    """Get Kubernetes deployment information."""
    # Check for Kubernetes environment
    namespace = os.getenv("POD_NAMESPACE") or os.getenv("KUBERNETES_NAMESPACE")
    node_name = os.getenv("NODE_NAME")

    if namespace:
        components = [f"ns:{namespace}"]
        if node_name:
            components.append(f"node:{node_name}")
        return "|".join(components)

    # Check for service account token (indicates K8s environment)
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/namespace"):
        try:
            with open(
                "/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r"
            ) as f:
                namespace = f.read().strip()
                return f"ns:{namespace}"
        except (FileNotFoundError, PermissionError):
            pass

    return None


def generate_hardware_fingerprint() -> str:
    """
    Generate a hardware fingerprint hash.

    Returns:
        SHA-256 hash of hardware identifiers

    This function collects various hardware identifiers and combines
    them into a stable fingerprint that can be used for license binding.

    For containerized deployments, it uses Kubernetes namespace and
    node information to create a deployment-specific fingerprint.
    """
    fingerprint = HardwareFingerprint(
        machine_id=_get_machine_id(),
        hostname=socket.gethostname(),
        cpu_info=_get_cpu_info(),
        mac_addresses=_get_mac_addresses(),
        platform_info=f"{platform.system()}-{platform.machine()}",
        container_id=_get_container_id(),
        kubernetes_info=_get_kubernetes_info(),
    )

    logger.debug("Hardware fingerprint components: %s", fingerprint.to_dict())

    return fingerprint.to_hash()


def get_fingerprint_details() -> dict:
    """
    Get detailed hardware fingerprint information.

    Returns:
        Dictionary with fingerprint components and hash

    Useful for debugging and support purposes.
    """
    fingerprint = HardwareFingerprint(
        machine_id=_get_machine_id(),
        hostname=socket.gethostname(),
        cpu_info=_get_cpu_info(),
        mac_addresses=_get_mac_addresses(),
        platform_info=f"{platform.system()}-{platform.machine()}",
        container_id=_get_container_id(),
        kubernetes_info=_get_kubernetes_info(),
    )

    details = fingerprint.to_dict()
    details["fingerprint_hash"] = fingerprint.to_hash()

    return details


def verify_fingerprint(expected_hash: str, tolerance: int = 0) -> bool:
    """
    Verify current hardware matches expected fingerprint.

    Args:
        expected_hash: Expected SHA-256 fingerprint hash
        tolerance: Number of differing hash prefix bytes to allow

    Returns:
        True if fingerprint matches within tolerance
    """
    current_hash = generate_hardware_fingerprint()

    if current_hash == expected_hash:
        return True

    if tolerance > 0:
        # Allow prefix match with tolerance
        prefix_len = 64 - (tolerance * 2)  # Each byte = 2 hex chars
        if current_hash[:prefix_len] == expected_hash[:prefix_len]:
            logger.info(
                "Hardware fingerprint matched with tolerance %d",
                tolerance,
            )
            return True

    return False
