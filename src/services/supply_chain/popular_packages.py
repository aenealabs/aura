"""
Project Aura - Popular Packages Database

Top packages per ecosystem for typosquatting detection. Contains the most
popular packages from npm, PyPI, Go, and Cargo registries to detect
potential dependency confusion attacks.

Usage:
    from src.services.supply_chain.popular_packages import (
        get_popular_packages,
        is_popular_package,
        get_similar_popular_packages,
    )

    # Check if package is popular
    if is_popular_package("requests", "pypi"):
        print("This is a popular package")

    # Find similar popular packages (potential typosquatting targets)
    similar = get_similar_popular_packages("requets", "pypi", max_distance=2)
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

# Levenshtein distance implementation (fallback if python-Levenshtein not installed)
try:
    from Levenshtein import distance as levenshtein_distance
except ImportError:

    def levenshtein_distance(s1: str, s2: str) -> int:
        """Pure Python Levenshtein distance implementation."""
        if len(s1) < len(s2):
            return levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]


@dataclass
class PopularPackage:
    """Metadata for a popular package."""

    name: str
    ecosystem: str
    downloads_weekly: int
    description: str
    is_namespace: bool = False  # True if this is an organization namespace


# Top 100 PyPI packages by weekly downloads (as of 2025)
PYPI_PACKAGES: list[PopularPackage] = [
    PopularPackage("boto3", "pypi", 450_000_000, "AWS SDK for Python", False),
    PopularPackage("urllib3", "pypi", 380_000_000, "HTTP client", False),
    PopularPackage("requests", "pypi", 350_000_000, "HTTP library", False),
    PopularPackage("setuptools", "pypi", 320_000_000, "Build system", False),
    PopularPackage("certifi", "pypi", 310_000_000, "SSL certificates", False),
    PopularPackage("typing-extensions", "pypi", 300_000_000, "Typing backports", False),
    PopularPackage("idna", "pypi", 290_000_000, "Internationalized domains", False),
    PopularPackage(
        "charset-normalizer", "pypi", 280_000_000, "Encoding detection", False
    ),
    PopularPackage("python-dateutil", "pypi", 270_000_000, "Date utilities", False),
    PopularPackage("packaging", "pypi", 260_000_000, "Package utilities", False),
    PopularPackage("pyyaml", "pypi", 250_000_000, "YAML parser", False),
    PopularPackage("numpy", "pypi", 240_000_000, "Numerical computing", False),
    PopularPackage("six", "pypi", 230_000_000, "Python 2/3 compatibility", False),
    PopularPackage("botocore", "pypi", 220_000_000, "AWS SDK core", False),
    PopularPackage("s3transfer", "pypi", 210_000_000, "S3 transfer manager", False),
    PopularPackage("jmespath", "pypi", 200_000_000, "JSON query language", False),
    PopularPackage("pip", "pypi", 190_000_000, "Package installer", False),
    PopularPackage("wheel", "pypi", 180_000_000, "Built package format", False),
    PopularPackage("attrs", "pypi", 170_000_000, "Class helpers", False),
    PopularPackage("cryptography", "pypi", 160_000_000, "Cryptographic recipes", False),
    PopularPackage("cffi", "pypi", 155_000_000, "C FFI", False),
    PopularPackage("pycparser", "pypi", 150_000_000, "C parser", False),
    PopularPackage("platformdirs", "pypi", 145_000_000, "Platform directories", False),
    PopularPackage("filelock", "pypi", 140_000_000, "File locking", False),
    PopularPackage("pytz", "pypi", 135_000_000, "Timezone definitions", False),
    PopularPackage("click", "pypi", 130_000_000, "CLI framework", False),
    PopularPackage("importlib-metadata", "pypi", 125_000_000, "Metadata access", False),
    PopularPackage("zipp", "pypi", 120_000_000, "Zipfile utilities", False),
    PopularPackage("jsonschema", "pypi", 115_000_000, "JSON Schema validator", False),
    PopularPackage("markupsafe", "pypi", 110_000_000, "Safe string markup", False),
    PopularPackage("jinja2", "pypi", 105_000_000, "Template engine", False),
    PopularPackage("pyparsing", "pypi", 100_000_000, "Parsing library", False),
    PopularPackage("pydantic", "pypi", 95_000_000, "Data validation", False),
    PopularPackage("sqlalchemy", "pypi", 90_000_000, "SQL toolkit", False),
    PopularPackage("aiohttp", "pypi", 85_000_000, "Async HTTP", False),
    PopularPackage("tomli", "pypi", 80_000_000, "TOML parser", False),
    PopularPackage("wrapt", "pypi", 75_000_000, "Decorator utilities", False),
    PopularPackage("decorator", "pypi", 70_000_000, "Decorator helpers", False),
    PopularPackage("multidict", "pypi", 65_000_000, "Multivalue dict", False),
    PopularPackage("yarl", "pypi", 60_000_000, "URL library", False),
    PopularPackage("frozenlist", "pypi", 58_000_000, "Frozen list", False),
    PopularPackage("aiosignal", "pypi", 56_000_000, "Async signals", False),
    PopularPackage("async-timeout", "pypi", 54_000_000, "Async timeout", False),
    PopularPackage("pandas", "pypi", 52_000_000, "Data analysis", False),
    PopularPackage("protobuf", "pypi", 50_000_000, "Protocol buffers", False),
    PopularPackage("grpcio", "pypi", 48_000_000, "gRPC framework", False),
    PopularPackage("google-api-core", "pypi", 46_000_000, "Google API core", False),
    PopularPackage(
        "googleapis-common-protos", "pypi", 44_000_000, "Google protos", False
    ),
    PopularPackage("pyasn1", "pypi", 42_000_000, "ASN.1 library", False),
    PopularPackage("rsa", "pypi", 40_000_000, "RSA implementation", False),
    PopularPackage("cachetools", "pypi", 38_000_000, "Caching utilities", False),
    PopularPackage("google-auth", "pypi", 36_000_000, "Google authentication", False),
    PopularPackage("oauthlib", "pypi", 34_000_000, "OAuth library", False),
    PopularPackage(
        "requests-oauthlib", "pypi", 32_000_000, "OAuth for requests", False
    ),
    PopularPackage("pyopenssl", "pypi", 30_000_000, "OpenSSL wrapper", False),
    PopularPackage("werkzeug", "pypi", 28_000_000, "WSGI utilities", False),
    PopularPackage("flask", "pypi", 26_000_000, "Web framework", False),
    PopularPackage("django", "pypi", 24_000_000, "Web framework", False),
    PopularPackage("fastapi", "pypi", 22_000_000, "API framework", False),
    PopularPackage("uvicorn", "pypi", 20_000_000, "ASGI server", False),
    PopularPackage("starlette", "pypi", 18_000_000, "ASGI framework", False),
    PopularPackage("httpx", "pypi", 16_000_000, "HTTP client", False),
    PopularPackage("httpcore", "pypi", 15_000_000, "HTTP core", False),
    PopularPackage("anyio", "pypi", 14_000_000, "Async I/O", False),
    PopularPackage("sniffio", "pypi", 13_000_000, "Async detection", False),
    PopularPackage("h11", "pypi", 12_000_000, "HTTP/1.1 parser", False),
    PopularPackage("pytest", "pypi", 11_000_000, "Testing framework", False),
    PopularPackage("pluggy", "pypi", 10_500_000, "Plugin system", False),
    PopularPackage("iniconfig", "pypi", 10_000_000, "INI parser", False),
    PopularPackage("exceptiongroup", "pypi", 9_500_000, "Exception groups", False),
    PopularPackage("coverage", "pypi", 9_000_000, "Code coverage", False),
    PopularPackage("mypy", "pypi", 8_500_000, "Type checker", False),
    PopularPackage("black", "pypi", 8_000_000, "Code formatter", False),
    PopularPackage("flake8", "pypi", 7_500_000, "Linter", False),
    PopularPackage("isort", "pypi", 7_000_000, "Import sorter", False),
    PopularPackage("pylint", "pypi", 6_500_000, "Linter", False),
    PopularPackage("scipy", "pypi", 6_000_000, "Scientific computing", False),
    PopularPackage("matplotlib", "pypi", 5_500_000, "Plotting library", False),
    PopularPackage("pillow", "pypi", 5_000_000, "Image processing", False),
    PopularPackage("scikit-learn", "pypi", 4_500_000, "Machine learning", False),
    PopularPackage("tensorflow", "pypi", 4_000_000, "ML framework", False),
    PopularPackage("torch", "pypi", 3_500_000, "ML framework", False),
    PopularPackage("transformers", "pypi", 3_000_000, "NLP models", False),
    PopularPackage("openai", "pypi", 2_500_000, "OpenAI API", False),
    PopularPackage("anthropic", "pypi", 2_000_000, "Anthropic API", False),
    PopularPackage("langchain", "pypi", 1_800_000, "LLM framework", False),
    PopularPackage("redis", "pypi", 1_600_000, "Redis client", False),
    PopularPackage("celery", "pypi", 1_400_000, "Task queue", False),
    PopularPackage("psycopg2", "pypi", 1_200_000, "PostgreSQL adapter", False),
    PopularPackage("pymongo", "pypi", 1_000_000, "MongoDB driver", False),
]

# Top 100 npm packages by weekly downloads
NPM_PACKAGES: list[PopularPackage] = [
    PopularPackage("lodash", "npm", 50_000_000, "Utility library", False),
    PopularPackage("react", "npm", 45_000_000, "UI library", False),
    PopularPackage("axios", "npm", 40_000_000, "HTTP client", False),
    PopularPackage("express", "npm", 35_000_000, "Web framework", False),
    PopularPackage("typescript", "npm", 32_000_000, "Type system", False),
    PopularPackage("chalk", "npm", 30_000_000, "Terminal colors", False),
    PopularPackage("moment", "npm", 28_000_000, "Date library", False),
    PopularPackage("commander", "npm", 26_000_000, "CLI framework", False),
    PopularPackage("debug", "npm", 24_000_000, "Debugging utility", False),
    PopularPackage("uuid", "npm", 22_000_000, "UUID generation", False),
    PopularPackage("async", "npm", 20_000_000, "Async utilities", False),
    PopularPackage("fs-extra", "npm", 18_000_000, "File system", False),
    PopularPackage("glob", "npm", 17_000_000, "Pattern matching", False),
    PopularPackage("semver", "npm", 16_000_000, "Version parsing", False),
    PopularPackage("minimist", "npm", 15_000_000, "Argument parsing", False),
    PopularPackage("yargs", "npm", 14_000_000, "CLI builder", False),
    PopularPackage("underscore", "npm", 13_000_000, "Utility library", False),
    PopularPackage("request", "npm", 12_000_000, "HTTP client", False),
    PopularPackage("bluebird", "npm", 11_000_000, "Promise library", False),
    PopularPackage("inquirer", "npm", 10_500_000, "CLI prompts", False),
    PopularPackage("webpack", "npm", 10_000_000, "Bundler", False),
    PopularPackage("babel", "npm", 9_500_000, "Transpiler", False),
    PopularPackage("jest", "npm", 9_000_000, "Testing framework", False),
    PopularPackage("mocha", "npm", 8_500_000, "Testing framework", False),
    PopularPackage("eslint", "npm", 8_000_000, "Linter", False),
    PopularPackage("prettier", "npm", 7_500_000, "Formatter", False),
    PopularPackage("dotenv", "npm", 7_000_000, "Env loader", False),
    PopularPackage("cors", "npm", 6_500_000, "CORS middleware", False),
    PopularPackage("body-parser", "npm", 6_000_000, "Body parsing", False),
    PopularPackage("mongoose", "npm", 5_500_000, "MongoDB ODM", False),
    PopularPackage("next", "npm", 5_000_000, "React framework", False),
    PopularPackage("vue", "npm", 4_500_000, "UI framework", False),
    PopularPackage("angular", "npm", 4_000_000, "UI framework", False),
    PopularPackage("rxjs", "npm", 3_800_000, "Reactive extensions", False),
    PopularPackage("socket.io", "npm", 3_600_000, "WebSocket library", False),
    PopularPackage("jsonwebtoken", "npm", 3_400_000, "JWT library", False),
    PopularPackage("bcrypt", "npm", 3_200_000, "Password hashing", False),
    PopularPackage("passport", "npm", 3_000_000, "Authentication", False),
    PopularPackage("nodemon", "npm", 2_800_000, "Dev server", False),
    PopularPackage("pm2", "npm", 2_600_000, "Process manager", False),
    PopularPackage("mysql", "npm", 2_400_000, "MySQL driver", False),
    PopularPackage("pg", "npm", 2_200_000, "PostgreSQL driver", False),
    PopularPackage("redis", "npm", 2_000_000, "Redis client", False),
    PopularPackage("aws-sdk", "npm", 1_800_000, "AWS SDK", False),
    PopularPackage("graphql", "npm", 1_600_000, "GraphQL", False),
    PopularPackage("apollo-server", "npm", 1_400_000, "GraphQL server", False),
    PopularPackage("prisma", "npm", 1_200_000, "Database ORM", False),
    PopularPackage("tailwindcss", "npm", 1_000_000, "CSS framework", False),
]

# Top Go modules
GO_PACKAGES: list[PopularPackage] = [
    PopularPackage("github.com/gin-gonic/gin", "go", 80_000, "Web framework", True),
    PopularPackage("github.com/gorilla/mux", "go", 70_000, "HTTP router", True),
    PopularPackage("github.com/sirupsen/logrus", "go", 65_000, "Logging", True),
    PopularPackage("github.com/stretchr/testify", "go", 60_000, "Testing", True),
    PopularPackage("github.com/spf13/cobra", "go", 55_000, "CLI framework", True),
    PopularPackage("github.com/spf13/viper", "go", 50_000, "Configuration", True),
    PopularPackage("github.com/go-redis/redis", "go", 45_000, "Redis client", True),
    PopularPackage("github.com/jinzhu/gorm", "go", 40_000, "ORM", True),
    PopularPackage(
        "github.com/prometheus/client_golang", "go", 38_000, "Metrics", True
    ),
    PopularPackage("github.com/aws/aws-sdk-go", "go", 36_000, "AWS SDK", True),
    PopularPackage("github.com/kubernetes/client-go", "go", 34_000, "K8s client", True),
    PopularPackage("github.com/grpc/grpc-go", "go", 32_000, "gRPC", True),
    PopularPackage("github.com/golang/protobuf", "go", 30_000, "Protobuf", True),
    PopularPackage("github.com/uber-go/zap", "go", 28_000, "Logging", True),
    PopularPackage("github.com/labstack/echo", "go", 26_000, "Web framework", True),
    PopularPackage("github.com/go-kit/kit", "go", 24_000, "Microservices", True),
    PopularPackage("github.com/hashicorp/terraform", "go", 22_000, "IaC", True),
    PopularPackage("github.com/hashicorp/consul", "go", 20_000, "Service mesh", True),
    PopularPackage("github.com/hashicorp/vault", "go", 18_000, "Secrets", True),
    PopularPackage("github.com/docker/docker", "go", 16_000, "Container runtime", True),
]

# Top Cargo (Rust) crates
CARGO_PACKAGES: list[PopularPackage] = [
    PopularPackage("serde", "cargo", 150_000_000, "Serialization", False),
    PopularPackage("serde_json", "cargo", 120_000_000, "JSON support", False),
    PopularPackage("tokio", "cargo", 100_000_000, "Async runtime", False),
    PopularPackage("rand", "cargo", 90_000_000, "Random numbers", False),
    PopularPackage("clap", "cargo", 80_000_000, "CLI parsing", False),
    PopularPackage("log", "cargo", 75_000_000, "Logging facade", False),
    PopularPackage("env_logger", "cargo", 70_000_000, "Logging impl", False),
    PopularPackage("reqwest", "cargo", 65_000_000, "HTTP client", False),
    PopularPackage("regex", "cargo", 60_000_000, "Regular expressions", False),
    PopularPackage("chrono", "cargo", 55_000_000, "Date/time", False),
    PopularPackage("hyper", "cargo", 50_000_000, "HTTP library", False),
    PopularPackage("futures", "cargo", 45_000_000, "Async primitives", False),
    PopularPackage("anyhow", "cargo", 40_000_000, "Error handling", False),
    PopularPackage("thiserror", "cargo", 38_000_000, "Error derive", False),
    PopularPackage("async-trait", "cargo", 36_000_000, "Async traits", False),
    PopularPackage("tracing", "cargo", 34_000_000, "Instrumentation", False),
    PopularPackage("bytes", "cargo", 32_000_000, "Byte utilities", False),
    PopularPackage("parking_lot", "cargo", 30_000_000, "Synchronization", False),
    PopularPackage("once_cell", "cargo", 28_000_000, "Lazy statics", False),
    PopularPackage("itertools", "cargo", 26_000_000, "Iterator adapters", False),
]

# Common internal namespace prefixes that attackers might try to hijack
COMMON_INTERNAL_PREFIXES: list[str] = [
    "internal-",
    "private-",
    "corp-",
    "company-",
    "@internal/",
    "@private/",
    "@corp/",
    "mycompany-",
    "acme-",
    "bigco-",
]


def get_all_packages() -> dict[str, list[PopularPackage]]:
    """Get all popular packages organized by ecosystem."""
    return {
        "pypi": PYPI_PACKAGES,
        "npm": NPM_PACKAGES,
        "go": GO_PACKAGES,
        "cargo": CARGO_PACKAGES,
    }


@lru_cache(maxsize=1)
def _build_package_index() -> dict[str, dict[str, PopularPackage]]:
    """Build an index of packages by ecosystem and name for fast lookup."""
    index: dict[str, dict[str, PopularPackage]] = {}
    for ecosystem, packages in get_all_packages().items():
        index[ecosystem] = {}
        for pkg in packages:
            # Store by lowercase name for case-insensitive lookup
            index[ecosystem][pkg.name.lower()] = pkg
    return index


def get_popular_packages(ecosystem: str) -> list[PopularPackage]:
    """Get popular packages for a specific ecosystem.

    Args:
        ecosystem: One of 'pypi', 'npm', 'go', 'cargo'

    Returns:
        List of popular packages for the ecosystem
    """
    packages = get_all_packages()
    return packages.get(ecosystem.lower(), [])


def is_popular_package(name: str, ecosystem: str) -> bool:
    """Check if a package name is a popular package in the ecosystem.

    Args:
        name: Package name to check
        ecosystem: Ecosystem to check in

    Returns:
        True if the package is in the popular packages list
    """
    index = _build_package_index()
    ecosystem_index = index.get(ecosystem.lower(), {})
    return name.lower() in ecosystem_index


def get_package_info(name: str, ecosystem: str) -> Optional[PopularPackage]:
    """Get information about a popular package.

    Args:
        name: Package name
        ecosystem: Ecosystem

    Returns:
        PopularPackage if found, None otherwise
    """
    index = _build_package_index()
    ecosystem_index = index.get(ecosystem.lower(), {})
    return ecosystem_index.get(name.lower())


def get_similar_popular_packages(
    name: str,
    ecosystem: str,
    max_distance: int = 2,
    max_results: int = 5,
) -> list[tuple[PopularPackage, int]]:
    """Find popular packages with names similar to the given name.

    Uses Levenshtein distance to find potential typosquatting targets.

    Args:
        name: Package name to check
        ecosystem: Ecosystem to search
        max_distance: Maximum Levenshtein distance (default 2)
        max_results: Maximum number of results to return

    Returns:
        List of (PopularPackage, distance) tuples, sorted by distance
    """
    similar: list[tuple[PopularPackage, int]] = []
    packages = get_popular_packages(ecosystem)

    name_lower = name.lower()

    for pkg in packages:
        pkg_name_lower = pkg.name.lower()

        # Skip exact matches
        if name_lower == pkg_name_lower:
            continue

        # Calculate distance
        dist = levenshtein_distance(name_lower, pkg_name_lower)

        if dist <= max_distance:
            similar.append((pkg, dist))

    # Sort by distance (closest first), then by downloads (most popular first)
    similar.sort(key=lambda x: (x[1], -x[0].downloads_weekly))

    return similar[:max_results]


def check_common_typos(name: str) -> list[str]:
    """Generate common typo variants of a package name.

    Args:
        name: Original package name

    Returns:
        List of common typo variants
    """
    variants: list[str] = []
    name_lower = name.lower()

    # Character swaps (adjacent characters)
    for i in range(len(name_lower) - 1):
        swapped = (
            name_lower[:i] + name_lower[i + 1] + name_lower[i] + name_lower[i + 2 :]
        )
        if swapped != name_lower:
            variants.append(swapped)

    # Missing characters
    for i in range(len(name_lower)):
        missing = name_lower[:i] + name_lower[i + 1 :]
        if missing:
            variants.append(missing)

    # Doubled characters
    for i in range(len(name_lower)):
        doubled = name_lower[:i] + name_lower[i] + name_lower[i:]
        variants.append(doubled)

    # Common substitutions
    substitutions = {
        "0": "o",
        "o": "0",
        "1": "l",
        "l": "1",
        "i": "1",
        "s": "5",
        "5": "s",
        "e": "3",
        "3": "e",
        "-": "_",
        "_": "-",
    }

    for i, char in enumerate(name_lower):
        if char in substitutions:
            substituted = name_lower[:i] + substitutions[char] + name_lower[i + 1 :]
            variants.append(substituted)

    return list(set(variants))


def is_namespace_match(
    package_name: str,
    internal_prefixes: list[str],
) -> tuple[bool, Optional[str]]:
    """Check if a package name matches an internal namespace pattern.

    Args:
        package_name: Package name to check
        internal_prefixes: List of internal namespace prefixes

    Returns:
        Tuple of (is_match, matched_prefix)
    """
    name_lower = package_name.lower()

    # Check provided prefixes
    for prefix in internal_prefixes:
        if name_lower.startswith(prefix.lower()):
            return True, prefix

    # Check common internal prefixes
    for prefix in COMMON_INTERNAL_PREFIXES:
        if name_lower.startswith(prefix.lower()):
            return True, prefix

    return False, None
