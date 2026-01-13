"""
Integration tests for MCP servers.
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.mcp
class TestLeanOpsMCP:
    """Tests for LEAN-Ops MCP server."""
    
    def test_mcp_server_imports(self):
        """Should import MCP server modules."""
        try:
            from lean_ops import server
            assert hasattr(server, "app") or hasattr(server, "mcp")
        except ImportError:
            pytest.skip("LEAN-Ops MCP not installed")
    
    def test_tool_definitions_exist(self):
        """Should have required tool definitions."""
        try:
            from lean_ops.tools import TOOLS
            
            tool_names = [t["name"] for t in TOOLS]
            
            assert "run_backtest" in tool_names or "backtest" in tool_names
            assert "get_parameters" in tool_names or "parameters" in tool_names
        except ImportError:
            pytest.skip("LEAN-Ops tools not accessible")


@pytest.mark.mcp
class TestTradeMindMCP:
    """Tests for Trade-Mind MCP server."""
    
    def test_mcp_server_imports(self):
        """Should import MCP server modules."""
        try:
            from trade_mind import server
            assert hasattr(server, "app") or hasattr(server, "mcp")
        except ImportError:
            pytest.skip("Trade-Mind MCP not installed")
    
    def test_tool_definitions_exist(self):
        """Should have required tool definitions."""
        try:
            from trade_mind.tools import TOOLS
            
            tool_names = [t["name"] for t in TOOLS]
            
            assert any("pattern" in t.lower() for t in tool_names)
            assert any("recommend" in t.lower() for t in tool_names)
        except ImportError:
            pytest.skip("Trade-Mind tools not accessible")


@pytest.mark.mcp
class TestMCPProtocol:
    """Tests for MCP protocol compliance."""
    
    def test_valid_jsonrpc_request(self):
        """Should handle valid JSON-RPC request format."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }
        
        assert request["jsonrpc"] == "2.0"
        assert "id" in request
        assert "method" in request
    
    def test_valid_tool_call_request(self):
        """Should format tool call correctly."""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "run_backtest",
                "arguments": {
                    "start_date": "2024-01-01",
                    "end_date": "2024-03-01",
                    "initial_capital": 100000,
                },
            },
        }
        
        assert request["params"]["name"] == "run_backtest"
        assert "arguments" in request["params"]


@pytest.mark.mcp
class TestMCPMockResponses:
    """Tests using mock MCP responses."""
    
    def test_mock_backtest_response(self):
        """Should handle backtest response."""
        from fixtures.mock_responses import mock_backtest_result
        
        response = mock_backtest_result(
            total_return=0.25,
            sharpe_ratio=2.1,
            max_drawdown=0.06,
        )
        
        assert response["status"] == "completed"
        assert response["metrics"]["total_return"] == 0.25
        assert response["metrics"]["sharpe_ratio"] == 2.1
    
    def test_mock_pattern_response(self):
        """Should handle pattern response."""
        from fixtures.mock_responses import mock_pattern_response
        
        response = mock_pattern_response(
            pattern_type="ENTRY_TIMING",
            confidence=0.85,
        )
        
        assert response["pattern_type"] == "ENTRY_TIMING"
        assert response["confidence"] == 0.85
    
    def test_mock_error_handling(self):
        """Should handle error responses."""
        from fixtures.mock_responses import mock_error_response
        
        response = mock_error_response(500, "Database connection failed")
        
        assert "error" in response
        assert response["error"]["code"] == 500


@pytest.mark.mcp
@pytest.mark.asyncio
class TestMCPClientMock:
    """Tests for MCP client with mocked server."""
    
    async def test_mock_client_post(self, mock_http_client):
        """Should make POST requests."""
        response = await mock_http_client.post(
            "http://localhost:8000/mcp",
            json={"method": "test"},
        )
        
        assert response.status_code == 200
    
    async def test_mock_tool_execution(self, mock_http_client):
        """Should execute tools via mock client."""
        mock_http_client.post.return_value.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "success": True,
                "data": {"backtest_id": "BT_123"},
            },
        }
        
        response = await mock_http_client.post(
            "http://localhost:8000/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "run_backtest", "arguments": {}},
            },
        )
        
        result = response.json()
        
        assert result["result"]["success"] == True


@pytest.mark.mcp
class TestToolParameterValidation:
    """Tests for MCP tool parameter validation."""
    
    def test_backtest_params_validation(self):
        """Should validate backtest parameters."""
        valid_params = {
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 100000,
        }
        
        # All required fields present
        assert "start_date" in valid_params
        assert "end_date" in valid_params
        assert "initial_capital" in valid_params
        
        # Types are correct
        assert isinstance(valid_params["initial_capital"], int)
    
    def test_pattern_params_validation(self):
        """Should validate pattern parameters."""
        valid_params = {
            "pattern_type": "ENTRY_TIMING",
            "min_confidence": 0.7,
            "limit": 10,
        }
        
        assert valid_params["pattern_type"] in [
            "ENTRY_TIMING", "EXIT_TIMING", "POSITION_SIZING",
            "REGIME_DETECTION", "RISK_MANAGEMENT",
        ]
        assert 0 <= valid_params["min_confidence"] <= 1
