# Voice Chat Application

A Python voice chat application that uses ALSA for audio and Wyoming services for wake word detection, speech-to-text, and text-to-speech.

## Features

- Wake word detection using Wyoming protocol
- Speech-to-text (STT) recognition
- Text-to-speech (TTS) synthesis
- ALSA audio input/output
- Customizable text processing via `process_text` function

## Requirements

- Python 3.8+
- ALSA audio system (Linux)
- Wyoming services running:
  - Wake word detection service
  - Speech-to-text service
  - Text-to-speech service

## Installation

1. Install system dependencies:

```bash
# On Ubuntu/Debian
sudo apt-get install python3-dev libasound2-dev

# On Fedora/RHEL
sudo dnf install python3-devel alsa-lib-devel
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Wyoming Services Setup

You need to have Wyoming-compatible services running. Here are some common options:

### Wake Word Detection

```bash
# Using wyoming-openwakeword
pip install wyoming-openwakeword
python -m wyoming_openwakeword --uri tcp://0.0.0.0:10400
```

### Speech-to-Text

```bash
# Using wyoming-faster-whisper
pip install wyoming-faster-whisper
python -m wyoming_faster_whisper --uri tcp://0.0.0.0:10300 --model tiny-int8
```

### Text-to-Speech

```bash
# Using wyoming-piper
pip install wyoming-piper
python -m wyoming_piper --uri tcp://0.0.0.0:10200 --voice en_US-lessac-medium
```

## Usage

### Basic Usage

Run the voice chat application with default settings:

```bash
python voice_chat.py
```

### Custom Configuration

Specify custom Wyoming service URIs:

```bash
python voice_chat.py \
  --wake-word-uri tcp://192.168.1.10:10400 \
  --stt-uri tcp://192.168.1.11:10300 \
  --tts-uri tcp://192.168.1.12:10200 \
  --sample-rate 16000
```

### Command-line Arguments

- `--wake-word-uri`: Wyoming wake word service URI (default: tcp://127.0.0.1:10400)
- `--stt-uri`: Wyoming STT service URI (default: tcp://127.0.0.1:10300)
- `--tts-uri`: Wyoming TTS service URI (default: tcp://127.0.0.1:10200)
- `--sample-rate`: Audio sample rate in Hz (default: 16000)

## Customization

### Process Text Function

The `process_text` function in `voice_chat.py` is called when speech is recognized. Customize this function to implement your own logic:

```python
def process_text(text: str) -> str:
    """
    Process recognized text and return a response.

    Args:
        text: The recognized text from speech-to-text

    Returns:
        The response text to be spoken
    """
    # Your custom logic here
    response = f"You said: {text}"
    return response
```

### Audio Configuration

You can customize audio settings in the `AudioHandler` class in `audio_handler.py`:

- `sample_rate`: Audio sample rate (default: 16000 Hz)
- `sample_width`: Sample width in bytes (default: 2 for 16-bit)
- `channels`: Number of channels (default: 1 for mono)
- `period_size`: ALSA period size (default: 1024 frames)
- `device`: ALSA device name (default: "default")

## How It Works

1. The application continuously listens for a wake word using the Wyoming wake word service
2. When the wake word is detected, it starts recording audio
3. The recorded audio is sent to the Wyoming STT service for transcription
4. The transcribed text is passed to the `process_text` function
5. The response from `process_text` is synthesized to speech using the Wyoming TTS service
6. The synthesized audio is played through the speakers
7. The application returns to listening for the wake word

## Architecture

```
┌─────────────────────────────────────────────────┐
│           Voice Chat Application                │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │ Wake Word  │  │     STT     │  │   TTS    │ │
│  │  Client    │  │   Client    │  │  Client  │ │
│  └─────┬──────┘  └──────┬──────┘  └────┬─────┘ │
│        │                │               │       │
│        └────────────────┼───────────────┘       │
│                         │                       │
│                  ┌──────▼──────┐                │
│                  │ process_text│                │
│                  │  function   │                │
│                  └─────────────┘                │
│                                                  │
│                  ┌─────────────┐                │
│                  │    ALSA     │                │
│                  │Audio Handler│                │
│                  └─────────────┘                │
└─────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
  ┌─────────────┐              ┌─────────────┐
  │ Microphone  │              │  Speaker    │
  └─────────────┘              └─────────────┘
```

## Troubleshooting

### No audio input detected

- Check that your microphone is properly connected
- Verify ALSA is working: `arecord -l`
- Test recording: `arecord -f S16_LE -r 16000 test.wav`

### No audio output

- Check that speakers/headphones are connected
- Verify ALSA is working: `aplay -l`
- Test playback: `aplay test.wav`

### Wyoming services not connecting

- Ensure all Wyoming services are running
- Check that the URIs are correct
- Verify network connectivity if using remote services

### Permission errors

- Ensure your user has access to audio devices
- Add your user to the `audio` group: `sudo usermod -a -G audio $USER`
- Log out and log back in for changes to take effect

## License

MIT
