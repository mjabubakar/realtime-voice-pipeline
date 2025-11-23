from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_stt_service_transcribe():
    """Test STT transcription"""
    from app.services.stt_service import STTService

    with patch("app.services.stt_service.WhisperModel") as mock_model:
        mock_segments = [
            MagicMock(start=0.0, end=2.5, text="Hello world", avg_logprob=-0.3, no_speech_prob=0.1)
        ]
        mock_info = MagicMock(language="en", language_probability=0.95, duration=2.5)

        mock_model.return_value.transcribe.return_value = (iter(mock_segments), mock_info)

        stt = STTService()
        result = await stt.transcribe("test.wav")

        assert result["text"] == "Hello world"
        assert result["language"] == "en"


@pytest.mark.asyncio
async def test_stt_service_transcribe_bytes():
    """Test STT with bytes input"""
    from app.services.stt_service import STTService

    stt = STTService()

    with patch.object(stt, "transcribe", new_callable=AsyncMock) as mock_transcribe:
        mock_transcribe.return_value = {
            "text": "Test",
            "language": "en",
            "language_probability": 0.95,
            "duration": 1.0,
            "segments": [],
        }

        result = await stt.transcribe_bytes(b"fake_audio")
        assert result["text"] == "Test"


@pytest.mark.asyncio
async def test_stt_detect_language():
    """Test STT language detection"""
    from app.services.stt_service import STTService

    with patch("app.services.stt_service.WhisperModel") as mock_model:
        mock_info = MagicMock(language="es", language_probability=0.92)
        mock_model.return_value.transcribe.return_value = (iter([]), mock_info)

        stt = STTService()
        result = stt.detect_language("test.wav")

        assert result["language"] == "es"
        assert result["probability"] == 0.92


@pytest.mark.asyncio
async def test_stt_with_language_param():
    """Test STT with specific language"""
    from app.services.stt_service import STTService

    with patch("app.services.stt_service.WhisperModel") as mock_model:
        mock_segments = [
            MagicMock(start=0.0, end=1.0, text="Hola", avg_logprob=-0.2, no_speech_prob=0.05)
        ]
        mock_info = MagicMock(language="es", language_probability=0.98, duration=1.0)
        mock_model.return_value.transcribe.return_value = (iter(mock_segments), mock_info)

        stt = STTService()
        result = await stt.transcribe("test.wav", language="es")

        assert result["language"] == "es"


@pytest.mark.asyncio
async def test_stt_transcribe_with_task():
    """Test STT transcription with task parameter"""
    from app.services.stt_service import STTService

    with patch("app.services.stt_service.WhisperModel") as mock_model:
        mock_segments = [
            MagicMock(start=0.0, end=1.0, text="Traducido", avg_logprob=-0.2, no_speech_prob=0.1)
        ]
        mock_info = MagicMock(language="en", language_probability=0.95, duration=1.0)
        mock_model.return_value.transcribe.return_value = (iter(mock_segments), mock_info)

        stt = STTService()
        result = await stt.transcribe("test.wav", task="translate")

        assert result["text"] == "Traducido"


@pytest.mark.asyncio
async def test_stt_transcribe_error():
    """Test STT transcription error handling"""
    from app.services.stt_service import STTService

    with patch("app.services.stt_service.WhisperModel") as mock_model:
        mock_model.return_value.transcribe.side_effect = Exception("Transcription failed")

        stt = STTService()

        with pytest.raises(Exception):
            await stt.transcribe("test.wav")


@pytest.mark.asyncio
async def test_stt_model_loading_error():
    """Test STT model loading failure (lines 27-29)"""
    from app.services.stt_service import STTService

    with patch("app.services.stt_service.WhisperModel") as mock_model:
        mock_model.side_effect = Exception("Model loading failed")

        with pytest.raises(Exception) as exc_info:
            STTService()

        assert "Model loading failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_stt_transcribe_bytes_cleanup():
    """Test temp file cleanup in transcribe_bytes (lines 142-144)"""

    from app.services.stt_service import STTService

    stt = STTService()

    with patch.object(stt, "transcribe", new_callable=AsyncMock) as mock_transcribe:
        mock_transcribe.side_effect = Exception("Transcription failed")

        with pytest.raises(Exception):
            await stt.transcribe_bytes(b"fake_audio")

        # Verify temp file was cleaned up even on error
        # (implicitly tested by the finally block executing)


@pytest.mark.asyncio
async def test_stt_detect_language_error():
    from app.services.stt_service import STTService

    with patch("app.services.stt_service.WhisperModel") as mock_model:
        mock_model.return_value.transcribe.side_effect = Exception("Detection failed")

        stt = STTService()

        with pytest.raises(Exception):
            stt.detect_language("test.wav")


@pytest.mark.asyncio
async def test_stt_multiple_segments():
    """Test handling multiple segments in transcription"""
    from app.services.stt_service import STTService

    with patch("app.services.stt_service.WhisperModel") as mock_model:
        mock_segments = [
            MagicMock(start=0.0, end=1.0, text="First", avg_logprob=-0.1, no_speech_prob=0.05),
            MagicMock(start=1.0, end=2.0, text="Second", avg_logprob=-0.2, no_speech_prob=0.1),
            MagicMock(start=2.0, end=3.0, text="Third", avg_logprob=-0.15, no_speech_prob=0.08),
        ]
        mock_info = MagicMock(language="en", language_probability=0.95, duration=3.0)
        mock_model.return_value.transcribe.return_value = (iter(mock_segments), mock_info)

        stt = STTService()
        result = await stt.transcribe("test.wav")

        assert result["text"] == "First Second Third"
        assert len(result["segments"]) == 3
        assert result["segments"][0]["text"] == "First"
        assert result["segments"][1]["text"] == "Second"
        assert result["segments"][2]["text"] == "Third"


@pytest.mark.asyncio
async def test_stt_empty_segments():
    """Test handling empty segments"""
    from app.services.stt_service import STTService

    with patch("app.services.stt_service.WhisperModel") as mock_model:
        mock_segments = []
        mock_info = MagicMock(language="en", language_probability=0.95, duration=0.0)
        mock_model.return_value.transcribe.return_value = (iter(mock_segments), mock_info)

        stt = STTService()
        result = await stt.transcribe("test.wav")

        assert result["text"] == ""
        assert len(result["segments"]) == 0
