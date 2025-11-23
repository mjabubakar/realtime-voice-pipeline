from unittest.mock import MagicMock, patch


def test_audio_normalization(audio_processor, sample_audio):
    """Test audio normalization"""
    with patch("pydub.AudioSegment.from_file") as mock_audio:
        mock_segment = MagicMock()
        mock_segment.dBFS = -30.0
        mock_segment.apply_gain = MagicMock(return_value=mock_segment)
        mock_segment.export = MagicMock()
        mock_audio.return_value = mock_segment

        result = audio_processor.normalize(sample_audio)

        assert isinstance(result, bytes)
        mock_segment.apply_gain.assert_called_once()


def test_audio_compression(audio_processor, sample_audio):
    """Test audio compression"""
    with patch("pydub.AudioSegment.from_file") as mock_audio:
        mock_segment = MagicMock()
        mock_audio.return_value = mock_segment

        with patch("pydub.effects.compress_dynamic_range", return_value=mock_segment):
            result = audio_processor.compress(sample_audio)
            assert isinstance(result, bytes)


def test_audio_duration(audio_processor, sample_audio):
    """Test audio duration calculation"""
    with patch("pydub.AudioSegment.from_file") as mock_audio:
        mock_segment = MagicMock()
        mock_segment.__len__ = MagicMock(return_value=5000)  # 5 seconds in ms
        mock_audio.return_value = mock_segment

        duration = audio_processor.get_duration(sample_audio)

        assert duration == 5.0


def test_audio_metadata(audio_processor, sample_audio):
    """Test audio metadata extraction"""
    with patch("pydub.AudioSegment.from_file") as mock_audio:
        mock_segment = MagicMock()
        mock_segment.__len__ = MagicMock(return_value=3000)
        mock_segment.frame_rate = 44100
        mock_segment.channels = 2
        mock_segment.dBFS = -20.0
        mock_segment.sample_width = 2
        mock_segment.frame_width = 4
        mock_segment.max_dBFS = 0.0
        mock_segment.rms = 5000
        mock_audio.return_value = mock_segment

        metadata = audio_processor.get_metadata(sample_audio)

        assert "duration_seconds" in metadata
        assert metadata["sample_rate"] == 44100
        assert metadata["channels"] == 2


def test_audio_format_conversion(audio_processor, sample_audio):
    """Test audio format conversion"""
    with patch("pydub.AudioSegment.from_file") as mock_audio:
        mock_segment = MagicMock()
        mock_segment.export = MagicMock()
        mock_audio.return_value = mock_segment

        result = audio_processor.convert_format(sample_audio, "mp3", "wav")

        assert isinstance(result, bytes)


def test_audio_error_handling(audio_processor):
    """Test audio processor handles errors gracefully"""
    invalid_audio = b"not_valid_audio"

    # Should return original audio on error, not crash
    result = audio_processor.normalize(invalid_audio)
    assert result == invalid_audio


def test_audio_trim_silence():
    """Test silence trimming"""
    from app.services.audio_processor import AudioProcessor

    processor = AudioProcessor()
    audio_data = b"fake_audio" * 100

    with patch("pydub.AudioSegment.from_file") as mock_audio:
        mock_segment = MagicMock()
        mock_segment.__getitem__ = MagicMock(return_value=mock_segment)
        mock_segment.export = MagicMock()
        mock_audio.return_value = mock_segment

        with patch("pydub.silence.detect_nonsilent", return_value=[(100, 5000)]):
            result = processor.trim_silence(audio_data)
            assert isinstance(result, bytes)


def test_audio_process_pipeline():
    """Test complete audio processing pipeline"""
    from app.services.audio_processor import AudioProcessor

    processor = AudioProcessor()
    audio_data = b"fake_audio" * 100

    with patch.object(processor, "trim_silence", return_value=audio_data):
        with patch.object(processor, "normalize", return_value=audio_data):
            with patch.object(processor, "compress", return_value=audio_data):
                result = processor.process_pipeline(audio_data)
                assert result == audio_data


def test_audio_get_metadata_error():
    """Test audio metadata with error"""
    from app.services.audio_processor import AudioProcessor

    processor = AudioProcessor()
    invalid_audio = b"not_valid_audio"

    metadata = processor.get_metadata(invalid_audio)
    assert metadata == {}


def test_audio_trim_silence_no_nonsilent():
    """Test trimming when no non-silent parts found"""
    from app.services.audio_processor import AudioProcessor

    processor = AudioProcessor()
    audio_data = b"fake_audio" * 100

    with patch("pydub.AudioSegment.from_file"):
        with patch("pydub.silence.detect_nonsilent", return_value=[]):
            result = processor.trim_silence(audio_data)
            assert result == audio_data


def test_audio_compress_error():
    """Test audio compression error handling"""
    from app.services.audio_processor import AudioProcessor

    processor = AudioProcessor()
    invalid_audio = b"not_valid_audio"

    # Should return original audio on error
    result = processor.compress(invalid_audio)
    assert result == invalid_audio


def test_audio_trim_silence_error():
    """Test trim silence error handling"""
    from app.services.audio_processor import AudioProcessor

    processor = AudioProcessor()
    invalid_audio = b"not_valid_audio"

    # Should return original audio on error
    result = processor.trim_silence(invalid_audio)
    assert result == invalid_audio
