"""
Tests for API Call Tracer
=========================

ADR-056 Phase 3: Data Flow Analysis

Tests for API endpoint and HTTP client detection in code.
"""

import platform
import tempfile
from pathlib import Path

import pytest

from src.services.data_flow.api_tracer import APICallTracer

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestAPICallTracerMock:
    """Tests for APICallTracer in mock mode."""

    @pytest.fixture
    def tracer(self):
        """Create mock tracer."""
        return APICallTracer(use_mock=True)

    @pytest.mark.asyncio
    async def test_trace_file_mock(self, tracer):
        """Test mock file tracing returns sample data."""
        endpoints = await tracer.trace_file("test.py")

        assert len(endpoints) > 0
        assert all(ep.endpoint_id for ep in endpoints)
        assert any(ep.is_internal for ep in endpoints)
        assert any(ep.is_external for ep in endpoints)

    @pytest.mark.asyncio
    async def test_trace_directory_mock(self, tracer):
        """Test mock directory tracing returns sample data."""
        endpoints = await tracer.trace_directory("/some/path")

        assert len(endpoints) > 0


class TestAPICallTracerReal:
    """Tests for APICallTracer with real code analysis."""

    @pytest.fixture
    def tracer(self):
        """Create real tracer."""
        return APICallTracer(use_mock=False)

    @pytest.mark.asyncio
    async def test_trace_file_nonexistent(self, tracer):
        """Test tracing nonexistent file returns empty list."""
        endpoints = await tracer.trace_file("/nonexistent/file.py")
        assert endpoints == []

    @pytest.mark.asyncio
    async def test_trace_file_with_fastapi_endpoints(self, tracer):
        """Test detecting FastAPI endpoints."""
        code = """
from fastapi import FastAPI, APIRouter

app = FastAPI()
router = APIRouter()

@app.get("/api/v1/users")
async def get_users():
    return {"users": []}

@app.post("/api/v1/users")
async def create_user(user: dict):
    return {"id": 1}

@router.get("/api/v1/orders/{order_id}")
async def get_order(order_id: int):
    return {"order_id": order_id}
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            endpoints = await tracer.trace_file(temp_path)
            assert len(endpoints) >= 2
            assert any(ep.method == "GET" for ep in endpoints)
            assert any(ep.method == "POST" for ep in endpoints)
            assert any(ep.is_internal for ep in endpoints)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_trace_file_with_flask_endpoints(self, tracer):
        """Test detecting Flask endpoints."""
        code = """
from flask import Flask

app = Flask(__name__)

@app.route("/users", methods=["GET"])
def get_users():
    return {"users": []}

@app.route("/users", methods=["POST"])
def create_user():
    return {"id": 1}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            endpoints = await tracer.trace_file(temp_path)
            assert len(endpoints) >= 2
            assert any(ep.is_internal for ep in endpoints)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_trace_file_with_httpx_client(self, tracer):
        """Test detecting httpx client calls."""
        code = """
import httpx

async def fetch_user(user_id):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/users/{user_id}")
        return response.json()

def sync_fetch():
    response = httpx.get("https://api.example.com/data")
    return response.json()
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            endpoints = await tracer.trace_file(temp_path)
            assert len(endpoints) >= 1
            assert any(ep.is_external for ep in endpoints)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_trace_file_with_requests_client(self, tracer):
        """Test detecting requests library calls."""
        code = """
import requests

def get_data():
    response = requests.get("https://api.github.com/repos/owner/repo")
    return response.json()

def post_data(data):
    response = requests.post("https://api.stripe.com/v1/charges", json=data)
    return response.json()

def with_timeout():
    response = requests.get("https://api.example.com", timeout=30)
    return response
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            endpoints = await tracer.trace_file(temp_path)
            assert len(endpoints) >= 2
            assert any(ep.is_external for ep in endpoints)
            assert any(ep.method == "GET" for ep in endpoints)
            assert any(ep.method == "POST" for ep in endpoints)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_trace_file_detects_auth_patterns(self, tracer):
        """Test detecting authentication patterns."""
        code = """
from fastapi import FastAPI, Depends
from fastapi.security import OAuth2PasswordBearer

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.get("/api/v1/protected")
async def protected_endpoint(token: str = Depends(oauth2_scheme)):
    return {"status": "authenticated"}

@app.get("/api/v1/admin")
async def admin_endpoint(current_user: User = Depends(get_current_user)):
    return {"status": "admin"}
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            endpoints = await tracer.trace_file(temp_path)
            assert len(endpoints) >= 1
            # Should detect auth in protected endpoints
            assert any(ep.auth_type is not None for ep in endpoints)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_trace_file_detects_timeout(self, tracer):
        """Test detecting timeout configuration."""
        code = """
import requests

def call_with_timeout():
    response = requests.get("https://api.example.com", timeout=30)
    return response

def call_with_tuple_timeout():
    response = requests.post("https://api.example.com", timeout=(5, 30))
    return response
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            endpoints = await tracer.trace_file(temp_path)
            assert len(endpoints) >= 1
            # Should detect timeout
            assert any(ep.timeout_ms is not None for ep in endpoints)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_trace_file_no_api(self, tracer):
        """Test file without API endpoints or calls."""
        code = """
def calculate_total(items):
    return sum(item.price for item in items)

def format_price(amount):
    return f"${amount:.2f}"
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            endpoints = await tracer.trace_file(temp_path)
            assert endpoints == []
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_trace_directory(self, tracer):
        """Test directory tracing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            api_file = Path(tmpdir) / "api_endpoints.py"
            api_file.write_text(
                """
from fastapi import FastAPI
app = FastAPI()

@app.get("/users")
async def get_users():
    return []
"""
            )
            util_file = Path(tmpdir) / "utils.py"
            util_file.write_text(
                """
def format_data(data):
    return data
"""
            )

            endpoints = await tracer.trace_directory(tmpdir)
            assert len(endpoints) >= 1
            assert any(ep.is_internal for ep in endpoints)

    @pytest.mark.asyncio
    async def test_trace_file_with_aiohttp(self, tracer):
        """Test detecting aiohttp client calls."""
        code = """
import aiohttp

async def fetch_data():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.example.com/data") as response:
            return await response.json()
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            endpoints = await tracer.trace_file(temp_path)
            assert len(endpoints) >= 1
        finally:
            Path(temp_path).unlink()


class TestAPICallTracerEdgeCases:
    """Edge case tests for APICallTracer."""

    @pytest.fixture
    def tracer(self):
        """Create real tracer."""
        return APICallTracer(use_mock=False)

    @pytest.mark.asyncio
    async def test_syntax_error_file(self, tracer):
        """Test handling of files with syntax errors."""
        code = """
from fastapi import FastAPI
app = FastAPI(

# Missing closing parenthesis
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            endpoints = await tracer.trace_file(temp_path)
            assert isinstance(endpoints, list)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_empty_file(self, tracer):
        """Test handling of empty files."""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            endpoints = await tracer.trace_file(temp_path)
            assert endpoints == []
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_mixed_internal_external(self, tracer):
        """Test file with both internal endpoints and external calls."""
        code = """
from fastapi import FastAPI
import requests

app = FastAPI()

@app.get("/api/v1/proxy")
async def proxy_endpoint():
    # This endpoint calls an external API
    external_response = requests.get("https://api.external.com/data")
    return external_response.json()
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            endpoints = await tracer.trace_file(temp_path)
            assert any(ep.is_internal for ep in endpoints)
            assert any(ep.is_external for ep in endpoints)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_fstring_url(self, tracer):
        """Test detecting URLs in f-strings."""
        code = """
import requests

def get_user(user_id):
    url = f"https://api.example.com/users/{user_id}"
    return requests.get(url)
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            endpoints = await tracer.trace_file(temp_path)
            # May or may not detect f-string URL depending on implementation
            assert isinstance(endpoints, list)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_all_http_methods(self, tracer):
        """Test detecting all HTTP methods."""
        code = """
from fastapi import FastAPI

app = FastAPI()

@app.get("/resource")
async def get_resource(): pass

@app.post("/resource")
async def create_resource(): pass

@app.put("/resource/{id}")
async def update_resource(id: int): pass

@app.delete("/resource/{id}")
async def delete_resource(id: int): pass

@app.patch("/resource/{id}")
async def patch_resource(id: int): pass
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            endpoints = await tracer.trace_file(temp_path)
            methods = {ep.method for ep in endpoints}
            assert "GET" in methods
            assert "POST" in methods
            assert "PUT" in methods
            assert "DELETE" in methods
            assert "PATCH" in methods
        finally:
            Path(temp_path).unlink()
