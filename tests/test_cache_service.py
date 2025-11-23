from unittest.mock import AsyncMock, patch

import pytest

from app.services.cache_service import CacheService


@pytest.fixture
async def cache_service():
    """Mock cache service"""
    service = CacheService()
    service.redis_client = AsyncMock()
    service.redis_client.ping = AsyncMock(return_value=True)
    service.redis_client.get = AsyncMock(return_value=None)
    service.redis_client.setex = AsyncMock(return_value=True)
    service.redis_client.delete = AsyncMock(return_value=1)
    return service


@pytest.mark.asyncio
async def test_cache_key_generation(cache_service, sample_text):
    """Test cache key generation is consistent"""
    key1 = cache_service._generate_key(sample_text)
    key2 = cache_service._generate_key(sample_text)

    assert key1 == key2
    assert key1.startswith("tts:audio:")
    assert len(key1) > 20  # Should be a hash


@pytest.mark.asyncio
async def test_cache_normalization(cache_service):
    """Test text normalization in cache keys"""
    text1 = "Hello World"
    text2 = "hello world"
    text3 = "  HELLO WORLD  "

    key1 = cache_service._generate_key(text1)
    key2 = cache_service._generate_key(text2)
    key3 = cache_service._generate_key(text3)

    assert key1 == key2 == key3


@pytest.mark.asyncio
async def test_cache_get_miss(cache_service, sample_text):
    """Test cache miss"""
    cache_service.redis_client.get = AsyncMock(return_value=None)

    result = await cache_service.get(sample_text)

    assert result is None
    assert cache_service.misses == 1
    assert cache_service.hits == 0


@pytest.mark.asyncio
async def test_cache_get_hit(cache_service, sample_text, sample_audio):
    """Test cache hit"""
    cache_service.redis_client.get = AsyncMock(return_value=sample_audio)

    result = await cache_service.get(sample_text)

    assert result == sample_audio
    assert cache_service.hits == 1
    assert cache_service.misses == 0


@pytest.mark.asyncio
async def test_cache_set(cache_service, sample_text, sample_audio):
    """Test cache set operation"""
    result = await cache_service.set(sample_text, sample_audio)

    assert result is True
    cache_service.redis_client.setex.assert_called_once()


@pytest.mark.asyncio
async def test_cache_set_with_ttl(cache_service, sample_text, sample_audio):
    """Test cache set with custom TTL"""
    custom_ttl = 7200
    await cache_service.set(sample_text, sample_audio, ttl=custom_ttl)

    # Verify TTL was passed correctly
    call_args = cache_service.redis_client.setex.call_args
    assert call_args[0][1] == custom_ttl


@pytest.mark.asyncio
async def test_cache_delete(cache_service, sample_text):
    """Test cache delete operation"""
    result = await cache_service.delete(sample_text)

    assert result is True
    cache_service.redis_client.delete.assert_called_once()


@pytest.mark.asyncio
async def test_cache_stats(cache_service):
    """Test cache statistics"""
    cache_service.hits = 10
    cache_service.misses = 5

    stats = await cache_service.get_stats()

    assert stats["hits"] == 10
    assert stats["misses"] == 5
    assert stats["total_requests"] == 15
    assert stats["hit_rate"] == pytest.approx(66.67, rel=0.1)


@pytest.mark.asyncio
async def test_cache_connection_error(cache_service, sample_text):
    """Test cache handles connection errors gracefully"""
    from redis.exceptions import RedisError

    cache_service.redis_client.get = AsyncMock(side_effect=RedisError("Connection failed"))

    result = await cache_service.get(sample_text)

    assert result is None


@pytest.mark.asyncio
async def test_cache_ping(cache_service):
    """Test cache ping/health check"""
    result = await cache_service.ping()
    assert result is True


@pytest.mark.asyncio
async def test_cache_connect():
    """Test cache connection"""
    from app.services.cache_service import CacheService

    cache = CacheService()

    with patch("redis.asyncio.from_url", new_callable=AsyncMock) as mock_redis:
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_redis.return_value = mock_client

        await cache.connect()
        assert cache.redis_client is not None


@pytest.mark.asyncio
async def test_cache_disconnect():
    """Test cache disconnection"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.redis_client = AsyncMock()

    await cache.disconnect()
    cache.redis_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_cache_clear_all():
    """Test clearing all cache"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.redis_client = AsyncMock()

    # Mock async iterator properly
    async def mock_scan_iter(*args, **kwargs):
        for key in [b"key1", b"key2", b"key3"]:
            yield key

    cache.redis_client.scan_iter = mock_scan_iter
    cache.redis_client.delete = AsyncMock(return_value=3)

    result = await cache.clear_all()
    assert result is True
    cache.redis_client.delete.assert_called_once()


@pytest.mark.asyncio
async def test_cache_get_size():
    """Test getting cache size"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.redis_client = AsyncMock()

    # Mock async iterator with kwargs support
    async def mock_iter(*args, **kwargs):
        for i in range(5):
            yield f"key{i}"

    cache.redis_client.scan_iter = mock_iter

    size = await cache.get_size()
    assert size == 5


@pytest.mark.asyncio
async def test_cache_get_stats_with_redis():
    """Test cache stats with Redis info"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.redis_client = AsyncMock()
    cache.redis_client.info = AsyncMock(
        return_value={"total_connections_received": 100, "total_commands_processed": 500}
    )
    cache.hits = 30
    cache.misses = 20

    stats = await cache.get_stats()

    assert stats["redis_connected"] is True
    assert stats["total_connections"] == 100


@pytest.mark.asyncio
async def test_tts_service_close():
    """Test TTS service close"""
    from app.services.tts_service import TTSService

    tts = TTSService()
    tts._ws = AsyncMock()
    tts._ws.closed = False
    tts._ws.close = AsyncMock()

    await tts.close()
    tts._ws.close.assert_called_once()


@pytest.mark.asyncio
async def test_cache_connect_failure():
    """Test cache connection failure"""
    from redis.exceptions import RedisError

    from app.services.cache_service import CacheService

    cache = CacheService()

    with patch("redis.asyncio.from_url", side_effect=RedisError("Connection failed")):
        with pytest.raises(RedisError):
            await cache.connect()


@pytest.mark.asyncio
async def test_cache_clear_all_empty():
    """Test clearing cache when empty"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.redis_client = AsyncMock()

    async def empty_iter(*args, **kwargs):
        return
        yield  # Never reached

    cache.redis_client.scan_iter = empty_iter

    result = await cache.clear_all()
    assert result is True


@pytest.mark.asyncio
async def test_cache_get_no_client():
    """Test cache get when Redis client is not initialized"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    # Don't initialize redis_client

    result = await cache.get("test text")
    assert result is None


@pytest.mark.asyncio
async def test_cache_set_no_client():
    """Test cache set when Redis client is not initialized"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    # Don't initialize redis_client

    result = await cache.set("test text", b"audio data")
    assert result is False


@pytest.mark.asyncio
async def test_cache_delete_no_client():
    """Test cache delete when Redis client is not initialized"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    # Don't initialize redis_client

    result = await cache.delete("test text")
    assert result is False


@pytest.mark.asyncio
async def test_cache_clear_all_no_client():
    """Test cache clear_all when Redis client is not initialized"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    # Don't initialize redis_client

    result = await cache.clear_all()
    assert result is False


@pytest.mark.asyncio
async def test_cache_get_size_no_client():
    """Test cache get_size when Redis client is not initialized"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    # Don't initialize redis_client

    size = await cache.get_size()
    assert size == 0


@pytest.mark.asyncio
async def test_cache_ping_no_client():
    """Test cache ping when Redis client is not initialized"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    # Don't initialize redis_client

    result = await cache.ping()
    assert result is False


@pytest.mark.asyncio
async def test_cache_ping_error():
    """Test cache ping when Redis raises error"""
    from redis.exceptions import RedisError

    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.redis_client = AsyncMock()
    cache.redis_client.ping = AsyncMock(side_effect=RedisError("Ping failed"))

    result = await cache.ping()
    assert result is False


@pytest.mark.asyncio
async def test_cache_disconnect_no_client():
    """Test cache disconnect when client is None"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    # Don't initialize redis_client

    await cache.disconnect()  # Should not raise error


@pytest.mark.asyncio
async def test_cache_set_error():
    """Test cache set when Redis raises error"""
    from redis.exceptions import RedisError

    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.redis_client = AsyncMock()
    cache.redis_client.setex = AsyncMock(side_effect=RedisError("Set failed"))

    result = await cache.set("test", b"data")
    assert result is False


@pytest.mark.asyncio
async def test_cache_delete_error():
    """Test cache delete when Redis raises error"""
    from redis.exceptions import RedisError

    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.redis_client = AsyncMock()
    cache.redis_client.delete = AsyncMock(side_effect=RedisError("Delete failed"))

    result = await cache.delete("test")
    assert result is False


@pytest.mark.asyncio
async def test_cache_delete_not_found():
    """Test cache delete when key doesn't exist"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.redis_client = AsyncMock()
    cache.redis_client.delete = AsyncMock(return_value=0)  # 0 = not found

    result = await cache.delete("test")
    assert result is False


@pytest.mark.asyncio
async def test_cache_clear_all_error():
    """Test cache clear_all when Redis raises error"""
    from redis.exceptions import RedisError

    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.redis_client = AsyncMock()

    async def error_iter(*args, **kwargs):
        raise RedisError("Scan failed")
        yield  # Never reached

    cache.redis_client.scan_iter = error_iter

    result = await cache.clear_all()
    assert result is False


@pytest.mark.asyncio
async def test_cache_get_size_error():
    """Test cache get_size when Redis raises error"""
    from redis.exceptions import RedisError

    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.redis_client = AsyncMock()

    async def error_iter(*args, **kwargs):
        raise RedisError("Scan failed")
        yield  # Never reached

    cache.redis_client.scan_iter = error_iter

    size = await cache.get_size()
    assert size == 0


@pytest.mark.asyncio
async def test_cache_get_stats_no_client():
    """Test cache stats when Redis client is None"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.hits = 5
    cache.misses = 5
    # Don't initialize redis_client

    stats = await cache.get_stats()

    assert stats["redis_connected"] is False
    assert "total_connections" not in stats
    assert "total_commands" not in stats


@pytest.mark.asyncio
async def test_cache_get_stats_redis_info_error():
    """Test cache stats when Redis info() raises error"""
    from redis.exceptions import RedisError

    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.redis_client = AsyncMock()
    cache.redis_client.info = AsyncMock(side_effect=RedisError("Info failed"))
    cache.hits = 10
    cache.misses = 5

    stats = await cache.get_stats()

    assert stats["redis_connected"] is False


@pytest.mark.asyncio
async def test_cache_get_stats_zero_requests():
    """Test cache stats when no requests made"""
    from app.services.cache_service import CacheService

    cache = CacheService()
    cache.hits = 0
    cache.misses = 0

    stats = await cache.get_stats()

    assert stats["hit_rate"] == 0
    assert stats["total_requests"] == 0
