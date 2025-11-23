from functools import lru_cache
from typing import Optional

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # API Configuration
    APP_NAME: str = "Realtime Voice Pipeline"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ElevenLabs Configuration
    ELEVENLABS_API_KEY: str  # Required, no default
    ELEVENLABS_VOICE_ID: str = "IKne3meq5aSn9XLyUdCD"  # Default voice
    ELEVENLABS_MODEL_ID: str = "eleven_monolingual_v1"

    # Whisper Configuration
    WHISPER_MODEL_SIZE: str = "base"  # tiny, base, small, medium, large, turbo
    WHISPER_DEVICE: str = "cpu"  # cpu or cuda
    WHISPER_COMPUTE_TYPE: str = "int8"  # int8, float16, float32

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: str | int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_CACHE_TTL: int = 3600  # 1 hour in seconds

    # Audio Processing
    AUDIO_SAMPLE_RATE: int = 22050
    AUDIO_CHANNELS: int = 1
    AUDIO_FORMAT: str = "mp3"
    TARGET_DBFS: float = -20.0  # Normalization target in dB

    # Retry Configuration
    MAX_RETRIES: int = 3
    RETRY_MULTIPLIER: float = 2.0
    RETRY_MIN_WAIT: float = 1.0
    RETRY_MAX_WAIT: float = 10.0

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra fields in .env
    )

    def get_redis_url(self) -> str:
        """Construct Redis connection URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    def is_production(self) -> bool:
        """Check if running in production mode"""
        return not self.DEBUG


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    This ensures we only load .env once
    """
    return Settings()


# Global settings instance
settings = get_settings()
