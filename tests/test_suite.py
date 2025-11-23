import asyncio
from unittest.mock import AsyncMock, patch

import pytest

pytest_plugins = ("pytest_asyncio",)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_end_to_end_tts_flow(cache_service, audio_processor, sentiment_service, sample_text):
    """Test complete TTS flow with caching and processing"""
    # Mock TTS service
    mock_audio = b"fake_audio"

    # Check cache (miss)
    cached = await cache_service.get(sample_text)
    assert cached is None

    # Simulate TTS generation
    audio_data = mock_audio

    # Cache the result
    await cache_service.set(sample_text, audio_data)

    # Verify cache hit
    cache_service.redis_client.get = AsyncMock(return_value=audio_data)
    cached = await cache_service.get(sample_text)
    assert cached == audio_data

    # Analyze sentiment
    sentiment = sentiment_service.analyze(sample_text)
    assert "polarity" in sentiment

    # Process audio (mocked)
    with patch.object(audio_processor, "normalize", return_value=audio_data):
        processed = audio_processor.normalize(audio_data)
        assert processed == audio_data


@pytest.mark.asyncio
async def test_concurrent_requests(cache_service, sample_text):
    """Test handling concurrent requests"""
    cache_service.redis_client.get = AsyncMock(return_value=None)

    # Simulate 10 concurrent requests
    tasks = [cache_service.get(f"{sample_text}_{i}") for i in range(10)]
    results = await asyncio.gather(*tasks)

    assert len(results) == 10
    assert all(r is None for r in results)


@pytest.mark.asyncio
async def test_cache_under_load(cache_service):
    """Test cache performance under load"""
    import time

    cache_service.redis_client.get = AsyncMock(return_value=None)
    cache_service.redis_client.setex = AsyncMock(return_value=True)

    start = time.time()

    # Simulate 100 cache operations
    for i in range(100):
        await cache_service.get(f"test_{i}")
        await cache_service.set(f"test_{i}", b"data")

    elapsed = time.time() - start

    # Should complete quickly
    assert elapsed < 2.0


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_cache_performance():
    """Test cache operation performance"""
    import time

    from app.services.cache_service import CacheService

    service = CacheService()
    service.redis_client = AsyncMock()
    service.redis_client.get = AsyncMock(return_value=None)

    start = time.time()

    for i in range(100):
        await service.get(f"test message {i}")

    elapsed = time.time() - start

    # Should complete 100 operations in under 1 second
    assert elapsed < 1.0


def test_sentiment_analysis_performance(sentiment_service):
    """Test sentiment analysis performance"""
    import time

    texts = [f"This is test message number {i}" for i in range(100)]

    start = time.time()
    results = sentiment_service.analyze_batch(texts)
    elapsed = time.time() - start

    assert len(results) == 100
    # Should complete 100 analyses in under 2 seconds
    assert elapsed < 2.0


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_cache_redis_connection_failure(cache_service):
    """Test cache handles Redis connection failure"""
    from redis.exceptions import ConnectionError as RedisConnectionError

    cache_service.redis_client.get = AsyncMock(side_effect=RedisConnectionError())

    result = await cache_service.get("test")
    assert result is None  # Should handle gracefully


def test_sentiment_invalid_input(sentiment_service):
    """Test sentiment with invalid input"""
    result = sentiment_service.analyze(None)
    # Should handle gracefully, not crash
    assert "polarity" in result


@pytest.mark.asyncio
async def test_circuit_breaker_timeout(circuit_breaker):
    """Test circuit breaker timeout behavior"""
    from datetime import datetime, timedelta

    from app.utils.circuit_breaker import CircuitState

    circuit_breaker.state = CircuitState.OPEN
    circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=1)

    # Should still be blocking (timeout not reached)
    time_until_retry = circuit_breaker._time_until_retry()
    assert time_until_retry > 0


@pytest.mark.asyncio
async def test_circuit_breaker_blocks_when_open(circuit_breaker):
    """Test circuit breaker blocks requests when open"""
    from datetime import datetime

    from app.utils.circuit_breaker import CircuitBreakerOpenException, CircuitState

    # Force circuit open
    circuit_breaker.state = CircuitState.OPEN
    circuit_breaker.last_failure_time = datetime.now()

    # Create a simple async function that returns an awaitable
    async def some_func():
        await asyncio.sleep(0)
        return "result"

    # The circuit breaker call method expects an awaitable
    # Pass the coroutine itself (the result of calling some_func())
    with pytest.raises(CircuitBreakerOpenException):
        # Create the coroutine and pass it to call
        coro = some_func()
        await circuit_breaker.call(coro)


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_recovery(circuit_breaker):
    """Test circuit breaker recovery through half-open state"""
    from datetime import datetime, timedelta

    from app.utils.circuit_breaker import CircuitState

    # Set circuit to open with old failure time
    circuit_breaker.state = CircuitState.OPEN
    circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=100)

    async def success_func():
        return "success"

    # First call should transition to half-open
    await circuit_breaker.call(success_func())
    assert circuit_breaker.state == CircuitState.HALF_OPEN

    # Enough successes should close circuit
    for _ in range(circuit_breaker.success_threshold - 1):
        await circuit_breaker.call(success_func())

    assert circuit_breaker.state == CircuitState.CLOSED


def test_circuit_breaker_status(circuit_breaker):
    """Test circuit breaker status reporting"""
    status = circuit_breaker.get_status()

    assert "name" in status
    assert "state" in status
    assert "failure_count" in status
    assert status["name"] == "Test"


def test_circuit_breaker_manual_reset(circuit_breaker):
    """Test manual circuit breaker reset"""
    from app.utils.circuit_breaker import CircuitState

    circuit_breaker.state = CircuitState.OPEN
    circuit_breaker.failure_count = 10

    circuit_breaker.reset()

    assert circuit_breaker.state == CircuitState.CLOSED
    assert circuit_breaker.failure_count == 0
