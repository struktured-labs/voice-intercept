#!/usr/bin/env python3
"""
Voice Chat Application
Uses ALSA for audio and Wyoming services for wake word, STT, and TTS.
"""

import asyncio
import wave
import struct
from pathlib import Path
from typing import Optional
import logging

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncClient
from wyoming.wake import Detect, Detection
from wyoming.asr import Transcribe, Transcript
from wyoming.tts import Synthesize
from wyoming.info import Describe, Info

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_text(text: str) -> str:
    """
    Process recognized text and return a response.

    This is a placeholder function that you should customize with your logic.

    Args:
        text: The recognized text from speech-to-text

    Returns:
        The response text to be spoken
    """
    logger.info(f"Processing text: {text}")

    # TODO: Implement your custom logic here
    # For now, just echo back with a prefix
    response = f"You said: {text}"

    return response


class VoiceChatApp:
    """Main voice chat application using Wyoming services."""

    def __init__(
        self,
        wake_word_uri: str = "tcp://127.0.0.1:10400",
        stt_uri: str = "tcp://127.0.0.1:10300",
        tts_uri: str = "tcp://127.0.0.1:10200",
        sample_rate: int = 16000,
        sample_width: int = 2,
        channels: int = 1,
    ):
        """
        Initialize the voice chat application.

        Args:
            wake_word_uri: Wyoming wake word service URI
            stt_uri: Wyoming speech-to-text service URI
            tts_uri: Wyoming text-to-speech service URI
            sample_rate: Audio sample rate in Hz
            sample_width: Audio sample width in bytes
            channels: Number of audio channels
        """
        self.wake_word_uri = wake_word_uri
        self.stt_uri = stt_uri
        self.tts_uri = tts_uri

        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self.channels = channels

        self.is_running = False

    async def connect_wake_word(self) -> AsyncClient:
        """Connect to the wake word detection service."""
        logger.info(f"Connecting to wake word service at {self.wake_word_uri}")
        client = AsyncClient.from_uri(self.wake_word_uri)
        await client.connect()

        # Get service info
        await client.write_event(Describe().event())
        info_event = await client.read_event()
        if info_event:
            info = Info.from_event(info_event)
            logger.info(f"Wake word service: {info}")

        return client

    async def connect_stt(self) -> AsyncClient:
        """Connect to the speech-to-text service."""
        logger.info(f"Connecting to STT service at {self.stt_uri}")
        client = AsyncClient.from_uri(self.stt_uri)
        await client.connect()

        # Get service info
        await client.write_event(Describe().event())
        info_event = await client.read_event()
        if info_event:
            info = Info.from_event(info_event)
            logger.info(f"STT service: {info}")

        return client

    async def connect_tts(self) -> AsyncClient:
        """Connect to the text-to-speech service."""
        logger.info(f"Connecting to TTS service at {self.tts_uri}")
        client = AsyncClient.from_uri(self.tts_uri)
        await client.connect()

        # Get service info
        await client.write_event(Describe().event())
        info_event = await client.read_event()
        if info_event:
            info = Info.from_event(info_event)
            logger.info(f"TTS service: {info}")

        return client

    async def detect_wake_word(self, audio_queue: asyncio.Queue) -> bool:
        """
        Listen for wake word detection.

        Args:
            audio_queue: Queue containing audio chunks from microphone

        Returns:
            True if wake word detected
        """
        client = await self.connect_wake_word()

        try:
            # Send detect command
            await client.write_event(Detect().event())

            # Stream audio
            await client.write_event(
                AudioStart(
                    rate=self.sample_rate,
                    width=self.sample_width,
                    channels=self.channels,
                ).event()
            )

            # Read audio from queue and send to wake word service
            detection_task = asyncio.create_task(self._read_detection(client))
            audio_task = asyncio.create_task(self._stream_audio_to_service(client, audio_queue))

            # Wait for detection
            detected = await detection_task

            # Cancel audio streaming
            audio_task.cancel()
            try:
                await audio_task
            except asyncio.CancelledError:
                pass

            await client.write_event(AudioStop().event())

            return detected

        finally:
            await client.disconnect()

    async def _read_detection(self, client: AsyncClient) -> bool:
        """Read detection event from wake word service."""
        while True:
            event = await client.read_event()
            if event is None:
                return False

            if Detection.is_type(event.type):
                detection = Detection.from_event(event)
                logger.info(f"Wake word detected: {detection.name}")
                return True

    async def _stream_audio_to_service(self, client: AsyncClient, audio_queue: asyncio.Queue):
        """Stream audio chunks to a Wyoming service."""
        while True:
            audio_chunk = await audio_queue.get()
            await client.write_event(
                AudioChunk(
                    rate=self.sample_rate,
                    width=self.sample_width,
                    channels=self.channels,
                    audio=audio_chunk,
                ).event()
            )

    async def recognize_speech(self, audio_queue: asyncio.Queue, timeout: float = 10.0) -> Optional[str]:
        """
        Recognize speech from audio stream.

        Args:
            audio_queue: Queue containing audio chunks
            timeout: Maximum time to wait for speech

        Returns:
            Recognized text or None
        """
        client = await self.connect_stt()

        try:
            # Send transcribe command
            await client.write_event(Transcribe().event())

            # Stream audio
            await client.write_event(
                AudioStart(
                    rate=self.sample_rate,
                    width=self.sample_width,
                    channels=self.channels,
                ).event()
            )

            # Read audio from queue and send to STT service
            transcript_task = asyncio.create_task(self._read_transcript(client))
            audio_task = asyncio.create_task(self._stream_audio_to_service(client, audio_queue))

            # Wait for transcript with timeout
            try:
                text = await asyncio.wait_for(transcript_task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("Speech recognition timed out")
                text = None

            # Cancel audio streaming
            audio_task.cancel()
            try:
                await audio_task
            except asyncio.CancelledError:
                pass

            await client.write_event(AudioStop().event())

            return text

        finally:
            await client.disconnect()

    async def _read_transcript(self, client: AsyncClient) -> Optional[str]:
        """Read transcript event from STT service."""
        while True:
            event = await client.read_event()
            if event is None:
                return None

            if Transcript.is_type(event.type):
                transcript = Transcript.from_event(event)
                logger.info(f"Transcript: {transcript.text}")
                return transcript.text

    async def synthesize_speech(self, text: str) -> bytes:
        """
        Synthesize speech from text.

        Args:
            text: Text to synthesize

        Returns:
            Audio data as bytes
        """
        client = await self.connect_tts()

        try:
            # Send synthesize command
            await client.write_event(Synthesize(text=text).event())

            # Collect audio chunks
            audio_data = bytearray()

            while True:
                event = await client.read_event()
                if event is None:
                    break

                if AudioChunk.is_type(event.type):
                    chunk = AudioChunk.from_event(event)
                    audio_data.extend(chunk.audio)
                elif AudioStop.is_type(event.type):
                    break

            logger.info(f"Synthesized {len(audio_data)} bytes of audio")
            return bytes(audio_data)

        finally:
            await client.disconnect()

    async def run(self):
        """Run the main voice chat loop."""
        from audio_handler import AudioHandler

        self.is_running = True
        audio_handler = AudioHandler(
            sample_rate=self.sample_rate,
            sample_width=self.sample_width,
            channels=self.channels,
        )

        logger.info("Voice chat application started")
        logger.info("Listening for wake word...")

        try:
            while self.is_running:
                # Create audio queue for wake word detection
                wake_audio_queue = asyncio.Queue()

                # Start recording for wake word
                record_task = asyncio.create_task(
                    audio_handler.record_to_queue(wake_audio_queue)
                )

                # Wait for wake word
                detected = await self.detect_wake_word(wake_audio_queue)

                # Stop recording
                audio_handler.stop_recording()
                record_task.cancel()
                try:
                    await record_task
                except asyncio.CancelledError:
                    pass

                if not detected:
                    continue

                logger.info("Wake word detected! Listening for speech...")

                # Create audio queue for speech recognition
                stt_audio_queue = asyncio.Queue()

                # Start recording for speech
                record_task = asyncio.create_task(
                    audio_handler.record_to_queue(stt_audio_queue)
                )

                # Recognize speech
                text = await self.recognize_speech(stt_audio_queue)

                # Stop recording
                audio_handler.stop_recording()
                record_task.cancel()
                try:
                    await record_task
                except asyncio.CancelledError:
                    pass

                if text:
                    # Process the recognized text
                    response = process_text(text)

                    if response:
                        logger.info(f"Response: {response}")

                        # Synthesize and play response
                        audio_data = await self.synthesize_speech(response)
                        audio_handler.play_audio(audio_data)

                logger.info("Listening for wake word...")

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.is_running = False
            audio_handler.cleanup()


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Voice Chat Application")
    parser.add_argument(
        "--wake-word-uri",
        default="tcp://127.0.0.1:10400",
        help="Wyoming wake word service URI (default: tcp://127.0.0.1:10400)",
    )
    parser.add_argument(
        "--stt-uri",
        default="tcp://127.0.0.1:10300",
        help="Wyoming STT service URI (default: tcp://127.0.0.1:10300)",
    )
    parser.add_argument(
        "--tts-uri",
        default="tcp://127.0.0.1:10200",
        help="Wyoming TTS service URI (default: tcp://127.0.0.1:10200)",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="Audio sample rate in Hz (default: 16000)",
    )

    args = parser.parse_args()

    app = VoiceChatApp(
        wake_word_uri=args.wake_word_uri,
        stt_uri=args.stt_uri,
        tts_uri=args.tts_uri,
        sample_rate=args.sample_rate,
    )

    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
