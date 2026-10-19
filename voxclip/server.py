"""Remote transcription server for VoxClip."""

import json
import logging
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import numpy as np

from .transcriber import WhisperTranscriber
from .config import WHISPER_MODELS

import threading

log = logging.getLogger(__name__)

# Global active transcriber to keep model loaded across requests
_active_transcriber = None
_transcriber_lock = threading.Lock()


def get_transcriber(
    model_size: str,
    device: str,
    compute_type: str,
    language: str,
    vad_filter: bool,
    vad_threshold: float,
    cpu_threads: int = 4,
) -> WhisperTranscriber:
    """Gets or creates the active WhisperTranscriber, hotswapping the model if necessary."""
    global _active_transcriber
    
    with _transcriber_lock:
        need_reload = (
            _active_transcriber is None
            or _active_transcriber.model_size != model_size
            or _active_transcriber.device != device
            or _active_transcriber.compute_type != compute_type
            or _active_transcriber.cpu_threads != cpu_threads
        )
        
        if need_reload:
            if _active_transcriber is not None:
                log.info("Unloading previous model: %s", _active_transcriber.model_size)
                _active_transcriber.unload_model()
                
            log.info("Initializing new model: %s (device=%s, cpu_threads=%d)", model_size, device, cpu_threads)
            _active_transcriber = WhisperTranscriber(
                model_size=model_size,
                device=device,
                compute_type=compute_type,
                language=language,
                vad_filter=vad_filter,
                vad_threshold=vad_threshold,
                cpu_threads=cpu_threads,
            )
        else:
            # Just update non-structural settings
            _active_transcriber.language = language if language != "auto" else None
            _active_transcriber.vad_filter = vad_filter
            _active_transcriber.vad_threshold = vad_threshold
            
        return _active_transcriber


class VoxClipRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for VoxClip Whisper server."""

    def log_message(self, format, *args):
        # Redirect http.server logs to python logging
        log.debug(format % args)

    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        if self.path == "/health":
            self._send_json({"status": "ok", "message": "VoxClip Server is running"})
        elif self.path == "/models":
            self._send_json({"models": WHISPER_MODELS})
        else:
            self._send_json({"error": "Not Found"}, 404)

    def do_POST(self):
        if self.path != "/transcribe":
            self._send_json({"error": "Not Found"}, 404)
            return

        try:
            # Read request headers with transcription options
            sample_rate = int(self.headers.get("X-Sample-Rate", "16000"))
            language = self.headers.get("X-Language", "auto")
            model_size = self.headers.get("X-Model-Size", "medium")
            device = self.headers.get("X-Device", "cpu")
            compute_type = self.headers.get("X-Compute-Type", "int8")
            vad_filter = self.headers.get("X-Vad-Filter", "1") == "1"
            vad_threshold = float(self.headers.get("X-Vad-Threshold", "0.5"))
            cpu_threads = int(self.headers.get("X-Cpu-Threads", "4"))

            # Read body raw bytes
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._send_json({"error": "Empty audio data"}, 400)
                return

            raw_audio = self.rfile.read(content_length)
            
            # Reconstruct float32 numpy array
            audio_np = np.frombuffer(raw_audio, dtype=np.float32)
            
            log.info("Received request for transcription: %.1fs of audio, model=%s", 
                     len(audio_np) / sample_rate, model_size)

            # Get transcriber
            transcriber = get_transcriber(
                model_size=model_size,
                device=device,
                compute_type=compute_type,
                language=language,
                vad_filter=vad_filter,
                vad_threshold=vad_threshold,
                cpu_threads=cpu_threads,
            )

            # Transcribe
            result = transcriber.transcribe(audio_np, sample_rate=sample_rate)

            # Return response
            response = {
                "text": result.text,
                "language": result.language,
                "language_probability": result.language_probability,
                "duration_seconds": result.duration_seconds,
                "transcription_time": result.transcription_time,
            }
            self._send_json(response)

        except Exception as e:
            log.exception("Error during request processing")
            self._send_json({"error": str(e)}, 500)


def run_server(host: str = "0.0.0.0", port: int = 8745):
    """Starts the remote Whisper HTTP server."""
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, VoxClipRequestHandler)
    log.info("Starting VoxClip Whisper server on http://%s:%d", host, port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        global _active_transcriber
        if _active_transcriber is not None:
            _active_transcriber.unload_model()
        log.info("Server stopped.")
