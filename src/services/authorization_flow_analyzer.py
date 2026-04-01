"""
Project Aura - Authorization Flow Analyzer Service

Extracts and analyzes authorization flows from code using graph traversal.
Identifies authorization patterns, bypasses, and missing checks.

Part of AWS Security Agent capability parity (ADR-019 Gap 4).

Author: Project Aura Team
Created: 2025-12-03
Version: 1.0.0
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AuthorizationPattern(Enum):
    """Types of authorization patterns detected in code."""

    RBAC = "rbac"  # Role-Based Access Control
    ABAC = "abac"  # Attribute-Based Access Control
    ACL = "acl"  # Access Control Lists
    OWNERSHIP = "ownership"  # Owner-based access
    NONE = "none"  # No authorization detected


class AuthorizationCheckType(Enum):
    """Types of authorization checks."""

    ROLE_CHECK = "role_check"  # @roles_required, hasRole()
    PERMISSION_CHECK = "permission_check"  # @permission_required
    OWNERSHIP_CHECK = "ownership_check"  # user.id == resource.owner_id
    SESSION_CHECK = "session_check"  # session.user, request.user
    JWT_CHECK = "jwt_check"  # JWT token validation
    API_KEY_CHECK = "api_key_check"  # API key validation
    NONE = "none"  # No check


@dataclass
class AuthorizationNode:
    """A node in the authorization flow graph."""

    node_id: str
    node_type: str  # function, decorator, conditional
    name: str
    file_path: str
    line_number: int
    check_type: AuthorizationCheckType
    parameters: list[str] = field(default_factory=list)


@dataclass
class AuthorizationFlow:
    """An authorization flow from entry point to resource access."""

    flow_id: str
    entry_point: AuthorizationNode
    auth_nodes: list[AuthorizationNode]
    resource_access: AuthorizationNode
    is_protected: bool
    pattern: AuthorizationPattern
    confidence: float = 0.8


@dataclass
class AuthorizationGap:
    """A gap or weakness in authorization flow."""

    gap_id: str
    gap_type: str  # missing_check, weak_check, bypass_possible
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    flow: AuthorizationFlow
    description: str
    recommendation: str
    cwe_ids: list[str] = field(default_factory=list)


class AuthorizationFlowAnalyzer:
    """
    Analyzes authorization flows in code using graph traversal.

    Capabilities:
    - Extract authorization patterns from source code
    - Build authorization flow graphs
    - Identify missing or weak authorization checks
    - Detect potential authorization bypasses

    Usage:
        analyzer = AuthorizationFlowAnalyzer(neptune_service)
        flows = await analyzer.analyze_authorization_flows("src/api/")
        gaps = await analyzer.find_authorization_gaps(flows)
    """

    def __init__(
        self,
        neptune_service: Any = None,
        use_mock: bool = False,
    ):
        """
        Initialize the Authorization Flow Analyzer.

        Args:
            neptune_service: Neptune graph service for queries
            use_mock: Use mock mode for testing
        """
        self.neptune = neptune_service
        self.use_mock = use_mock or neptune_service is None
        self._flow_counter = 0
        self._gap_counter = 0

        # Authorization patterns to detect
        self.auth_decorator_patterns = [
            r"@(?:login_required|auth_required|authenticated)",
            r"@(?:roles_required|require_role|role)\(['\"](\w+)['\"]",
            r"@(?:permissions_required|require_permission|permission)",
            r"@(?:jwt_required|jwt_auth|token_required)",
            r"@(?:api_key_required|apikey_auth)",
        ]

        self.auth_function_patterns = [
            r"(?:check|verify|validate)_(?:auth|role|permission|access)",
            r"(?:is|has)_(?:admin|authenticated|authorized|allowed)",
            r"require_(?:auth|role|permission)",
            r"current_user",
            r"get_current_user",
            r"request\.user",
            r"session\.(?:user|uid|user_id)",
        ]

        self.ownership_patterns = [
            r"\.owner(?:_id)?(?:\s*==|\s*!=)",
            r"(?:user|current_user)(?:\.id|_id)\s*==\s*\w+\.(?:user|owner)",
            r"belongs_to\s*\(",
            r"owned_by\s*\(",
        ]

        self.resource_access_patterns = [
            r"\.get\s*\(\s*['\"]?\w*[iI][dD]",
            r"\.filter\s*\(",
            r"\.find(?:_one|_by_id)?\s*\(",
            r"\.query\s*\(",
            r"\.execute\s*\(",
            r"SELECT\s+.*\s+FROM",
            r"UPDATE\s+.*\s+SET",
            r"DELETE\s+FROM",
        ]

    def _generate_flow_id(self) -> str:
        """Generate unique flow ID."""
        self._flow_counter += 1
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"AFL-{timestamp}-{self._flow_counter:04d}"

    def _generate_gap_id(self) -> str:
        """Generate unique gap ID."""
        self._gap_counter += 1
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"AGP-{timestamp}-{self._gap_counter:04d}"

    async def analyze_file(
        self,
        file_path: str,
        content: str,
    ) -> list[AuthorizationFlow]:
        """
        Analyze authorization flows in a single file.

        Args:
            file_path: Path to the file
            content: File content

        Returns:
            List of authorization flows found
        """
        flows: list[AuthorizationFlow] = []

        # Find all functions/methods
        function_pattern = r"(?:def|async def)\s+(\w+)\s*\([^)]*\)"
        for match in re.finditer(function_pattern, content):
            func_name = match.group(1)
            func_start = match.start()
            line_number = content[:func_start].count("\n") + 1

            # Check for auth decorators above the function
            decorator_context = content[max(0, func_start - 500) : func_start]
            auth_nodes: list[AuthorizationNode] = []

            for dec_pattern in self.auth_decorator_patterns:
                for dec_match in re.finditer(dec_pattern, decorator_context):
                    auth_nodes.append(
                        AuthorizationNode(
                            node_id=f"{file_path}:{line_number}:decorator",
                            node_type="decorator",
                            name=dec_match.group(0),
                            file_path=file_path,
                            line_number=line_number
                            - decorator_context[dec_match.end() :].count("\n")
                            - 1,
                            check_type=self._classify_check_type(dec_match.group(0)),
                            parameters=(
                                list(dec_match.groups()) if dec_match.groups() else []
                            ),
                        )
                    )

            # Get function body
            func_body_start = content.find(":", func_start) + 1
            next_def = content.find("\ndef ", func_body_start)
            if next_def == -1:
                next_def = len(content)
            func_body = content[func_body_start:next_def]

            # Check for auth function calls in body
            for auth_pattern in self.auth_function_patterns:
                for auth_match in re.finditer(auth_pattern, func_body):
                    auth_line = line_number + func_body[: auth_match.start()].count(
                        "\n"
                    )
                    auth_nodes.append(
                        AuthorizationNode(
                            node_id=f"{file_path}:{auth_line}:call",
                            node_type="function_call",
                            name=auth_match.group(0),
                            file_path=file_path,
                            line_number=auth_line,
                            check_type=self._classify_check_type(auth_match.group(0)),
                        )
                    )

            # Check for ownership checks
            for own_pattern in self.ownership_patterns:
                for own_match in re.finditer(own_pattern, func_body):
                    own_line = line_number + func_body[: own_match.start()].count("\n")
                    auth_nodes.append(
                        AuthorizationNode(
                            node_id=f"{file_path}:{own_line}:ownership",
                            node_type="conditional",
                            name=own_match.group(0),
                            file_path=file_path,
                            line_number=own_line,
                            check_type=AuthorizationCheckType.OWNERSHIP_CHECK,
                        )
                    )

            # Check for resource access
            resource_accesses: list[AuthorizationNode] = []
            for res_pattern in self.resource_access_patterns:
                for res_match in re.finditer(res_pattern, func_body, re.IGNORECASE):
                    res_line = line_number + func_body[: res_match.start()].count("\n")
                    resource_accesses.append(
                        AuthorizationNode(
                            node_id=f"{file_path}:{res_line}:resource",
                            node_type="resource_access",
                            name=res_match.group(0),
                            file_path=file_path,
                            line_number=res_line,
                            check_type=AuthorizationCheckType.NONE,
                        )
                    )

            # Create flows for each resource access
            for resource in resource_accesses:
                entry_point = AuthorizationNode(
                    node_id=f"{file_path}:{line_number}:entry",
                    node_type="function",
                    name=func_name,
                    file_path=file_path,
                    line_number=line_number,
                    check_type=AuthorizationCheckType.NONE,
                )

                is_protected = len(auth_nodes) > 0
                pattern = self._determine_pattern(auth_nodes)

                flows.append(
                    AuthorizationFlow(
                        flow_id=self._generate_flow_id(),
                        entry_point=entry_point,
                        auth_nodes=auth_nodes,
                        resource_access=resource,
                        is_protected=is_protected,
                        pattern=pattern,
                        confidence=0.9 if auth_nodes else 0.7,
                    )
                )

        return flows

    def _classify_check_type(self, check_string: str) -> AuthorizationCheckType:
        """Classify the type of authorization check."""
        check_lower = check_string.lower()

        if "role" in check_lower:
            return AuthorizationCheckType.ROLE_CHECK
        if "permission" in check_lower:
            return AuthorizationCheckType.PERMISSION_CHECK
        if "owner" in check_lower or "belongs_to" in check_lower:
            return AuthorizationCheckType.OWNERSHIP_CHECK
        if "jwt" in check_lower or "token" in check_lower:
            return AuthorizationCheckType.JWT_CHECK
        if "api_key" in check_lower or "apikey" in check_lower:
            return AuthorizationCheckType.API_KEY_CHECK
        if "session" in check_lower:
            return AuthorizationCheckType.SESSION_CHECK

        return AuthorizationCheckType.NONE

    def _determine_pattern(
        self,
        auth_nodes: list[AuthorizationNode],
    ) -> AuthorizationPattern:
        """Determine the authorization pattern from nodes."""
        if not auth_nodes:
            return AuthorizationPattern.NONE

        check_types = {node.check_type for node in auth_nodes}

        if AuthorizationCheckType.ROLE_CHECK in check_types:
            return AuthorizationPattern.RBAC
        if AuthorizationCheckType.OWNERSHIP_CHECK in check_types:
            return AuthorizationPattern.OWNERSHIP
        if AuthorizationCheckType.PERMISSION_CHECK in check_types:
            return AuthorizationPattern.ABAC

        return AuthorizationPattern.ACL

    async def find_authorization_gaps(
        self,
        flows: list[AuthorizationFlow],
    ) -> list[AuthorizationGap]:
        """
        Find authorization gaps and weaknesses.

        Args:
            flows: List of authorization flows to analyze

        Returns:
            List of identified gaps
        """
        gaps: list[AuthorizationGap] = []

        for flow in flows:
            # Gap 1: No authorization at all
            if not flow.is_protected:
                gaps.append(
                    AuthorizationGap(
                        gap_id=self._generate_gap_id(),
                        gap_type="missing_check",
                        severity="HIGH",
                        flow=flow,
                        description=f"Resource access in '{flow.entry_point.name}' has no authorization checks",
                        recommendation="Add authentication/authorization decorators or checks before resource access",
                        cwe_ids=["CWE-862", "CWE-863"],
                    )
                )

            # Gap 2: Resource access by ID without ownership check
            if self._is_id_based_access(flow) and not self._has_ownership_check(flow):
                gaps.append(
                    AuthorizationGap(
                        gap_id=self._generate_gap_id(),
                        gap_type="idor_risk",
                        severity="CRITICAL",
                        flow=flow,
                        description=f"ID-based resource access in '{flow.entry_point.name}' without ownership verification (IDOR risk)",
                        recommendation="Add ownership check: verify current user owns the resource before access",
                        cwe_ids=["CWE-639", "CWE-284"],
                    )
                )

            # Gap 3: Weak authorization pattern
            if flow.is_protected and flow.pattern == AuthorizationPattern.ACL:
                gaps.append(
                    AuthorizationGap(
                        gap_id=self._generate_gap_id(),
                        gap_type="weak_check",
                        severity="MEDIUM",
                        flow=flow,
                        description=f"Authorization in '{flow.entry_point.name}' uses generic ACL pattern",
                        recommendation="Consider implementing RBAC or ABAC for more granular control",
                        cwe_ids=["CWE-285"],
                    )
                )

        return gaps

    def _is_id_based_access(self, flow: AuthorizationFlow) -> bool:
        """Check if the flow involves ID-based resource access."""
        resource_name = flow.resource_access.name.lower()
        return any(
            pattern in resource_name
            for pattern in ["id", "get(", "find_by_id", "find_one", "filter"]
        )

    def _has_ownership_check(self, flow: AuthorizationFlow) -> bool:
        """Check if the flow has an ownership verification."""
        return any(
            node.check_type == AuthorizationCheckType.OWNERSHIP_CHECK
            for node in flow.auth_nodes
        )

    async def analyze_with_neptune(
        self,
        repo_path: str,
    ) -> list[AuthorizationFlow]:
        """
        Analyze authorization using Neptune graph queries.

        Uses graph traversal to find paths from entry points
        to sensitive resources.

        Args:
            repo_path: Repository path for analysis

        Returns:
            List of authorization flows from graph
        """
        if self.use_mock or self.neptune is None:
            return await self._mock_neptune_analysis()

        flows: list[AuthorizationFlow] = []

        try:
            # Query 1: Find all API endpoints
            endpoints_query = """
            g.V().has('type', 'function')
             .has('is_api_endpoint', true)
             .project('name', 'file', 'line')
             .by('name')
             .by('file_path')
             .by('line_number')
            """

            endpoints = self.neptune.query(endpoints_query)

            for endpoint in endpoints:
                # Query 2: Find auth checks in path to resource
                auth_query = f"""
                g.V().has('name', '{endpoint['name']}')
                 .repeat(out('CALLS', 'USES'))
                 .until(has('type', 'auth_check').or().loops().is(5))
                 .path()
                """

                auth_paths = self.neptune.query(auth_query)

                # Query 3: Find resource accesses
                resource_query = f"""
                g.V().has('name', '{endpoint['name']}')
                 .repeat(out('CALLS'))
                 .until(has('accesses_resource', true).or().loops().is(10))
                 .has('accesses_resource', true)
                """

                resources = self.neptune.query(resource_query)

                # Build flows from graph data
                for resource in resources:
                    auth_nodes = self._build_auth_nodes_from_paths(auth_paths)

                    flows.append(
                        AuthorizationFlow(
                            flow_id=self._generate_flow_id(),
                            entry_point=AuthorizationNode(
                                node_id=f"{endpoint['file']}:{endpoint['line']}:entry",
                                node_type="function",
                                name=endpoint["name"],
                                file_path=endpoint["file"],
                                line_number=endpoint["line"],
                                check_type=AuthorizationCheckType.NONE,
                            ),
                            auth_nodes=auth_nodes,
                            resource_access=AuthorizationNode(
                                node_id=f"{resource.get('file_path', 'unknown')}:{resource.get('line_number', 0)}:resource",
                                node_type="resource_access",
                                name=resource.get("name", "unknown"),
                                file_path=resource.get("file_path", "unknown"),
                                line_number=resource.get("line_number", 0),
                                check_type=AuthorizationCheckType.NONE,
                            ),
                            is_protected=len(auth_nodes) > 0,
                            pattern=self._determine_pattern(auth_nodes),
                        )
                    )

        except Exception as e:
            logger.error(f"Neptune analysis failed: {e}")

        return flows

    def _build_auth_nodes_from_paths(
        self,
        paths: list[Any],
    ) -> list[AuthorizationNode]:
        """Build authorization nodes from Neptune path results."""
        auth_nodes: list[AuthorizationNode] = []

        for path in paths:
            if isinstance(path, list):
                for node in path:
                    if isinstance(node, dict) and node.get("type") == "auth_check":
                        auth_nodes.append(
                            AuthorizationNode(
                                node_id=node.get("id", "unknown"),
                                node_type=node.get("check_type", "unknown"),
                                name=node.get("name", "unknown"),
                                file_path=node.get("file_path", "unknown"),
                                line_number=node.get("line_number", 0),
                                check_type=self._classify_check_type(
                                    node.get("name", "")
                                ),
                            )
                        )

        return auth_nodes

    async def _mock_neptune_analysis(self) -> list[AuthorizationFlow]:
        """Return mock flows for testing."""
        return [
            AuthorizationFlow(
                flow_id=self._generate_flow_id(),
                entry_point=AuthorizationNode(
                    node_id="mock:1:entry",
                    node_type="function",
                    name="get_user",
                    file_path="src/api/users.py",
                    line_number=42,
                    check_type=AuthorizationCheckType.NONE,
                ),
                auth_nodes=[
                    AuthorizationNode(
                        node_id="mock:40:decorator",
                        node_type="decorator",
                        name="@login_required",
                        file_path="src/api/users.py",
                        line_number=40,
                        check_type=AuthorizationCheckType.SESSION_CHECK,
                    ),
                ],
                resource_access=AuthorizationNode(
                    node_id="mock:50:resource",
                    node_type="resource_access",
                    name="User.get(user_id)",
                    file_path="src/api/users.py",
                    line_number=50,
                    check_type=AuthorizationCheckType.NONE,
                ),
                is_protected=True,
                pattern=AuthorizationPattern.ACL,
            ),
            AuthorizationFlow(
                flow_id=self._generate_flow_id(),
                entry_point=AuthorizationNode(
                    node_id="mock:100:entry",
                    node_type="function",
                    name="get_document",
                    file_path="src/api/documents.py",
                    line_number=100,
                    check_type=AuthorizationCheckType.NONE,
                ),
                auth_nodes=[],  # No auth!
                resource_access=AuthorizationNode(
                    node_id="mock:110:resource",
                    node_type="resource_access",
                    name="Document.get(doc_id)",
                    file_path="src/api/documents.py",
                    line_number=110,
                    check_type=AuthorizationCheckType.NONE,
                ),
                is_protected=False,
                pattern=AuthorizationPattern.NONE,
            ),
        ]


# =============================================================================
# Factory Function
# =============================================================================


def create_authorization_flow_analyzer(
    neptune_service: Any = None,
    use_mock: bool = False,
) -> AuthorizationFlowAnalyzer:
    """
    Create an AuthorizationFlowAnalyzer instance.

    Args:
        neptune_service: Optional Neptune service for graph queries
        use_mock: Use mock mode for testing

    Returns:
        Configured AuthorizationFlowAnalyzer
    """
    return AuthorizationFlowAnalyzer(
        neptune_service=neptune_service,
        use_mock=use_mock,
    )
