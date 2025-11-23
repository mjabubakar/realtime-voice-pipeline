import asyncio
import base64
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    mock = AsyncMock()
    mock.ping = AsyncMock(return_value=True)
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.setex = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.scan_iter = AsyncMock(return_value=[])
    mock.info = AsyncMock(return_value={})
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_elevenlabs_response():
    """Mock ElevenLabs API response"""
    return {"audio": "base64_encoded_audio_data_here", "isFinal": True}


@pytest.fixture
def mock_whisper_response():
    """Mock Whisper transcription response"""
    return {
        "text": "This is a test transcription",
        "language": "en",
        "language_probability": 0.95,
        "duration": 2.5,
        "segments": [
            {
                "start": 0.0,
                "end": 2.5,
                "text": "This is a test transcription",
                "avg_logprob": -0.3,
                "no_speech_prob": 0.1,
            }
        ],
    }


@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
    return {
        "ELEVENLABS_API_KEY": "test_api_key_123",
        "ELEVENLABS_VOICE_ID": "test_voice_id",
        "REDIS_HOST": "localhost",
        "REDIS_PORT": 6379,
        "REDIS_DB": 0,
        "WHISPER_MODEL_SIZE": "base",
        "DEBUG": True,
    }


@pytest.fixture
async def app_client():
    """FastAPI test client"""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_settings(sample_config):
    """Mock settings object"""
    from app.config import Settings

    return Settings(**sample_config)


@pytest.fixture
def sample_audio():
    """Sample audio data"""
    return b"fake_audio_data_here_" * 100


@pytest.fixture
def sample_text():
    """Sample text for TTS"""
    return "Hello, this is a test message."


@pytest.fixture
def sample_audio_base64(sample_audio):
    """Base64 encoded audio"""
    return base64.b64encode(sample_audio).decode("utf-8")


@pytest.fixture
async def cache_service():
    """Mock cache service"""
    from app.services.cache_service import CacheService

    service = CacheService()
    service.redis_client = AsyncMock()
    service.redis_client.ping = AsyncMock(return_value=True)
    service.redis_client.get = AsyncMock(return_value=None)
    service.redis_client.setex = AsyncMock(return_value=True)
    service.redis_client.delete = AsyncMock(return_value=1)
    service.redis_client.scan_iter = AsyncMock(return_value=[])
    service.redis_client.info = AsyncMock(return_value={})
    service.redis_client.close = AsyncMock()
    return service


@pytest.fixture
def sentiment_service():
    """Sentiment service"""
    from app.services.sentiment_service import SentimentService

    return SentimentService()


@pytest.fixture
def audio_processor():
    """Audio processor"""
    from app.services.audio_processor import AudioProcessor

    return AudioProcessor()


@pytest.fixture
def circuit_breaker():
    """Circuit breaker"""
    from app.utils.circuit_breaker import CircuitBreaker

    return CircuitBreaker(failure_threshold=3, timeout_duration=5, name="Test")


@pytest.fixture
def mock_tts_service():
    """Mock TTS service"""
    mock = AsyncMock()
    mock.text_to_speech = AsyncMock(return_value=b"fake_audio_data")
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_stt_service():
    """Mock STT service"""
    mock = AsyncMock()
    mock.transcribe_bytes = AsyncMock(
        return_value={
            "text": "Hello world",
            "language": "en",
            "language_probability": 0.95,
            "duration": 2.5,
            "segments": [],
        }
    )
    return mock
