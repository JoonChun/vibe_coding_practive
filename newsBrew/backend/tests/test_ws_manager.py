import pytest
from unittest.mock import AsyncMock, MagicMock
from ws.manager import ConnectionManager


@pytest.mark.asyncio
async def test_broadcast_sends_to_active_connections():
    manager = ConnectionManager()
    mock_ws = MagicMock()
    mock_ws.send_text = AsyncMock()
    manager.active_connections.append(mock_ws)
    await manager.broadcast("INFO", "테스트 메시지")
    mock_ws.send_text.assert_called_once()
    call_arg = mock_ws.send_text.call_args[0][0]
    import json
    payload = json.loads(call_arg)
    assert payload["level"] == "INFO"
    assert payload["message"] == "테스트 메시지"
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_broadcast_removes_dead_connections():
    manager = ConnectionManager()
    dead_ws = MagicMock()
    dead_ws.send_text = AsyncMock(side_effect=Exception("connection closed"))
    manager.active_connections.append(dead_ws)
    await manager.broadcast("INFO", "test")
    assert len(manager.active_connections) == 0


@pytest.mark.asyncio
async def test_disconnect_removes_connection():
    manager = ConnectionManager()
    mock_ws = MagicMock()
    manager.active_connections.append(mock_ws)
    manager.disconnect(mock_ws)
    assert mock_ws not in manager.active_connections
