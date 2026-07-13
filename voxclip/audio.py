"""Audio recording using sounddevice."""

import logging
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)


class AudioRecorder:
    """Records audio from the microphone using sounddevice.
    
    Captures 16kHz mono float32 audio suitable for Whisper.
    Provides real-time amplitude data for waveform visualization.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        max_seconds: int = 120,
        on_amplitude: Optional[Callable[[float], None]] = None,
        on_max_duration: Optional[Callable[[], None]] = None,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_seconds = max_seconds
        self.on_amplitude = on_amplitude
        self.on_max_duration = on_max_duration

        self._frames: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._recording = False
        self._start_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def elapsed_seconds(self) -> float:
        if not self._recording:
            return 0.0
        return time.monotonic() - self._start_time

    def start(self):
        """Start recording audio."""
        if self._recording:
            log.warning("Already recording")
            return

        self._frames = []
        self._recording = True
        self._start_time = time.monotonic()

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                blocksize=1024,
                callback=self._audio_callback,
            )
            self._stream.start()
            log.info("Recording started (sr=%d, ch=%d)", self.sample_rate, self.channels)
        except sd.PortAudioError as e:
            self._recording = False
            log.error("Failed to start audio stream: %s", e)
            raise RuntimeError(f"Could not start audio recording: {e}") from e

    def stop(self) -> Optional[np.ndarray]:
        """Stop recording and return the audio data as a numpy array.
        
        Returns None if no audio was captured.
        """
        if not self._recording:
            log.warning("Not recording")
            return None

        self._recording = False

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except sd.PortAudioError as e:
                log.warning("Error closing stream: %s", e)
            self._stream = None

        with self._lock:
            if not self._frames:
                log.warning("No audio frames captured")
                return None
            audio = np.concatenate(self._frames, axis=0).flatten()

        duration = len(audio) / self.sample_rate
        log.info("Recording stopped: %.1fs, %d samples", duration, len(audio))
        return audio

    def cancel(self):
        """Cancel recording without returning data."""
        self._recording = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except sd.PortAudioError:
                pass
            self._stream = None
        self._frames = []
        log.info("Recording cancelled")

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Callback for sounddevice stream — runs in audio thread."""
        if status:
            log.warning("Audio callback status: %s", status)

        if not self._recording:
            return

        # Check max duration
        if self.elapsed_seconds >= self.max_seconds:
            self._recording = False
            log.info("Max recording duration reached (%ds)", self.max_seconds)
            # Close the stream to stop PortAudio from continuing to call this callback
            if self._stream:
                try:
                    self._stream.abort()
                except Exception:
                    pass
            # Notify the daemon so it can transition to the TRANSCRIBING state
            if self.on_max_duration:
                from gi.repository import GLib
                GLib.idle_add(self.on_max_duration)
            return

        # Store audio frame
        with self._lock:
            self._frames.append(indata.copy())

        # Send amplitude to UI for waveform visualization
        if self.on_amplitude:
            try:
                rms = float(np.sqrt(np.mean(indata ** 2)))
                self.on_amplitude(rms)
            except Exception:
                pass


def list_devices() -> str:
    """List available audio input devices."""
    return sd.query_devices()
