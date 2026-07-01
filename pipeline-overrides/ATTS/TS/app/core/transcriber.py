# TS/app/core/transcriber.py
import os
import logging
import threading
import azure.cognitiveservices.speech as speechsdk
from pydub import AudioSegment
from app.config import CONFIG
from app.services.error_service import NotificationException

LOGGER = logging.getLogger(__name__)

# Azure AI Speech's file input (AudioConfig(filename=...)) only accepts 16 kHz / 16-bit /
# mono PCM WAV. CSP exports segments at the SOURCE stream's rate/channels (the debate and
# the M3U8 emulator audio are 44.1 kHz stereo), which Azure's default WAV reader silently
# rejects -> zero recognized phrases -> empty transcript -> no segment is ever posted back
# to the backend -> no live messages. Normalising the audio first fixes that.
AZURE_SAMPLE_RATE = 16000
AZURE_CHANNELS = 1
AZURE_SAMPLE_WIDTH = 2  # bytes == 16-bit PCM

# A ~25 s segment finishes well within this. The timeout only guards against a stuck
# recognition hanging the worker forever (which would stall every following segment).
RECOGNITION_TIMEOUT_S = int(os.getenv("SPEECH_RECOGNITION_TIMEOUT", "180"))


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
        pcm_path = None
        try:
            LOGGER.info(f"Transcribing audio file via Azure Speech: {audio_path}")

            # Normalise to 16 kHz / mono / 16-bit PCM so Azure's file reader accepts it.
            pcm_path = self._to_azure_pcm(audio_path)

            speech_config = speechsdk.SpeechConfig(
                subscription=self.speech_key, region=self.speech_region
            )
            speech_config.speech_recognition_language = self.language
            audio_config = speechsdk.audio.AudioConfig(filename=pcm_path)
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config, audio_config=audio_config
            )

            segments: list[str] = []
            done = threading.Event()
            cancel_error: dict[str, str] = {}

            def _on_recognized(evt):
                if (
                    evt.result.reason == speechsdk.ResultReason.RecognizedSpeech
                    and evt.result.text
                ):
                    segments.append(evt.result.text)

            def _on_canceled(evt):
                # EndOfStream is the normal end-of-file signal. Only a real error
                # (bad key/region, quota, unsupported audio format) must surface --
                # otherwise the failure is swallowed and the segment silently vanishes.
                if getattr(evt, "reason", None) == speechsdk.CancellationReason.Error:
                    cancel_error["msg"] = (
                        f"Azure Speech canceled (code={getattr(evt, 'error_code', '?')}): "
                        f"{getattr(evt, 'error_details', '') or evt}"
                    )
                    LOGGER.error(cancel_error["msg"])
                done.set()

            def _on_stop(evt):
                done.set()

            recognizer.recognized.connect(_on_recognized)
            recognizer.session_stopped.connect(_on_stop)
            recognizer.canceled.connect(_on_canceled)

            recognizer.start_continuous_recognition()
            finished = done.wait(timeout=RECOGNITION_TIMEOUT_S)
            recognizer.stop_continuous_recognition()

            if not finished:
                raise NotificationException(
                    debate_id=debate_id,
                    service_name="Transcriber.transcribe_audio",
                    error_code="TRANSCRIPTION_ERROR",
                    error_message=f"Azure Speech recognition timed out after {RECOGNITION_TIMEOUT_S}s",
                )
            if cancel_error:
                raise NotificationException(
                    debate_id=debate_id,
                    service_name="Transcriber.transcribe_audio",
                    error_code="TRANSCRIPTION_ERROR",
                    error_message=cancel_error["msg"],
                )

            transcript = " ".join(segments).replace("...", "").strip()
            LOGGER.info(
                f"Transcription completed for {audio_path} "
                f"({len(segments)} phrase(s), {len(transcript)} chars)"
            )
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
        finally:
            # Clean up both the temp normalised copy and the original download.
            if pcm_path and pcm_path != audio_path:
                self._delete_file(pcm_path)
            self._delete_file(audio_path)

    def _to_azure_pcm(self, audio_path: str) -> str:
        """Return a path to a 16 kHz / mono / 16-bit PCM WAV copy of audio_path.

        Short-circuits and returns the original path if it is already compatible.
        """
        try:
            audio = AudioSegment.from_file(audio_path)
            if (
                audio.frame_rate == AZURE_SAMPLE_RATE
                and audio.channels == AZURE_CHANNELS
                and audio.sample_width == AZURE_SAMPLE_WIDTH
            ):
                return audio_path

            audio = (
                audio.set_frame_rate(AZURE_SAMPLE_RATE)
                .set_channels(AZURE_CHANNELS)
                .set_sample_width(AZURE_SAMPLE_WIDTH)
            )
            pcm_path = f"{audio_path}.16k.wav"
            audio.export(pcm_path, format="wav")
            LOGGER.info(f"Normalised {audio_path} -> 16kHz/mono/16-bit PCM for Azure Speech")
            return pcm_path
        except Exception as e:
            raise NotificationException(
                debate_id=self.debate_id,
                service_name="Transcriber.to_azure_pcm",
                error_code="TRANSCRIPTION_ERROR",
                error_message=f"Failed to normalise audio for Azure Speech: {e}",
            )

    def _delete_file(self, audio_path: str) -> None:
        """Delete a temp audio file. Cleanup failure must never mask the transcription result."""
        try:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
                LOGGER.debug(f"Deleted audio file: {audio_path}")
        except Exception as e:
            LOGGER.warning(f"Could not delete {audio_path}: {e}")
