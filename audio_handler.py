#!/usr/bin/env python3
"""
ALSA Audio Handler for Voice Chat Application
Handles audio recording and playback using ALSA.
"""

import asyncio
import logging
import alsaaudio
from typing import Optional

logger = logging.getLogger(__name__)


class AudioHandler:
    """Handles audio input/output using ALSA."""

    def __init__(
        self,
        sample_rate: int = 16000,
        sample_width: int = 2,
        channels: int = 1,
        period_size: int = 1024,
        device: str = "default",
    ):
        """
        Initialize the audio handler.

        Args:
            sample_rate: Audio sample rate in Hz
            sample_width: Audio sample width in bytes (2 for 16-bit)
            channels: Number of audio channels (1 for mono, 2 for stereo)
            period_size: ALSA period size in frames
            device: ALSA device name
        """
        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self.channels = channels
        self.period_size = period_size
        self.device = device

        self.is_recording = False
        self.pcm_input: Optional[alsaaudio.PCM] = None
        self.pcm_output: Optional[alsaaudio.PCM] = None

        # Determine ALSA format based on sample width
        if sample_width == 2:
            self.format = alsaaudio.PCM_FORMAT_S16_LE
        elif sample_width == 4:
            self.format = alsaaudio.PCM_FORMAT_S32_LE
        else:
            raise ValueError(f"Unsupported sample width: {sample_width}")

    def _init_input(self):
        """Initialize ALSA input (microphone)."""
        try:
            self.pcm_input = alsaaudio.PCM(
                type=alsaaudio.PCM_CAPTURE,
                mode=alsaaudio.PCM_NORMAL,
                device=self.device,
            )

            # Set audio parameters
            self.pcm_input.setchannels(self.channels)
            self.pcm_input.setrate(self.sample_rate)
            self.pcm_input.setformat(self.format)
            self.pcm_input.setperiodsize(self.period_size)

            logger.info(
                f"ALSA input initialized: {self.sample_rate}Hz, "
                f"{self.channels} channel(s), {self.sample_width * 8}-bit"
            )

        except alsaaudio.ALSAAudioError as e:
            logger.error(f"Failed to initialize ALSA input: {e}")
            raise

    def _init_output(self):
        """Initialize ALSA output (speaker)."""
        try:
            self.pcm_output = alsaaudio.PCM(
                type=alsaaudio.PCM_PLAYBACK,
                mode=alsaaudio.PCM_NORMAL,
                device=self.device,
            )

            # Set audio parameters
            self.pcm_output.setchannels(self.channels)
            self.pcm_output.setrate(self.sample_rate)
            self.pcm_output.setformat(self.format)
            self.pcm_output.setperiodsize(self.period_size)

            logger.info(
                f"ALSA output initialized: {self.sample_rate}Hz, "
                f"{self.channels} channel(s), {self.sample_width * 8}-bit"
            )

        except alsaaudio.ALSAAudioError as e:
            logger.error(f"Failed to initialize ALSA output: {e}")
            raise

    async def record_to_queue(self, audio_queue: asyncio.Queue):
        """
        Record audio from microphone and put chunks into queue.

        Args:
            audio_queue: Queue to put audio chunks into
        """
        if self.pcm_input is None:
            self._init_input()

        self.is_recording = True
        logger.info("Started recording")

        try:
            while self.is_recording:
                # Read audio data
                length, data = self.pcm_input.read()

                if length > 0:
                    # Put audio chunk into queue
                    await audio_queue.put(data)

                # Small sleep to allow other tasks to run
                await asyncio.sleep(0.001)

        except Exception as e:
            logger.error(f"Error during recording: {e}")
            raise
        finally:
            logger.info("Stopped recording")

    def stop_recording(self):
        """Stop recording audio."""
        self.is_recording = False

    def record_chunk(self) -> bytes:
        """
        Record a single audio chunk synchronously.

        Returns:
            Audio data as bytes
        """
        if self.pcm_input is None:
            self._init_input()

        length, data = self.pcm_input.read()
        return data if length > 0 else b""

    def play_audio(self, audio_data: bytes):
        """
        Play audio data through speakers.

        Args:
            audio_data: Raw audio data to play
        """
        if self.pcm_output is None:
            self._init_output()

        logger.info(f"Playing {len(audio_data)} bytes of audio")

        try:
            # Write audio data in chunks
            chunk_size = self.period_size * self.sample_width * self.channels
            offset = 0

            while offset < len(audio_data):
                chunk = audio_data[offset : offset + chunk_size]
                self.pcm_output.write(chunk)
                offset += chunk_size

            logger.info("Finished playing audio")

        except alsaaudio.ALSAAudioError as e:
            logger.error(f"Error during playback: {e}")
            raise

    async def play_audio_async(self, audio_data: bytes):
        """
        Play audio data asynchronously.

        Args:
            audio_data: Raw audio data to play
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.play_audio, audio_data)

    def cleanup(self):
        """Clean up audio resources."""
        self.is_recording = False

        if self.pcm_input is not None:
            try:
                self.pcm_input.close()
            except Exception as e:
                logger.error(f"Error closing input: {e}")
            self.pcm_input = None

        if self.pcm_output is not None:
            try:
                self.pcm_output.close()
            except Exception as e:
                logger.error(f"Error closing output: {e}")
            self.pcm_output = None

        logger.info("Audio handler cleaned up")

    def __del__(self):
        """Destructor to ensure cleanup."""
        self.cleanup()
