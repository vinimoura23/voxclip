"""Remote transcription using VoxClip Whisper server."""

import json
import logging
import time
import urllib.request
import urllib.error
from typing import Optional

import numpy as np

from .transcriber import TranscriptionResult

log = logging.getLogger(__name__)


class RemoteTranscriber:
    """Sends audio to a remote VoxClip server for transcription.
    
    Acts as a drop-in replacement for WhisperTranscriber.
    """

    def __init__(
        self,
        remote_url: str = "http://localhost:8745",
        model_size: str = "medium",
        device: str = "cpu",
        compute_type: str = "int8",
        language: Optional[str] = None,
        vad_filter: bool = True,
        vad_threshold: float = 0.5,
        cpu_threads: int = 4,
    ):
        self.remote_url = remote_url.rstrip("/")
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language if language != "auto" else None
        self.vad_filter = vad_filter
        self.vad_threshold = vad_threshold
        self.cpu_threads = cpu_threads

    @property
    def is_loaded(self) -> bool:
        # A remote transcriber doesn't load a local model, but we can assume it's always ready.
        # We can perform a quick check if needed, but returning True is standard.
        return True

    def load_model(self):
        """No-op for remote transcriber."""
        pass

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> TranscriptionResult:
        """Send audio to the remote server and get transcription."""
        duration = len(audio) / sample_rate
        log.info("Sending %.1fs of audio to remote server %s...", duration, self.remote_url)

        # Prepare headers with transcription settings
        headers = {
            "Content-Type": "application/octet-stream",
            "X-Sample-Rate": str(sample_rate),
            "X-Language": self.language or "auto",
            "X-Model-Size": self.model_size,
            "X-Device": self.device,
            "X-Compute-Type": self.compute_type,
            "X-Vad-Filter": "1" if self.vad_filter else "0",
            "X-Vad-Threshold": str(self.vad_threshold),
            "X-Cpu-Threads": str(self.cpu_threads),
        }

        # Convert numpy array to raw float32 bytes
        data = audio.tobytes()
        url = f"{self.remote_url}/transcribe"

        t0 = time.monotonic()
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            # Set a timeout (e.g., 60 seconds) to prevent hanging
            with urllib.request.urlopen(req, timeout=60.0) as response:
                response_data = response.read().decode("utf-8")
                res = json.loads(response_data)
                
                # Check for error field in response
                if "error" in res:
                    raise RuntimeError(res["error"])

                transcription_time = time.monotonic() - t0
                
                # Create TranscriptionResult from remote response
                result = TranscriptionResult(
                    text=res.get("text", "").strip(),
                    language=res.get("language", "unknown"),
                    language_probability=res.get("language_probability", 0.0),
                    duration_seconds=res.get("duration_seconds", duration),
                    transcription_time=res.get("transcription_time", transcription_time),
                )
                
                log.info("Remote transcription success: %d chars in %.1fs", len(result.text), transcription_time)
                return result

        except urllib.error.URLError as e:
            log.error("Failed to connect to remote transcription server: %s", e)
            raise ConnectionError(f"Could not connect to transcription server at {self.remote_url}. Is it running?") from e
        except json.JSONDecodeError as e:
            log.error("Invalid JSON response from server: %s", e)
            raise ValueError("Invalid response from transcription server") from e
        except Exception as e:
            log.error("Error during remote transcription: %s", e)
            raise

    def unload_model(self):
        """No-op for remote transcriber."""
        pass
