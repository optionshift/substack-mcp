import os
import pytest
from unittest.mock import patch


class TestServerInitialization:
    """Test MCP server creates and initializes correctly."""

    def test_mcp_instance_exists(self):
        from src.server import mcp
        assert mcp is not None

    def test_mcp_instance_name(self):
        from src.server import mcp
        assert mcp.name == "ss-navigator"


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check_returns_dict(self):
        from src.server import health_check
        result = health_check()
        assert isinstance(result, dict)

    def test_health_check_status_ok(self):
        from src.server import health_check
        result = health_check()
        assert result["status"] == "ok"

    def test_health_check_version(self):
        from src.server import health_check
        result = health_check()
        assert result["version"] == "1.0.0"

    def test_health_check_complete_body(self):
        from src.server import health_check
        result = health_check()
        assert result == {"status": "ok", "version": "1.0.0"}


class TestHealthHTTPEndpoint:
    """Test health endpoint responds via HTTP."""

    def test_health_http_returns_200(self):
        from src.server import create_starlette_app
        from starlette.testclient import TestClient

        app = create_starlette_app()
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_http_returns_correct_body(self):
        from src.server import create_starlette_app
        from starlette.testclient import TestClient

        app = create_starlette_app()
        client = TestClient(app)
        response = client.get("/health")
        assert response.json() == {"status": "ok", "version": "1.0.0"}


class TestTransportSelection:
    """Test transport selection based on MCP_ENV."""

    def test_production_env_selects_streamable_http(self):
        from src.server import get_transport
        with patch.dict(os.environ, {"MCP_ENV": "production"}):
            assert get_transport() == "streamable-http"

    def test_no_env_selects_stdio(self):
        from src.server import get_transport
        env = os.environ.copy()
        env.pop("MCP_ENV", None)
        with patch.dict(os.environ, env, clear=True):
            assert get_transport() == "stdio"

    def test_development_env_selects_stdio(self):
        from src.server import get_transport
        with patch.dict(os.environ, {"MCP_ENV": "development"}):
            assert get_transport() == "stdio"
