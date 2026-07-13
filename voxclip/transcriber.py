"""Whisper transcription using faster-whisper."""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    """Result of a transcription."""
    text: str
    language: str
    language_probability: float
    duration_seconds: float
    transcription_time: float  # How long the transcription took

    @property
    def is_empty(self) -> bool:
        return not self.text or not self.text.strip()


class WhisperTranscriber:
    """Transcribes audio using faster-whisper (CTranslate2).
    
    Lazily loads the model on first use to keep startup fast.
    """

    def __init__(
        self,
        model_size: str = "medium",
        device: str = "cpu",
        compute_type: str = "int8",
        language: Optional[str] = None,
        vad_filter: bool = True,
        vad_threshold: float = 0.5,
        cache_dir: Optional[str] = None,
        cpu_threads: int = 4,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language if language != "auto" else None
        self.vad_filter = vad_filter
        self.vad_threshold = vad_threshold
        self.cache_dir = cache_dir
        self.cpu_threads = cpu_threads
        self._model = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load_model(self):
        """Pre-load the Whisper model. Call this at daemon startup."""
        if self._model is not None:
            return

        log.info(
            "Loading faster-whisper model: %s (device=%s, compute=%s, cpu_threads=%d)",
            self.model_size, self.device, self.compute_type, self.cpu_threads
        )
        t0 = time.monotonic()

        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            download_root=self.cache_dir,
            cpu_threads=self.cpu_threads,
        )

        elapsed = time.monotonic() - t0
        log.info("Model loaded in %.1fs", elapsed)

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> TranscriptionResult:
        """Transcribe audio data.
        
        Args:
            audio: Float32 numpy array of audio samples (mono, 16kHz).
            sample_rate: Sample rate of the audio (default 16000).
            
        Returns:
            TranscriptionResult with the transcribed text and metadata.
        """
        if self._model is None:
            self.load_model()

        duration = len(audio) / sample_rate
        log.info("Transcribing %.1fs of audio (lang=%s)...", duration, self.language or "auto")

        t0 = time.monotonic()

        segments, info = self._model.transcribe(
            audio,
            language=self.language,
            vad_filter=self.vad_filter,
            vad_parameters=dict(threshold=self.vad_threshold) if self.vad_filter else None,
            beam_size=5,
            best_of=5,
            temperature=0.0,
        )

        # Collect all segment texts
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        text = " ".join(text_parts).strip()
        transcription_time = time.monotonic() - t0

        result = TranscriptionResult(
            text=text,
            language=info.language,
            language_probability=info.language_probability,
            duration_seconds=duration,
            transcription_time=transcription_time,
        )

        log.info(
            "Transcription done in %.1fs (%.1fx realtime): lang=%s (%.0f%%), %d chars",
            transcription_time,
            transcription_time / max(duration, 0.01),
            result.language,
            result.language_probability * 100,
            len(text),
        )

        return result

    def unload_model(self):
        """Unload the model to free memory."""
        if self._model is not None:
            del self._model
            self._model = None
            log.info("Model unloaded")
