"""
API Call Chain Tracer
=====================

ADR-056 Phase 3: Data Flow Analysis

Traces API endpoints and HTTP client calls in code to map:
- Internal API endpoints (FastAPI, Flask, Django)
- External API calls (httpx, requests, aiohttp)
- API-to-API call chains
- Authentication and rate limiting patterns
"""

import ast
import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from src.services.data_flow.types import APIEndpoint

logger = logging.getLogger(__name__)

# API framework and HTTP client patterns
API_PATTERNS: list[dict[str, Any]] = [
    # FastAPI patterns
    {
        "name": "fastapi",
        "import_patterns": [
            r"from\s+fastapi\s+import",
            r"import\s+fastapi",
        ],
        "endpoint_decorators": [
            r"@(?:app|router)\.(get|post|put|delete|patch|options|head)\s*\(",
            r"@(?:api_router|app)\.(get|post|put|delete|patch|options|head)\s*\(",
        ],
        "route_patterns": [
            r"\.add_api_route\s*\(",
            r"include_router\s*\(",
        ],
    },
    # Flask patterns
    {
        "name": "flask",
        "import_patterns": [
            r"from\s+flask\s+import",
            r"import\s+flask",
        ],
        "endpoint_decorators": [
            r"@(?:app|blueprint)\.(route|get|post|put|delete|patch)\s*\(",
            r"@(?:bp|api)\.(route|get|post|put|delete|patch)\s*\(",
        ],
        "route_patterns": [
            r"\.add_url_rule\s*\(",
            r"register_blueprint\s*\(",
        ],
    },
    # Django REST Framework patterns
    {
        "name": "django_rest",
        "import_patterns": [
            r"from\s+rest_framework",
            r"from\s+django\.urls",
        ],
        "endpoint_decorators": [
            r"@api_view\s*\(\s*\[",
            r"@action\s*\(",
        ],
        "route_patterns": [
            r"path\s*\(",
            r"re_path\s*\(",
            r"url\s*\(",
        ],
    },
    # httpx client patterns (async HTTP)
    {
        "name": "httpx",
        "import_patterns": [
            r"import\s+httpx",
            r"from\s+httpx\s+import",
        ],
        "client_patterns": [
            r"httpx\.(get|post|put|delete|patch|head|options)\s*\(",
            r"httpx\.AsyncClient\s*\(",
            r"httpx\.Client\s*\(",
            r"await\s+client\.(get|post|put|delete|patch)\s*\(",
        ],
        "is_external": True,
    },
    # requests library patterns
    {
        "name": "requests",
        "import_patterns": [
            r"import\s+requests",
            r"from\s+requests\s+import",
        ],
        "client_patterns": [
            r"requests\.(get|post|put|delete|patch|head|options)\s*\(",
            r"requests\.Session\s*\(",
            r"session\.(get|post|put|delete|patch)\s*\(",
        ],
        "is_external": True,
    },
    # aiohttp client patterns
    {
        "name": "aiohttp",
        "import_patterns": [
            r"import\s+aiohttp",
            r"from\s+aiohttp\s+import",
        ],
        "client_patterns": [
            r"aiohttp\.ClientSession\s*\(",
            r"session\.(get|post|put|delete|patch)\s*\(",
            r"await\s+session\.(get|post|put|delete|patch)\s*\(",
        ],
        "is_external": True,
    },
    # urllib patterns
    {
        "name": "urllib",
        "import_patterns": [
            r"from\s+urllib\.request\s+import",
            r"import\s+urllib\.request",
        ],
        "client_patterns": [
            r"urllib\.request\.urlopen\s*\(",
            r"urlopen\s*\(",
            r"Request\s*\(",
        ],
        "is_external": True,
    },
    # boto3 API Gateway patterns
    {
        "name": "boto3_apigateway",
        "import_patterns": [
            r"boto3\.client\s*\(\s*['\"]apigateway",
            r"boto3\.client\s*\(\s*['\"]apigatewayv2",
        ],
        "client_patterns": [
            r"\.invoke\s*\(",
            r"\.create_rest_api\s*\(",
            r"\.get_rest_api\s*\(",
        ],
        "is_external": True,
    },
]

# Authentication patterns to detect
AUTH_PATTERNS = [
    (r"Bearer\s+", "bearer"),
    (r"Authorization", "header"),
    (r"api[_-]?key", "api_key"),
    (r"OAuth", "oauth"),
    (r"JWT", "jwt"),
    (r"Basic\s+", "basic"),
    (r"cognito", "cognito"),
    (r"x-api-key", "api_key"),
]

# Rate limiting patterns
RATE_LIMIT_PATTERNS = [
    r"RateLimiter",
    r"rate_limit",
    r"throttle",
    r"slowapi",
    r"limits",
    r"X-RateLimit",
]

# Timeout patterns
TIMEOUT_PATTERNS = [
    (r"timeout\s*=\s*(\d+(?:\.\d+)?)", "seconds"),
    (r"timeout\s*=\s*\(\s*(\d+(?:\.\d+)?)", "connect_seconds"),
    (r"connect_timeout\s*=\s*(\d+(?:\.\d+)?)", "connect_seconds"),
    (r"read_timeout\s*=\s*(\d+(?:\.\d+)?)", "read_seconds"),
]


class APICallTracer:
    """Traces API endpoints and HTTP client calls in code.

    Detects:
    - Internal API endpoints (FastAPI, Flask, Django)
    - External HTTP client calls (httpx, requests, aiohttp)
    - Authentication patterns
    - Rate limiting configurations
    - Timeout settings

    Attributes:
        use_mock: If True, returns mock data for testing
        patterns: List of API patterns to detect
    """

    def __init__(self, use_mock: bool = False) -> None:
        """Initialize APICallTracer.

        Args:
            use_mock: If True, returns mock data instead of real analysis
        """
        self.use_mock = use_mock
        self.patterns = API_PATTERNS

    async def trace_file(self, file_path: str) -> list[APIEndpoint]:
        """Trace API endpoints and calls in a single file.

        Args:
            file_path: Path to the Python file to analyze

        Returns:
            List of detected API endpoints
        """
        if self.use_mock:
            return self._get_mock_endpoints(file_path)

        path = Path(file_path)
        if not path.exists() or path.suffix != ".py":
            return []

        try:
            content = path.read_text(encoding="utf-8")
            return self._analyze_file(content, file_path)
        except Exception as e:
            logger.warning(f"Failed to analyze {file_path}: {e}")
            return []

    async def trace_directory(
        self,
        directory: str,
        recursive: bool = True,
        exclude_patterns: list[str] | None = None,
    ) -> list[APIEndpoint]:
        """Trace API endpoints across a directory.

        Args:
            directory: Directory path to analyze
            recursive: If True, analyze subdirectories
            exclude_patterns: Glob patterns to exclude

        Returns:
            List of all detected API endpoints
        """
        if self.use_mock:
            return self._get_mock_endpoints(directory)

        exclude_patterns = exclude_patterns or ["**/test_*.py", "**/__pycache__/**"]
        dir_path = Path(directory)
        endpoints: list[APIEndpoint] = []

        if not dir_path.exists():
            return endpoints

        pattern = "**/*.py" if recursive else "*.py"

        for py_file in dir_path.glob(pattern):
            # Skip excluded patterns
            skip = False
            for exclude in exclude_patterns:
                if py_file.match(exclude):
                    skip = True
                    break
            if skip:
                continue

            file_endpoints = await self.trace_file(str(py_file))
            endpoints.extend(file_endpoints)

        return endpoints

    def _analyze_file(self, content: str, file_path: str) -> list[APIEndpoint]:
        """Analyze file content for API patterns.

        Args:
            content: File content to analyze
            file_path: Path to the file (for reporting)

        Returns:
            List of detected API endpoints
        """
        endpoints: list[APIEndpoint] = []

        # First pass: Check which frameworks are imported
        imported_frameworks = self._detect_imported_frameworks(content)

        if not imported_frameworks:
            return endpoints

        # Parse AST for precise detection
        try:
            tree = ast.parse(content)
            ast_endpoints = self._analyze_ast(
                tree, content, file_path, imported_frameworks
            )
            endpoints.extend(ast_endpoints)
        except SyntaxError:
            # Fall back to regex for files that can't be parsed
            regex_endpoints = self._analyze_with_regex(
                content, file_path, imported_frameworks
            )
            endpoints.extend(regex_endpoints)

        return endpoints

    def _detect_imported_frameworks(self, content: str) -> set[str]:
        """Detect which API frameworks are imported in the file.

        Args:
            content: File content

        Returns:
            Set of imported framework names
        """
        imported = set()

        for pattern_config in self.patterns:
            for import_pattern in pattern_config["import_patterns"]:
                if re.search(import_pattern, content):
                    imported.add(pattern_config["name"])
                    break

        return imported

    def _analyze_ast(
        self,
        tree: ast.AST,
        content: str,
        file_path: str,
        frameworks: set[str],
    ) -> list[APIEndpoint]:
        """Analyze AST for API patterns.

        Args:
            tree: Parsed AST
            content: Original file content
            file_path: Path to file
            frameworks: Set of imported frameworks

        Returns:
            List of detected API endpoints
        """
        endpoints: list[APIEndpoint] = []
        lines = content.split("\n")

        for node in ast.walk(tree):
            # Check decorated functions (endpoints)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                endpoint = self._check_function_decorators(
                    node, file_path, lines, frameworks
                )
                if endpoint:
                    endpoints.append(endpoint)

            # Check function calls (HTTP clients)
            elif isinstance(node, ast.Call):
                endpoint = self._check_http_call(node, file_path, lines, frameworks)
                if endpoint:
                    endpoints.append(endpoint)

        return endpoints

    def _check_function_decorators(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        lines: list[str],
        frameworks: set[str],
    ) -> APIEndpoint | None:
        """Check function decorators for endpoint patterns.

        Args:
            node: Function definition node
            file_path: Path to file
            lines: File lines for context
            frameworks: Imported frameworks

        Returns:
            APIEndpoint if found, None otherwise
        """
        for decorator in node.decorator_list:
            # Handle @app.get("/path") style decorators
            if isinstance(decorator, ast.Call) and isinstance(
                decorator.func, ast.Attribute
            ):
                method = decorator.func.attr.upper()
                if method in {
                    "GET",
                    "POST",
                    "PUT",
                    "DELETE",
                    "PATCH",
                    "OPTIONS",
                    "HEAD",
                    "ROUTE",
                }:
                    url_pattern = self._extract_url_from_decorator(decorator)
                    if url_pattern:
                        # If ROUTE, try to extract method from arguments
                        if method == "ROUTE":
                            method = self._extract_method_from_route(decorator) or "GET"

                        endpoint_id = self._generate_endpoint_id(
                            file_path, node.lineno, url_pattern
                        )

                        # Detect auth type from function body
                        auth_type = self._detect_auth_in_function(node)

                        # Detect rate limiting
                        rate_limit = self._detect_rate_limit_in_function(
                            node, decorator
                        )

                        return APIEndpoint(
                            endpoint_id=endpoint_id,
                            url_pattern=url_pattern,
                            method=method,
                            source_file=file_path,
                            source_line=node.lineno,
                            is_internal=True,
                            is_external=False,
                            auth_type=auth_type,
                            rate_limit=rate_limit,
                            confidence=0.95,
                        )

            # Handle @api_view(['GET', 'POST']) style (Django REST)
            elif isinstance(decorator, ast.Call) and isinstance(
                decorator.func, ast.Name
            ):
                if decorator.func.id == "api_view":
                    methods = self._extract_methods_from_api_view(decorator)
                    url_pattern = (
                        f"/{node.name}"  # Django uses function name as default
                    )

                    for method in methods:
                        endpoint_id = self._generate_endpoint_id(
                            file_path, node.lineno, url_pattern
                        )
                        return APIEndpoint(
                            endpoint_id=endpoint_id,
                            url_pattern=url_pattern,
                            method=method,
                            source_file=file_path,
                            source_line=node.lineno,
                            is_internal=True,
                            is_external=False,
                            confidence=0.85,
                        )

        return None

    def _check_http_call(
        self,
        node: ast.Call,
        file_path: str,
        lines: list[str],
        frameworks: set[str],
    ) -> APIEndpoint | None:
        """Check if call is an HTTP client request.

        Args:
            node: Call node
            file_path: Path to file
            lines: File lines
            frameworks: Imported frameworks

        Returns:
            APIEndpoint if HTTP call found, None otherwise
        """
        # Check for httpx/requests style calls: requests.get(url)
        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in {
                "get",
                "post",
                "put",
                "delete",
                "patch",
                "head",
                "options",
            }:
                # Check if it's from an HTTP client library
                if isinstance(node.func.value, ast.Name):
                    lib_name = node.func.value.id
                    if lib_name in {"requests", "httpx", "session", "client"}:
                        url = self._extract_url_from_call(node)
                        if url:
                            endpoint_id = self._generate_endpoint_id(
                                file_path, node.lineno, url
                            )
                            timeout = self._extract_timeout_from_call(node)

                            return APIEndpoint(
                                endpoint_id=endpoint_id,
                                url_pattern=url,
                                method=attr_name.upper(),
                                source_file=file_path,
                                source_line=node.lineno,
                                is_internal=False,
                                is_external=True,
                                timeout_ms=int(timeout * 1000) if timeout else None,
                                confidence=0.9,
                            )

        return None

    def _extract_url_from_decorator(self, decorator: ast.Call) -> str | None:
        """Extract URL pattern from decorator arguments.

        Args:
            decorator: Decorator call node

        Returns:
            URL pattern or None
        """
        # First positional argument is usually the path
        if decorator.args:
            first_arg = decorator.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                return first_arg.value

        # Check path keyword argument
        for keyword in decorator.keywords:
            if keyword.arg == "path" and isinstance(keyword.value, ast.Constant):
                return str(keyword.value.value)

        return None

    def _extract_method_from_route(self, decorator: ast.Call) -> str | None:
        """Extract HTTP method from @route decorator.

        Args:
            decorator: Route decorator call

        Returns:
            HTTP method or None
        """
        for keyword in decorator.keywords:
            if keyword.arg == "methods":
                if isinstance(keyword.value, ast.List) and keyword.value.elts:
                    first_method = keyword.value.elts[0]
                    if isinstance(first_method, ast.Constant):
                        return str(first_method.value).upper()
        return None

    def _extract_methods_from_api_view(self, decorator: ast.Call) -> list[str]:
        """Extract methods from @api_view decorator.

        Args:
            decorator: api_view decorator call

        Returns:
            List of HTTP methods
        """
        methods = []
        if decorator.args and isinstance(decorator.args[0], ast.List):
            for elt in decorator.args[0].elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    methods.append(elt.value.upper())
        return methods or ["GET"]

    def _extract_url_from_call(self, node: ast.Call) -> str | None:
        """Extract URL from HTTP client call.

        Args:
            node: Call node

        Returns:
            URL or None
        """
        # First positional argument is usually the URL
        if node.args:
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                return first_arg.value
            elif isinstance(first_arg, ast.JoinedStr):
                # f-string - extract static parts
                return self._extract_fstring_url(first_arg)

        # Check url keyword argument
        for keyword in node.keywords:
            if keyword.arg == "url" and isinstance(keyword.value, ast.Constant):
                return str(keyword.value.value)

        return None

    def _extract_fstring_url(self, node: ast.JoinedStr) -> str:
        """Extract URL pattern from f-string.

        Args:
            node: JoinedStr (f-string) node

        Returns:
            URL pattern with placeholders
        """
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                # Replace variable with placeholder
                parts.append("{param}")
        return "".join(parts)

    def _extract_timeout_from_call(self, node: ast.Call) -> float | None:
        """Extract timeout from HTTP call.

        Args:
            node: Call node

        Returns:
            Timeout in seconds or None
        """
        for keyword in node.keywords:
            if keyword.arg == "timeout":
                if isinstance(keyword.value, ast.Constant):
                    try:
                        return float(keyword.value.value)
                    except (TypeError, ValueError):
                        pass
                elif isinstance(keyword.value, ast.Tuple) and keyword.value.elts:
                    # timeout=(connect, read)
                    first = keyword.value.elts[0]
                    if isinstance(first, ast.Constant):
                        try:
                            return float(first.value)
                        except (TypeError, ValueError):
                            pass
        return None

    def _detect_auth_in_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> str | None:
        """Detect authentication type in function.

        Args:
            node: Function node

        Returns:
            Auth type or None
        """
        # Check function arguments for common auth patterns
        for arg in node.args.args:
            arg_name = arg.arg.lower()
            if "token" in arg_name or "auth" in arg_name:
                return "bearer"
            if "api_key" in arg_name:
                return "api_key"
            if "current_user" in arg_name:
                return "session"

        # Check decorators for auth dependencies
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                decorator_source = ast.unparse(decorator)
                for pattern, auth_type in AUTH_PATTERNS:
                    if re.search(pattern, decorator_source, re.IGNORECASE):
                        return auth_type

        return None

    def _detect_rate_limit_in_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        endpoint_decorator: ast.Call,
    ) -> dict[str, Any] | None:
        """Detect rate limiting configuration.

        Args:
            node: Function node
            endpoint_decorator: The endpoint decorator

        Returns:
            Rate limit config or None
        """
        # Check for rate limit decorators
        for decorator in node.decorator_list:
            decorator_source = ast.unparse(decorator)
            for pattern in RATE_LIMIT_PATTERNS:
                if re.search(pattern, decorator_source, re.IGNORECASE):
                    # Try to extract rate limit values
                    match = re.search(r"(\d+)\s*/\s*(\w+)", decorator_source)
                    if match:
                        return {
                            "requests": int(match.group(1)),
                            "period": match.group(2),
                        }
                    return {"detected": True}

        return None

    def _analyze_with_regex(
        self,
        content: str,
        file_path: str,
        frameworks: set[str],
    ) -> list[APIEndpoint]:
        """Analyze file with regex when AST parsing fails.

        Args:
            content: File content
            file_path: Path to file
            frameworks: Imported frameworks

        Returns:
            List of detected endpoints
        """
        endpoints: list[APIEndpoint] = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            for pattern_config in self.patterns:
                if pattern_config["name"] not in frameworks:
                    continue

                # Check endpoint decorators
                if "endpoint_decorators" in pattern_config:
                    for pattern in pattern_config["endpoint_decorators"]:
                        match = re.search(pattern, line)
                        if match:
                            method = match.group(1).upper() if match.groups() else "GET"
                            url_match = re.search(r"['\"]([^'\"]+)['\"]", line)
                            url_pattern = (
                                url_match.group(1) if url_match else "/unknown"
                            )

                            endpoint_id = self._generate_endpoint_id(
                                file_path, i, url_pattern
                            )
                            endpoints.append(
                                APIEndpoint(
                                    endpoint_id=endpoint_id,
                                    url_pattern=url_pattern,
                                    method=method,
                                    source_file=file_path,
                                    source_line=i,
                                    is_internal=True,
                                    is_external=False,
                                    confidence=0.7,  # Lower confidence for regex
                                )
                            )
                            break

                # Check HTTP client patterns
                if "client_patterns" in pattern_config:
                    for pattern in pattern_config["client_patterns"]:
                        match = re.search(pattern, line)
                        if match:
                            method = match.group(1).upper() if match.groups() else "GET"
                            url_match = re.search(r"['\"]([^'\"]+)['\"]", line)
                            url_pattern = (
                                url_match.group(1) if url_match else "external"
                            )

                            endpoint_id = self._generate_endpoint_id(
                                file_path, i, url_pattern
                            )
                            endpoints.append(
                                APIEndpoint(
                                    endpoint_id=endpoint_id,
                                    url_pattern=url_pattern,
                                    method=method,
                                    source_file=file_path,
                                    source_line=i,
                                    is_internal=False,
                                    is_external=pattern_config.get("is_external", True),
                                    confidence=0.6,
                                )
                            )
                            break

        return endpoints

    def _generate_endpoint_id(self, file_path: str, line: int, url: str) -> str:
        """Generate unique endpoint ID.

        Args:
            file_path: Source file path
            line: Line number
            url: URL pattern

        Returns:
            Unique endpoint identifier
        """
        content = f"{file_path}:{line}:{url}"
        return f"api-{hashlib.sha256(content.encode()).hexdigest()[:12]}"

    def _get_mock_endpoints(self, path: str) -> list[APIEndpoint]:
        """Return mock endpoints for testing.

        Args:
            path: File or directory path

        Returns:
            List of mock API endpoints
        """
        return [
            APIEndpoint(
                endpoint_id="api-mock-001",
                url_pattern="/api/v1/users",
                method="GET",
                source_file=f"{path}/api/users.py",
                source_line=25,
                is_internal=True,
                is_external=False,
                auth_type="bearer",
                rate_limit={"requests": 100, "period": "minute"},
                confidence=0.95,
            ),
            APIEndpoint(
                endpoint_id="api-mock-002",
                url_pattern="/api/v1/users/{user_id}",
                method="GET",
                source_file=f"{path}/api/users.py",
                source_line=45,
                is_internal=True,
                is_external=False,
                auth_type="bearer",
                confidence=0.95,
            ),
            APIEndpoint(
                endpoint_id="api-mock-003",
                url_pattern="/api/v1/users",
                method="POST",
                source_file=f"{path}/api/users.py",
                source_line=65,
                is_internal=True,
                is_external=False,
                auth_type="bearer",
                request_schema={"name": "string", "email": "string"},
                confidence=0.95,
            ),
            APIEndpoint(
                endpoint_id="api-mock-004",
                url_pattern="https://api.github.com/repos/{owner}/{repo}",
                method="GET",
                source_file=f"{path}/services/github_client.py",
                source_line=30,
                is_internal=False,
                is_external=True,
                auth_type="bearer",
                timeout_ms=30000,
                confidence=0.9,
            ),
            APIEndpoint(
                endpoint_id="api-mock-005",
                url_pattern="https://api.stripe.com/v1/charges",
                method="POST",
                source_file=f"{path}/services/payment_service.py",
                source_line=55,
                is_internal=False,
                is_external=True,
                auth_type="api_key",
                timeout_ms=60000,
                confidence=0.9,
            ),
        ]
