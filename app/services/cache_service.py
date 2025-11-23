import hashlib
import logging
from typing import Optional

import redis.asyncio as redis
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis-based cache for audio deduplication"""

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.hits = 0
        self.misses = 0

    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = await redis.from_url(
                settings.get_redis_url(),
                password=settings.REDIS_PASSWORD,
                encoding="utf-8",
                decode_responses=False,  # Keep binary data as-is
                socket_connect_timeout=5,
                socket_timeout=5,
            )

            # Test connection
            await self.redis_client.ping()
            logger.info("Redis connection established")

        except RedisError as e:
            logger.error(f"Redis connection failed: {str(e)}")
            raise

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")

    async def ping(self) -> bool:
        """Check if Redis is available"""
        try:
            if self.redis_client:
                await self.redis_client.ping()
                return True
        except RedisError:
            pass
        return False

    def _generate_key(self, text: str) -> str:
        """
        Generate cache key from text
        Uses SHA256 hash for consistent, collision-resistant keys

        Args:
            text: Input text

        Returns:
            Cache key
        """
        # Normalize text (lowercase, strip whitespace)
        normalized = text.lower().strip()

        # Generate hash
        hash_obj = hashlib.sha256(normalized.encode("utf-8"))
        key = f"tts:audio:{hash_obj.hexdigest()}"

        return key

    async def get(self, text: str) -> Optional[bytes]:
        """
        Get cached audio for text

        Args:
            text: Input text

        Returns:
            Cached audio data or None
        """
        if not self.redis_client:
            logger.warning("Redis client not initialized")
            return None

        try:
            key = self._generate_key(text)
            data = await self.redis_client.get(key)

            if data:
                self.hits += 1
                logger.debug(f"Cache HIT: {key[:20]}...")
                return data
            else:
                self.misses += 1
                logger.debug(f"Cache MISS: {key[:20]}...")
                return None

        except RedisError as e:
            logger.error(f"Redis GET error: {str(e)}")
            return None

    async def set(self, text: str, audio_data: bytes, ttl: Optional[int] = None) -> bool:
        """
        Cache audio data for text

        Args:
            text: Input text
            audio_data: Audio data to cache
            ttl: Time-to-live in seconds (default: from settings)

        Returns:
            True if successful
        """
        if not self.redis_client:
            logger.warning("Redis client not initialized")
            return False

        try:
            key = self._generate_key(text)
            ttl = ttl or settings.REDIS_CACHE_TTL

            await self.redis_client.setex(key, ttl, audio_data)

            logger.debug(f"Cache SET: {key[:20]}... (TTL: {ttl}s)")
            return True

        except RedisError as e:
            logger.error(f"Redis SET error: {str(e)}")
            return False

    async def delete(self, text: str) -> bool:
        """
        Delete cached audio

        Args:
            text: Input text

        Returns:
            True if successful
        """
        if not self.redis_client:
            return False

        try:
            key = self._generate_key(text)
            result = await self.redis_client.delete(key)
            return result > 0
        except RedisError as e:
            logger.error(f"Redis DELETE error: {str(e)}")
            return False

    async def clear_all(self) -> bool:
        """Clear all TTS caches"""
        if not self.redis_client:
            return False

        try:
            # Find all TTS keys
            keys = []
            async for key in self.redis_client.scan_iter(match="tts:audio:*"):
                keys.append(key)

            if keys:
                await self.redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} cached items")

            return True
        except RedisError as e:
            logger.error(f"Redis CLEAR error: {str(e)}")
            return False

    async def get_stats(self) -> dict:
        """
        Get cache statistics

        Returns:
            Dict with cache stats
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        stats = {
            "hits": self.hits,
            "misses": self.misses,
            "total_requests": total_requests,
            "hit_rate": round(hit_rate, 2),
            "reduction_percentage": round(hit_rate, 2),  # Same as hit rate
        }

        # Try to get Redis info
        if self.redis_client:
            try:
                info = await self.redis_client.info("stats")
                stats["redis_connected"] = True
                stats["total_connections"] = info.get("total_connections_received", 0)
                stats["total_commands"] = info.get("total_commands_processed", 0)
            except RedisError:
                stats["redis_connected"] = False
        else:
            stats["redis_connected"] = False

        return stats

    async def get_size(self) -> int:
        """
        Get number of cached items

        Returns:
            Number of cached audio files
        """
        if not self.redis_client:
            return 0

        try:
            count = 0
            async for _ in self.redis_client.scan_iter(match="tts:audio:*"):
                count += 1
            return count
        except RedisError:
            return 0
