"""WhisperLive-compatible websocket server that uses Azure AI Speech.

ATTS-CSP talks to WhisperLive, which needs a GPU. The protocol:
  1. client sends one JSON config message: {uid, language, task, model, use_vad}
  2. client sends audio as binary frames: float32 little-endian, 16 kHz, mono
  3. server sends {"uid": ..., "segments": [{"id", "start", "end", "text",
     "completed"}]}, with start/end in seconds from the start of the stream

This server implements that protocol on top of Azure Speech continuous
recognition, so kdai3 needs no changes. It only sends final results
(completed=true), which is all CSP's SegmentBuffer uses.

Plain HTTP GETs, like the backend's ATTS_WHISPERLIVE_URL health check, get a
200 "OK" from process_request.

Env: SPEECH_KEY, SPEECH_REGION (required), SPEECH_LANGUAGE (default nl-NL),
     WHISPERLIVE_PORT (default 9090), SPEECH_SEGMENTATION_SILENCE_MS (optional).
"""

import asyncio
import http
import itertools
import json
import logging
import os
import sys

import numpy as np
import websockets
import azure.cognitiveservices.speech as speechsdk

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
LOGGER = logging.getLogger("whisperlive-shim")

SPEECH_KEY = os.getenv("SPEECH_KEY", "")
SPEECH_REGION = os.getenv("SPEECH_REGION", "")
LANGUAGE = os.getenv("SPEECH_LANGUAGE", "nl-NL")
PORT = int(os.getenv("WHISPERLIVE_PORT", "9090"))
SEGMENTATION_SILENCE_MS = os.getenv("SPEECH_SEGMENTATION_SILENCE_MS", "")

if not SPEECH_KEY or not SPEECH_REGION:
    LOGGER.error("SPEECH_KEY and SPEECH_REGION must be set")
    sys.exit(1)


async def handle_client(websocket):
    peer = websocket.remote_address
    LOGGER.info("Client connected: %s", peer)

    # The first frame should be the JSON config, but some clients start with audio.
    uid = ""
    first_audio = None
    try:
        first = await websocket.recv()
    except websockets.exceptions.ConnectionClosed:
        LOGGER.info("Client %s closed before sending config", peer)
        return
    if isinstance(first, (bytes, bytearray)):
        first_audio = first
        LOGGER.warning("Client %s sent audio before config; using defaults", peer)
    else:
        try:
            cfg = json.loads(first)
            uid = str(cfg.get("uid", ""))
            LOGGER.info("Client %s config: %s", peer, cfg)
        except json.JSONDecodeError:
            LOGGER.warning("Client %s sent non-JSON config: %.100s", peer, first)

    loop = asyncio.get_running_loop()
    seg_ids = itertools.count()

    stream_format = speechsdk.audio.AudioStreamFormat(
        samples_per_second=16000, bits_per_sample=16, channels=1
    )
    push_stream = speechsdk.audio.PushAudioInputStream(stream_format=stream_format)

    speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
    speech_config.speech_recognition_language = LANGUAGE
    if SEGMENTATION_SILENCE_MS:
        speech_config.set_property(
            speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs,
            SEGMENTATION_SILENCE_MS,
        )

    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=speechsdk.audio.AudioConfig(stream=push_stream),
    )

    def send_json(payload):
        # Speech SDK callbacks run on SDK threads, not the event loop.
        asyncio.run_coroutine_threadsafe(websocket.send(json.dumps(payload)), loop)

    def on_recognized(evt):
        result = evt.result
        if result.reason != speechsdk.ResultReason.RecognizedSpeech or not result.text:
            return
        start = result.offset / 10_000_000.0  # 100-ns ticks -> seconds
        end = start + result.duration / 10_000_000.0
        LOGGER.info("[%s] %.1fs-%.1fs: %s", uid or "?", start, end, result.text)
        send_json(
            {
                "uid": uid,
                "segments": [
                    {
                        "id": f"azure-{next(seg_ids)}",
                        "start": start,
                        "end": end,
                        "text": result.text,
                        "completed": True,
                    }
                ],
            }
        )

    def on_canceled(evt):
        if evt.reason == speechsdk.CancellationReason.Error:
            msg = f"Azure Speech error {evt.error_code}: {evt.error_details}"
            LOGGER.error("[%s] %s", uid or "?", msg)
            send_json({"uid": uid, "type": "error", "message": msg})
        else:
            LOGGER.info("[%s] recognition canceled: %s", uid or "?", evt.reason)

    recognizer.recognized.connect(on_recognized)
    recognizer.canceled.connect(on_canceled)
    recognizer.session_stopped.connect(
        lambda evt: LOGGER.info("[%s] session stopped", uid or "?")
    )
    recognizer.start_continuous_recognition_async().get()
    LOGGER.info("[%s] Azure Speech continuous recognition started (%s)", uid or "?", LANGUAGE)

    def feed(frame: bytes):
        # float32 from the client, Azure wants int16 PCM
        samples = np.frombuffer(frame, dtype="<f4")
        if samples.size == 0:
            return
        pcm16 = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2")
        push_stream.write(pcm16.tobytes())

    try:
        if first_audio is not None:
            feed(first_audio)
        async for message in websocket:
            if isinstance(message, (bytes, bytearray)):
                feed(message)
            else:
                # text control frames like END_OF_AUDIO are ignored
                LOGGER.debug("[%s] control message: %.100s", uid or "?", message)
    except websockets.exceptions.ConnectionClosed:
        LOGGER.info("[%s] client disconnected", uid or "?")
    finally:
        try:
            push_stream.close()
        except Exception:
            pass
        recognizer.stop_continuous_recognition_async()
        LOGGER.info("[%s] connection cleaned up", uid or "?")


async def process_request(path, request_headers):
    """Answer plain HTTP health checks; websocket upgrades go through."""
    if request_headers.get("Upgrade", "").lower() != "websocket":
        return (http.HTTPStatus.OK, [("Content-Type", "text/plain")], b"OK\n")
    return None


async def main():
    LOGGER.info("Starting WhisperLive shim on :%d (Azure Speech %s, %s)", PORT, SPEECH_REGION, LANGUAGE)
    async with websockets.serve(
        handle_client,
        "0.0.0.0",
        PORT,
        process_request=process_request,
        max_size=2**23,
        ping_interval=20,
        ping_timeout=20,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
