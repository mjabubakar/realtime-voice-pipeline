from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_tts_service_success():
    """Test TTS service generates audio"""
    import base64
    import json

    from app.services.tts_service import TTSService

    tts = TTSService()

    # Patch where connect is imported in tts_service
    with patch("app.services.tts_service.connect") as mock_connect:
        # Create proper audio chunks with base64 encoding
        audio_chunk_1 = base64.b64encode(b"audio_chunk_1_data").decode()
        audio_chunk_2 = base64.b64encode(b"audio_chunk_2_data").decode()

        # Create messages that will be yielded by async for
        messages = [
            json.dumps({"audio": audio_chunk_1}),
            json.dumps({"audio": audio_chunk_2, "isFinal": True}),
        ]

        # Create a proper mock WebSocket that works as an async iterator
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        mock_ws.closed = False

        # Make the websocket itself an async iterator
        async def async_iterator():
            for msg in messages:
                yield msg

        mock_ws.__aiter__ = lambda self: async_iterator()

        # Create a proper async context manager mock
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        # Make connect return the context manager
        mock_connect.return_value = mock_context

        result = await tts.text_to_speech("test text")

        # Verify result is bytes
        assert isinstance(result, bytes), f"Expected bytes but got {type(result)}"
        assert len(result) > 0, f"Expected audio data but got empty bytes. Result: {result}"

        # Verify we got combined audio chunks
        expected_audio = b"audio_chunk_1_data" + b"audio_chunk_2_data"
        assert result == expected_audio

        # Verify connect was called
        mock_connect.assert_called_once()

        # Verify send was called 3 times (config, text, end-of-stream)
        assert mock_ws.send.call_count == 3


@pytest.mark.asyncio
async def test_tts_service_empty_audio():
    """Test TTS service handles empty audio chunks"""
    import base64
    import json

    from app.services.tts_service import TTSService

    tts = TTSService()

    with patch("app.services.tts_service.connect") as mock_connect:
        # Messages with empty audio and None values
        messages = [
            json.dumps({"audio": ""}),  # Empty string
            json.dumps({"audio": None}),  # None
            json.dumps({"audio": base64.b64encode(b"real_data").decode(), "isFinal": True}),
        ]

        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        mock_ws.closed = False

        async def async_iterator():
            for msg in messages:
                yield msg

        mock_ws.__aiter__ = lambda self: async_iterator()

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_connect.return_value = mock_context

        result = await tts.text_to_speech("test")

        # Should only include the real data, not empty/None
        assert result == b"real_data"


@pytest.mark.asyncio
async def test_tts_service_connection_error():
    """Test TTS service handles connection errors"""
    from websockets.exceptions import WebSocketException

    from app.services.tts_service import TTSService

    tts = TTSService()

    with patch("app.services.tts_service.connect") as mock_connect:
        # Make connect raise an exception
        mock_connect.side_effect = WebSocketException("Connection failed")

        # Should raise ConnectionError due to the exception handling in text_to_speech
        with pytest.raises(ConnectionError) as exc_info:
            await tts.text_to_speech("test")

        assert "TTS WebSocket error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_tts_service_attributes():
    """Test TTS service initialization"""
    from app.services.tts_service import TTSService

    tts = TTSService()

    # Verify service is properly initialized
    assert tts.api_key is not None
    assert tts.voice_id is not None
    assert tts.model_id is not None
    assert tts.ws_url is not None
    assert "wss://api.elevenlabs.io" in tts.ws_url


@pytest.mark.asyncio
async def test_tts_service_close():
    """Test TTS service cleanup"""
    from app.services.tts_service import TTSService

    tts = TTSService()

    # Create a mock websocket
    mock_ws = AsyncMock()
    mock_ws.closed = False
    mock_ws.close = AsyncMock()

    tts._ws = mock_ws

    await tts.close()

    # Verify close was called
    mock_ws.close.assert_called_once()


@pytest.mark.asyncio
async def test_tts_service_close_already_closed():
    """Test closing an already closed websocket"""
    from app.services.tts_service import TTSService

    tts = TTSService()

    # Mock an already closed websocket
    mock_ws = AsyncMock()
    mock_ws.closed = True
    mock_ws.close = AsyncMock()

    tts._ws = mock_ws

    await tts.close()

    # Close should not be called if already closed
    mock_ws.close.assert_not_called()
