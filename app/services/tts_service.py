import base64
import json
import logging
from typing import Optional

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from app.config import settings

logger = logging.getLogger(__name__)


class TTSService:
    """ElevenLabs TTS service with WebSocket support"""

    def __init__(self):
        self.api_key = settings.ELEVENLABS_API_KEY
        self.voice_id = settings.ELEVENLABS_VOICE_ID
        self.model_id = settings.ELEVENLABS_MODEL_ID
        self.ws_url = (
            f"wss://api.elevenlabs.io/v1/text-to-speech/"
            f"{self.voice_id}/stream-input?model_id={self.model_id}"
        )

        self._ws: Optional[object] = None

    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(
            multiplier=settings.RETRY_MULTIPLIER,
            min=settings.RETRY_MIN_WAIT,
            max=settings.RETRY_MAX_WAIT,
        ),
        retry=retry_if_exception_type((WebSocketException, ConnectionError, TimeoutError)),
        reraise=True,
    )
    async def text_to_speech(self, text: str) -> bytes:
        """
        Convert text to speech using ElevenLabs WebSocket API (new client syntax).
        """
        logger.info(f"Starting TTS for text: {text[:50]}...")
        try:
            async with connect(
                self.ws_url,
                additional_headers={"xi-api-key": self.api_key},
                ping_interval=20,
                ping_timeout=20,
            ) as websocket:

                self._ws = websocket

                # Send initial configuration
                await websocket.send(
                    json.dumps(
                        {
                            "text": " ",
                            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                            "generation_config": {"chunk_length_schedule": [120, 160, 250, 290]},
                        }
                    )
                )

                # Send actual text
                await websocket.send(json.dumps({"text": text, "try_trigger_generation": True}))
                # End of stream
                await websocket.send(json.dumps({"text": ""}))

                audio_chunks = []

                async for raw in websocket:
                    data = json.loads(raw)
                    if "audio" in data and data["audio"] not in ("", None):
                        chunk = base64.b64decode(data["audio"])
                        audio_chunks.append(chunk)
                    if data.get("isFinal"):
                        logger.info("Received final chunk")
                        break

                audio_data = b"".join(audio_chunks)
                logger.info(f"TTS complete. Total audio bytes: {len(audio_data)}")
                return audio_data

        except WebSocketException as e:
            logger.error(f"WebSocket error in TTS: {e}")
            raise ConnectionError(f"TTS WebSocket error: {str(e)}") from e

        except Exception:
            logger.error("Unexpected TTS error", exc_info=True)
            raise

    async def close(self):
        if self._ws and not self._ws.closed:
            try:
                await self._ws.close()
                logger.info("TTS WebSocket closed")
            except Exception:
                pass
