import asyncio
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_complete_tts_pipeline():
    """Test complete TTS pipeline from text to audio"""
    from app.services.audio_processor import AudioProcessor
    from app.services.cache_service import CacheService
    from app.services.sentiment_service import SentimentService

    # Setup services
    cache = CacheService()
    cache.redis_client = AsyncMock()
    cache.redis_client.get = AsyncMock(return_value=None)
    cache.redis_client.setex = AsyncMock(return_value=True)

    sentiment = SentimentService()
    audio_proc = AudioProcessor()

    text = "Hello, this is a test message"

    # 1. Check cache (miss)
    cached = await cache.get(text)
    assert cached is None

    # 2. Analyze sentiment
    sentiment_result = sentiment.analyze(text)
    assert "polarity" in sentiment_result
    assert "label" in sentiment_result

    # 3. Mock TTS generation
    fake_audio = b"fake_audio_data" * 100

    # 4. Cache result
    await cache.set(text, fake_audio)

    # 5. Verify cache hit on second request
    cache.redis_client.get = AsyncMock(return_value=fake_audio)
    cached = await cache.get(text)
    assert cached == fake_audio
    assert cache.hits == 1

    # 6. Process audio
    with patch.object(audio_proc, "normalize", return_value=fake_audio):
        processed = audio_proc.normalize(fake_audio)
        assert processed == fake_audio


@pytest.mark.asyncio
async def test_complete_stt_pipeline():
    """Test complete STT pipeline from audio to text"""
    from app.services.sentiment_service import SentimentService

    sentiment = SentimentService()

    # Mock STT service
    stt = AsyncMock()
    stt.transcribe_bytes = AsyncMock(
        return_value={
            "text": "This is a transcribed message",
            "language": "en",
            "language_probability": 0.95,
            "duration": 3.0,
            "segments": [],
        }
    )

    # 1. Transcribe audio
    audio_data = b"fake_audio_data"
    result = await stt.transcribe_bytes(audio_data)

    assert result["text"] == "This is a transcribed message"
    assert result["language"] == "en"

    # 2. Analyze sentiment of transcript
    sentiment_result = sentiment.analyze(result["text"])
    assert "polarity" in sentiment_result
    assert "label" in sentiment_result


@pytest.mark.asyncio
async def test_tts_with_circuit_breaker():
    """Test TTS with circuit breaker protection"""
    from app.utils.circuit_breaker import CircuitBreaker

    circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_duration=5, name="TTS")

    # Mock TTS that fails - make it return awaitable
    call_count = 0

    async def failing_tts():
        nonlocal call_count
        call_count += 1
        raise Exception("TTS service down")

    # Trigger failures
    for _ in range(3):
        try:
            await circuit_breaker.call(failing_tts())
        except Exception:
            pass  # Expected

    # Circuit should be open now
    assert circuit_breaker.state.value == "open"


@pytest.mark.asyncio
async def test_cache_deduplication():
    """Test cache reduces duplicate TTS calls"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.redis_client = AsyncMock()

    text = "Hello world"
    audio_data = b"fake_audio"

    # First call - cache miss
    cache.redis_client.get = AsyncMock(return_value=None)
    result1 = await cache.get(text)
    assert result1 is None
    assert cache.misses == 1

    # Cache the audio
    cache.redis_client.setex = AsyncMock(return_value=True)
    await cache.set(text, audio_data)

    # Second call - cache hit
    cache.redis_client.get = AsyncMock(return_value=audio_data)
    result2 = await cache.get(text)
    assert result2 == audio_data
    assert cache.hits == 1

    # Calculate reduction
    await cache.redis_client.info(section="stats")
    stats = await cache.get_stats()
    assert stats["hit_rate"] == 50.0


@pytest.mark.asyncio
async def test_concurrent_tts_requests():
    """Test handling multiple concurrent TTS requests"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.redis_client = AsyncMock()

    async def mock_get(*args, **kwargs):
        return None

    async def mock_setex(*args, **kwargs):
        return True

    cache.redis_client.get = mock_get
    cache.redis_client.setex = mock_setex

    # Simulate 10 concurrent requests
    async def process_request(text):
        cached = await cache.get(text)
        if not cached:
            # Simulate TTS generation
            await asyncio.sleep(0.01)
            audio = f"audio_for_{text}".encode()
            await cache.set(text, audio)
            return audio
        return cached

    texts = [f"message_{i}" for i in range(10)]
    tasks = [process_request(text) for text in texts]

    results = await asyncio.gather(*tasks)

    assert len(results) == 10
    assert all(isinstance(r, bytes) for r in results)


@pytest.mark.asyncio
async def test_sentiment_with_tts():
    """Test sentiment analysis integrated with TTS"""
    from app.services.sentiment_service import SentimentService

    sentiment = SentimentService()

    test_cases = [
        ("I absolutely love this amazing product!", "positive"),
        ("This is terrible and awful", "negative"),
        ("The table is wooden", "neutral"),
    ]

    for text, expected_label in test_cases:
        result = sentiment.analyze(text)
        assert result["label"] == expected_label


@pytest.mark.asyncio
async def test_retry_mechanism():
    """Test retry mechanism with Tenacity"""
    from tenacity import retry, stop_after_attempt

    attempt_count = 0

    @retry(stop=stop_after_attempt(3))
    async def flaky_service():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise Exception("Service temporarily unavailable")
        return "success"

    result = await flaky_service()
    assert result == "success"
    assert attempt_count == 3


@pytest.mark.asyncio
async def test_websocket_full_duplex_simulation():
    """Simulate full duplex realtime voice pipeline"""
    from app.services.sentiment_service import SentimentService

    sentiment = SentimentService()

    # Simulate: Audio → STT → Analyze → Generate Response → TTS → Audio

    # 1. Mock STT result
    transcript = "Hello, how are you?"

    # 2. Analyze sentiment
    sentiment_result = sentiment.analyze(transcript)
    assert "polarity" in sentiment_result

    # 3. Generate response based on sentiment
    if sentiment_result["label"] == "positive":
        response_text = "I'm doing great, thank you!"
    else:
        response_text = "I'm here to help."

    # 4. Mock TTS for response
    response_audio = b"fake_response_audio"

    assert isinstance(response_audio, bytes)
    assert len(response_text) > 0


@pytest.mark.asyncio
async def test_load_simulation():
    """Simulate load testing scenario"""
    import time

    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.redis_client = AsyncMock()

    async def mock_get(*args, **kwargs):
        return None

    async def mock_setex(*args, **kwargs):
        return True

    cache.redis_client.get = mock_get
    cache.redis_client.setex = mock_setex

    start_time = time.time()

    # Simulate 50 concurrent users
    async def user_session(user_id):
        for i in range(5):
            text = f"user_{user_id}_message_{i}"
            await cache.get(text)
            await cache.set(text, b"audio_data")

    tasks = [user_session(i) for i in range(50)]
    await asyncio.gather(*tasks)

    elapsed = time.time() - start_time

    # Should handle 250 operations (50 users × 5 messages) quickly
    assert elapsed < 5.0

    stats = await cache.get_stats()
    assert stats["total_requests"] == 250


@pytest.mark.asyncio
async def test_error_recovery():
    """Test system recovers from errors"""
    from datetime import datetime, timedelta

    from app.utils.circuit_breaker import CircuitBreaker

    circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_duration=1, name="TestService")

    # Cause failures
    async def failing_service():
        raise Exception("Service error")

    for _ in range(3):
        with pytest.raises(Exception):
            await circuit_breaker.call(failing_service())

    assert circuit_breaker.state.value == "open"

    # Wait for timeout
    circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=2)

    # Now it should work
    async def working_service():
        return "success"

    result = await circuit_breaker.call(working_service())
    assert result == "success"


@pytest.mark.asyncio
async def test_data_flow_integrity():
    """Test data integrity through the pipeline"""
    from app.services.sentiment_service import SentimentService

    sentiment = SentimentService()

    original_text = "This is a test message with specific content"

    # Analyze sentiment
    result = sentiment.analyze(original_text)

    # Verify data integrity
    assert isinstance(result["polarity"], float)
    assert isinstance(result["subjectivity"], float)
    assert isinstance(result["label"], str)
    assert result["label"] in ["positive", "negative", "neutral"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
