import logging
from io import BytesIO

from pydub import AudioSegment
from pydub.effects import compress_dynamic_range

from app.config import settings

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Audio processing and normalization service"""

    def __init__(self):
        """Initialize audio processor"""
        self.sample_rate = settings.AUDIO_SAMPLE_RATE
        self.channels = settings.AUDIO_CHANNELS
        self.target_dbfs = settings.TARGET_DBFS
        logger.info("Audio processor initialized")

    def normalize(self, audio_data: bytes, format: str = "mp3") -> bytes:
        """
        Normalize audio volume to consistent level

        Args:
            audio_data: Input audio as bytes
            format: Audio format (mp3, wav, etc.)

        Returns:
            Normalized audio as bytes
        """
        try:
            # Load audio
            audio = AudioSegment.from_file(BytesIO(audio_data), format=format)

            # Get current dBFS
            current_dbfs = audio.dBFS

            # Calculate gain needed
            gain = self.target_dbfs - current_dbfs

            # Apply gain
            normalized = audio.apply_gain(gain)

            logger.debug(
                f"Audio normalized: {current_dbfs:.1f} dBFS -> "
                f"{normalized.dBFS:.1f} dBFS (gain: {gain:.1f} dB)"
            )

            # Export to bytes
            output = BytesIO()
            normalized.export(output, format=format)
            return output.getvalue()

        except Exception as e:
            logger.error(f"Audio normalization error: {str(e)}")
            # Return original audio if processing fails
            return audio_data

    def compress(self, audio_data: bytes, format: str = "mp3") -> bytes:
        """
        Apply dynamic range compression

        Args:
            audio_data: Input audio as bytes
            format: Audio format

        Returns:
            Compressed audio as bytes
        """
        try:
            audio = AudioSegment.from_file(BytesIO(audio_data), format=format)

            # Apply compression
            compressed = compress_dynamic_range(
                audio, threshold=-20.0, ratio=4.0, attack=5.0, release=50.0
            )

            logger.debug("Dynamic range compression applied")

            output = BytesIO()
            compressed.export(output, format=format)
            return output.getvalue()

        except Exception as e:
            logger.error(f"Audio compression error: {str(e)}")
            return audio_data

    def convert_format(self, audio_data: bytes, input_format: str, output_format: str) -> bytes:
        """
        Convert audio between formats

        Args:
            audio_data: Input audio
            input_format: Input format
            output_format: Desired output format

        Returns:
            Converted audio
        """
        try:
            audio = AudioSegment.from_file(BytesIO(audio_data), format=input_format)

            output = BytesIO()
            audio.export(output, format=output_format)

            logger.debug(f"Converted {input_format} -> {output_format}")
            return output.getvalue()

        except Exception as e:
            logger.error(f"Format conversion error: {str(e)}")
            return audio_data

    def trim_silence(
        self, audio_data: bytes, format: str = "mp3", silence_thresh: int = -50
    ) -> bytes:
        """
        Trim silence from beginning and end

        Args:
            audio_data: Input audio
            format: Audio format
            silence_thresh: Silence threshold in dBFS

        Returns:
            Trimmed audio
        """
        try:
            audio = AudioSegment.from_file(BytesIO(audio_data), format=format)

            # Detect non-silent parts
            from pydub.silence import detect_nonsilent

            nonsilent_ranges = detect_nonsilent(
                audio, min_silence_len=100, silence_thresh=silence_thresh
            )

            if not nonsilent_ranges:
                return audio_data

            # Get first and last non-silent timestamp
            start_trim = nonsilent_ranges[0][0]
            end_trim = nonsilent_ranges[-1][1]

            # Trim
            trimmed = audio[start_trim:end_trim]

            logger.debug(
                f"Trimmed silence: {start_trim}ms - {end_trim}ms "
                f"(removed {(len(audio) - len(trimmed)) / 1000:.2f}s)"
            )

            output = BytesIO()
            trimmed.export(output, format=format)
            return output.getvalue()

        except Exception as e:
            logger.error(f"Silence trimming error: {str(e)}")
            return audio_data

    def get_duration(self, audio_data: bytes, format: str = "mp3") -> float:
        """
        Get audio duration in seconds

        Args:
            audio_data: Input audio
            format: Audio format

        Returns:
            Duration in seconds
        """
        try:
            audio = AudioSegment.from_file(BytesIO(audio_data), format=format)
            return len(audio) / 1000.0
        except Exception as e:
            logger.error(f"Duration calculation error: {str(e)}")
            return 0.0

    def get_metadata(self, audio_data: bytes, format: str = "mp3") -> dict:
        """
        Get audio metadata

        Args:
            audio_data: Input audio
            format: Audio format

        Returns:
            Dict with audio metadata
        """
        try:
            audio = AudioSegment.from_file(BytesIO(audio_data), format=format)

            return {
                "duration_seconds": len(audio) / 1000.0,
                "duration_ms": len(audio),
                "sample_rate": audio.frame_rate,
                "channels": audio.channels,
                "sample_width": audio.sample_width,
                "frame_width": audio.frame_width,
                "dbfs": audio.dBFS,
                "max_dbfs": audio.max_dBFS,
                "rms": audio.rms,
            }
        except Exception as e:
            logger.error(f"Metadata extraction error: {str(e)}")
            return {}

    def process_pipeline(self, audio_data: bytes, format: str = "mp3") -> bytes:
        """
        Run complete audio processing pipeline

        Args:
            audio_data: Input audio
            format: Audio format

        Returns:
            Processed audio
        """
        # Trim silence
        processed = self.trim_silence(audio_data, format)

        # Normalize volume
        processed = self.normalize(processed, format)

        # Apply compression
        processed = self.compress(processed, format)

        logger.info("Audio processing pipeline complete")
        return processed
