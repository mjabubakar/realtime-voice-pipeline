import asyncio
import logging
from typing import Dict, Optional

from faster_whisper import WhisperModel
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)


class STTService:
    """Speech-to-Text service using faster-whisper"""

    def __init__(self):
        """Initialize Whisper model"""
        logger.info(f"Loading Whisper model: {settings.WHISPER_MODEL_SIZE}")

        try:
            self.model = WhisperModel(
                settings.WHISPER_MODEL_SIZE,
                device=settings.WHISPER_DEVICE,
                compute_type=settings.WHISPER_COMPUTE_TYPE,
            )
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {str(e)}")
            raise

    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.RETRY_MULTIPLIER),
    )
    async def transcribe(
        self, audio_path: str, language: Optional[str] = None, task: str = "transcribe"
    ) -> Dict:
        """
        Transcribe audio file to text

        Args:
            audio_path: Path to audio file
            language: Optional language code (e.g., 'en', 'es')
            task: 'transcribe' or 'translate'

        Returns:
            Dict with transcription results
        """
        try:
            logger.info(f"Transcribing audio: {audio_path}")

            # Run transcription in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            segments, info = await loop.run_in_executor(
                None,
                lambda: self.model.transcribe(
                    audio_path,
                    language=language,
                    task=task,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                ),
            )

            # Collect all segments
            segments_list = []
            full_text = []

            for segment in segments:
                segment_dict = {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                    "avg_logprob": segment.avg_logprob,
                    "no_speech_prob": segment.no_speech_prob,
                }
                segments_list.append(segment_dict)
                full_text.append(segment.text.strip())

            result = {
                "text": " ".join(full_text),
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration,
                "segments": segments_list,
            }

            logger.info(
                f"Transcription complete: {len(result['text'])} chars, "
                f"{len(segments_list)} segments, "
                f"language: {info.language} ({info.language_probability:.2f})"
            )

            return result

        except Exception as e:
            logger.error(f"Transcription error: {str(e)}", exc_info=True)
            raise

    async def transcribe_bytes(self, audio_data: bytes, language: Optional[str] = None) -> Dict:
        """
        Transcribe audio from bytes

        Args:
            audio_data: Audio data as bytes
            language: Optional language code

        Returns:
            Dict with transcription results
        """
        import os
        import tempfile

        # Save bytes to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_file.write(audio_data)
            temp_path = temp_file.name

        try:
            result = await self.transcribe(temp_path, language=language)
            return result
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def detect_language(self, audio_path: str) -> Dict:
        """
        Detect language of audio file

        Args:
            audio_path: Path to audio file

        Returns:
            Dict with language detection results
        """
        try:
            _, info = self.model.transcribe(audio_path, beam_size=5)

            return {"language": info.language, "probability": info.language_probability}
        except Exception as e:
            logger.error(f"Language detection error: {str(e)}")
            raise
