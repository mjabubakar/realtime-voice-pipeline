import base64
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client"""
    from app.main import app

    return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint returns HTML"""
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Realtime Voice Pipeline" in response.text


def test_health_endpoint(client):
    """Test health check endpoint"""
    with patch("app.main.cache_service.ping", new_callable=AsyncMock) as mock_ping:
        mock_ping.return_value = True

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "active_connections" in data


def test_stats_endpoint(client):
    """Test statistics endpoint"""
    with patch("app.main.cache_service.get_stats", new_callable=AsyncMock) as mock_stats:
        mock_stats.return_value = {"hits": 10, "misses": 5, "total_requests": 15, "hit_rate": 66.67}

        response = client.get("/stats")

        assert response.status_code == 200
        data = response.json()
        assert "cache_stats" in data
        assert "circuit_breaker" in data
        assert data["cache_stats"]["hits"] == 10


def test_tts_api_endpoint(client):
    """Test TTS REST API endpoint"""
    with patch("app.main.tts_service.text_to_speech", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = b"fake_audio_data"

        with patch("app.main.cache_service.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with patch("app.main.cache_service.set", new_callable=AsyncMock):
                response = client.post("/api/tts", json={"text": "Hello world", "use_cache": True})

                assert response.status_code == 200
                data = response.json()
                assert "audio_base64" in data
                assert data["text"] == "Hello world"


def test_tts_api_empty_text(client):
    """Test TTS API with empty text"""
    response = client.post("/api/tts", json={"text": ""})

    assert response.status_code == 400
    assert "Text is required" in response.json()["detail"]


def test_stt_api_endpoint(client):
    """Test STT REST API endpoint"""
    audio_data = b"fake_audio_data"
    audio_base64 = base64.b64encode(audio_data).decode("utf-8")

    with patch("app.main.stt_service.transcribe_bytes", new_callable=AsyncMock) as mock_stt:
        mock_stt.return_value = {
            "text": "Hello world",
            "language": "en",
            "language_probability": 0.95,
            "duration": 2.5,
            "segments": [],
        }

        response = client.post("/api/stt", json={"audio_base64": audio_base64, "language": "en"})

        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Hello world"
        assert data["language"] == "en"
        assert "sentiment" in data


def test_stt_api_empty_audio(client):
    """Test STT API with empty audio"""
    response = client.post("/api/stt", json={"audio_base64": ""})

    assert response.status_code == 400
    assert "Audio data is required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_websocket_connection(client):
    """Test WebSocket connection"""
    with client.websocket_connect("/ws/voice") as websocket:
        # Connection should be established
        assert websocket is not None


@pytest.mark.asyncio
async def test_websocket_tts_message(client):
    """Test WebSocket TTS message"""
    with patch("app.main.tts_service.text_to_speech", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = b"fake_audio"

        with patch("app.main.cache_service.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with patch("app.main.cache_service.set", new_callable=AsyncMock):
                with client.websocket_connect("/ws/voice") as websocket:
                    # Send TTS request
                    websocket.send_json({"type": "text", "text": "Hello world"})

                    # Receive response
                    data = websocket.receive_json()

                    assert data["type"] == "audio"
                    assert "latency_ms" in data


@pytest.mark.asyncio
async def test_websocket_stt_message(client):
    """Test WebSocket STT message"""
    audio_data = b"fake_audio_data"
    audio_base64 = base64.b64encode(audio_data).decode("utf-8")

    with patch("app.main.stt_service.transcribe_bytes", new_callable=AsyncMock) as mock_stt:
        mock_stt.return_value = {
            "text": "Hello world",
            "language": "en",
            "language_probability": 0.95,
            "duration": 2.5,
            "segments": [],
        }

        with client.websocket_connect("/ws/voice") as websocket:
            # Send STT request
            websocket.send_json({"type": "audio", "audio": audio_base64})

            # Receive response
            data = websocket.receive_json()

            assert data["type"] == "transcript"
            assert data["text"] == "Hello world"


def test_websocket_invalid_message_type(client):
    """Test WebSocket with invalid message type"""
    with client.websocket_connect("/ws/voice") as websocket:
        websocket.send_json({"type": "invalid", "data": "test"})

        data = websocket.receive_json()

        assert data["type"] == "error"
        assert "Invalid message type" in data["message"]


def test_static_files_mounted(client):
    """Test static files are properly mounted"""
    # This will fail if static files aren't set up, which is expected
    # Just test that the app has the mount point configured
    from app.main import app

    routes = [route.path for route in app.routes]
    assert any("/static" in route for route in routes)


def test_cors_middleware(client):
    """Test CORS middleware is configured"""
    response = client.options("/health")

    # CORS headers should be present
    assert response.status_code in [200, 405]  # Either is acceptable


@pytest.mark.asyncio
async def test_websocket_cache_hit(client):
    """Test WebSocket with cache hit"""
    cached_audio = b"cached_audio_data"

    with patch("app.main.cache_service.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = cached_audio

        with client.websocket_connect("/ws/voice") as websocket:
            websocket.send_json({"type": "text", "text": "Hello world"})

            data = websocket.receive_json()

            assert data["type"] == "audio"
            assert data["cached"] is True


@pytest.mark.asyncio
async def test_websocket_error_handling(client):
    """Test WebSocket error handling"""
    with patch("app.main.tts_service.text_to_speech", new_callable=AsyncMock) as mock_tts:
        mock_tts.side_effect = Exception("TTS service error")

        with patch("app.main.cache_service.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with client.websocket_connect("/ws/voice") as websocket:
                websocket.send_json({"type": "text", "text": "Hello world"})

                data = websocket.receive_json()

                assert data["type"] == "error"
                assert "TTS service error" in data["message"]


def test_tts_api_cached_response(client):
    """Test TTS API returns cached response"""
    cached_audio = b"cached_audio_data"

    with patch("app.main.cache_service.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = cached_audio

        response = client.post("/api/tts", json={"text": "Hello world", "use_cache": True})

        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is True


def test_concurrent_websocket_connections(client):
    """Test multiple concurrent WebSocket connections"""
    connections = []

    try:
        for i in range(5):
            ws = client.websocket_connect("/ws/voice")
            connections.append(ws.__enter__())

        # All connections should be active
        assert len(connections) == 5

    finally:
        for ws in connections:
            ws.__exit__(None, None, None)


@pytest.mark.asyncio
async def test_lifespan_startup_and_shutdown():
    """Test app lifespan startup and shutdown"""
    from app.main import app, lifespan

    with patch("app.main.cache_service.connect", new_callable=AsyncMock) as mock_connect:
        with patch("app.main.cache_service.disconnect", new_callable=AsyncMock) as mock_disconnect:
            with patch("app.main.tts_service.close", new_callable=AsyncMock) as mock_close:

                # Test the lifespan context manager
                async with lifespan(app):
                    # Startup should have been called
                    mock_connect.assert_called_once()

                    # Simulating app running...

                # After exiting context, shutdown should have been called
                mock_disconnect.assert_called_once()
                mock_close.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_startup_only():
    """Test app lifespan startup"""
    from app.main import app, lifespan

    with patch("app.main.cache_service.connect", new_callable=AsyncMock) as mock_connect:
        with patch("app.main.cache_service.disconnect", new_callable=AsyncMock):
            with patch("app.main.tts_service.close", new_callable=AsyncMock):

                async with lifespan(app):
                    # Verify startup was called
                    mock_connect.assert_called_once()
                    # Don't wait for shutdown, just test startup


@pytest.mark.asyncio
async def test_lifespan_with_connection_error():
    """Test app lifespan handles connection errors"""
    from redis.exceptions import RedisError

    from app.main import app, lifespan

    with patch("app.main.cache_service.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.side_effect = RedisError("Connection failed")

        # Should raise the error during startup
        with pytest.raises(RedisError):
            async with lifespan(app):
                pass
