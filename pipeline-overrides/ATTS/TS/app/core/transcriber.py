# TS/app/core/transcriber.py
import os
import logging
import threading
import azure.cognitiveservices.speech as speechsdk
from app.config import CONFIG
from app.services.error_service import NotificationException

LOGGER = logging.getLogger(__name__)


class Transcriber:
    def __init__(self):
        """Validate Azure Speech configuration up front (mirrors the old WhisperX load step)."""
        self.speech_key = CONFIG["SPEECH_KEY"]
        self.speech_region = CONFIG["SPEECH_REGION"]
        self.language = CONFIG["SPEECH_LANGUAGE"]
        if not self.speech_key or not self.speech_region:
            raise NotificationException(
                debate_id="GLOBAL",
                service_name="Transcriber.__init__",
                error_code="MODEL_LOAD_ERROR",
                error_message="Azure Speech key/region not configured",
            )
        LOGGER.info(
            f"Azure Speech transcriber ready (region={self.speech_region}, language={self.language})"
        )

    def transcribe_audio(self, debate_id: str, audio_path: str) -> str:
        """Transcribe a WAV file with Azure AI Speech using continuous recognition.

        Continuous recognition (not recognize_once) is required because a debate audio
        segment is ~25s, beyond the single-shot ~15s limit. Results are concatenated.
        """
        self.debate_id = debate_id
        try:
            LOGGER.info(f"Transcribing audio file via Azure Speech: {audio_path}")
            speech_config = speechsdk.SpeechConfig(
                subscription=self.speech_key, region=self.speech_region
            )
            speech_config.speech_recognition_language = self.language
            audio_config = speechsdk.audio.AudioConfig(filename=audio_path)
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config, audio_config=audio_config
            )

            segments: list[str] = []
            done = threading.Event()

            def _on_recognized(evt):
                if (
                    evt.result.reason == speechsdk.ResultReason.RecognizedSpeech
                    and evt.result.text
                ):
                    segments.append(evt.result.text)

            def _on_stop(evt):
                done.set()

            recognizer.recognized.connect(_on_recognized)
            recognizer.session_stopped.connect(_on_stop)
            recognizer.canceled.connect(_on_stop)

            recognizer.start_continuous_recognition()
            done.wait()
            recognizer.stop_continuous_recognition()

            self._delete_file(audio_path)  # Delete the file after transcription

            transcript = " ".join(segments).replace("...", "").strip()
            LOGGER.info(f"Transcription completed for {audio_path}")
            return transcript
        except NotificationException:
            raise
        except Exception as e:
            raise NotificationException(
                debate_id=debate_id,
                service_name="Transcriber.transcribe_audio",
                error_code="TRANSCRIPTION_ERROR",
                error_message=str(e),
            )

    def _delete_file(self, audio_path: str) -> None:
        """Delete the audio file after transcription."""
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
                LOGGER.debug(f"Deleted audio file: {audio_path}")
        except Exception as e:
            raise NotificationException(
                debate_id=self.debate_id,
                service_name="Transcriber.delete_file",
                error_code="FILE_DELETE_ERROR",
                error_message=str(e),
            )
