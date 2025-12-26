# Auto Shorts Video Generator

AI-powered short video generator using Gemini, Grok, and Edge TTS.

## Features

- **Gemini Image Generation** - Generate high-quality images from text prompts with automatic watermark removal
- **Grok Video Generation** - Convert images to cinematic video clips using Grok AI
- **Gemini Pro Multi-Account** - Support for 3 Gemini Pro accounts (9 videos/day limit)
- **Edge TTS Voice Generation** - Natural voice synthesis with word-level timing
- **Subtitle Sync** - Automatic subtitle generation synchronized with voice
- **Video Rendering** - Combine videos, voice, and subtitles into final output
- **Web UI** - Easy-to-use web interface for project management

## System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Script Input   │────▶│  Gemini/Gemini  │────▶│  Image Output   │
│  (Text Prompts) │     │  Pro (Images)   │     │  (Cleaned)      │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Final Video    │◀────│  Video Renderer │◀────│  Grok Video     │
│  (With Voice)   │     │  (FFmpeg)       │     │  Generation     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               ▲
                               │
                        ┌──────┴──────┐
                        │  Edge TTS   │
                        │  (Voice +   │
                        │  Subtitles) │
                        └─────────────┘
```

## Installation

### Prerequisites

- Python 3.9+
- Google Chrome browser
- FFmpeg (for video processing)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/AyvatH/auto-shorts.git
cd auto-shorts
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install FFmpeg (macOS):
```bash
brew install ffmpeg
```

## Usage

### Start the Web UI

```bash
python app.py
```

Then open http://localhost:5050 in your browser.

### Workflow

#### Option 1: Gemini + Grok (Standard)

1. Enter your video script with image and video prompts
2. Click "Start" to generate images with Gemini
3. System automatically creates videos with Grok
4. Final render combines everything with voice and subtitles

#### Option 2: Gemini Pro (Multi-Account)

1. Go to "Gemini Pro" tab
2. Setup accounts (3 Google accounts supported)
3. Login to each account
4. Verify accounts are ready
5. Enter script and start generation (up to 9 videos/day)

### Script Format

```
IMAGE 1: [image prompt]
VIDEO 1: [video/camera prompt]

IMAGE 2: [image prompt]
VIDEO 2: [video/camera prompt]

...

VOICE: [narration text]
```

## Project Structure

```
auto-shorts/
├── app.py                    # Flask web application
├── generator.py              # Gemini image generator
├── grok_video_generator.py   # Grok video generator
├── gemini_pro_manager.py     # Gemini Pro multi-account manager
├── video_renderer.py         # Final video rendering with TTS
├── watermark_remover.py      # Gemini watermark removal
├── video_watermark_remover.py # Veo video watermark removal
├── complete_project.py       # Missing items completion
├── config.py                 # Configuration settings
├── templates/
│   └── index.html           # Web UI template
└── requirements.txt         # Python dependencies
```

## Configuration

Edit `config.py` for custom settings:

```python
PROJECTS_DIR = "projects"           # Output directory
GEMINI_URL = "https://gemini.google.com"
GROK_URL = "https://grok.com"
```

## Supported Aspect Ratios

- **9:16** - Vertical (TikTok, Instagram Reels, YouTube Shorts)
- **16:9** - Horizontal (YouTube)
- **1:1** - Square (Instagram)

## License

MIT License

## Acknowledgments

- [Gemini](https://gemini.google.com) - Image generation
- [Grok](https://grok.com) - Video generation
- [Edge TTS](https://github.com/rany2/edge-tts) - Text-to-speech
- [undetected-chromedriver](https://github.com/ultrafunkamsterdam/undetected-chromedriver) - Browser automation
