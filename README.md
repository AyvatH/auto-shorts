# Auto Shorts Video Generator

AI-powered short video generator using Gemini, Grok, and Edge TTS. Automatically creates viral-ready vertical videos for TikTok, Instagram Reels, and YouTube Shorts.

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
- Google account (for Gemini)
- X/Twitter account (for Grok)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/AyvatH/auto-shorts.git
cd auto-shorts
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Install FFmpeg:
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
choco install ffmpeg
```

## Quick Start

### 1. Start the Application

```bash
python app.py
```

Open http://localhost:5050 in your browser.

### 2. First Time Setup

When you first run the app, Chrome browsers will open for:
- **Gemini** - Login with your Google account
- **Grok** - Login with your X/Twitter account

These sessions are saved, so you only need to login once.

## Usage Guide

### Option 1: Gemini + Grok (Standard Mode)

This mode uses free Gemini for images and Grok for videos.

#### Step 1: Prepare Your Script

Enter your script in the text area. Format:

```
IMAGE 1: A glowing human brain with neural connections lighting up, dark background, cinematic lighting
VIDEO 1: CAMERA: slow zoom into brain | neural pathways activating | subtle particle effects

IMAGE 2: Closeup of neurons firing electrical signals, blue and purple colors
VIDEO 2: CAMERA: tracking shot following electrical signal | smooth motion | dark atmosphere

IMAGE 3: Wide shot of entire nervous system in human body silhouette
VIDEO 3: CAMERA: pull back reveal shot | body silhouette with glowing nerves | cinematic

THUMBNAIL: Dramatic brain visualization with electric effects, bold colors, eye-catching

VOICE: Your brain contains 86 billion neurons. Each one can connect to thousands of others. Right now, as you watch this, electrical signals are racing through your neural pathways at 270 miles per hour. This is how you think, feel, and experience the world.
```

#### Step 2: Configure Settings

- **Aspect Ratio**: Choose 9:16 (vertical), 16:9 (horizontal), or 1:1 (square)
- **Voice Style**: friendly, professional, or dramatic

#### Step 3: Generate

1. Click **"Başlat"** (Start)
2. Watch progress in real-time
3. Images are generated first (Gemini)
4. Then videos are created (Grok)
5. Final render combines everything

#### Step 4: Download

Once complete, download your final video from the project panel.

---

### Option 2: Gemini Pro (Multi-Account Mode)

This mode uses Gemini Pro for both images AND videos (no Grok needed). Supports up to 3 accounts for 9 videos per day.

#### Step 1: Setup Accounts

1. Go to **"Gemini Pro"** tab
2. Click **"Hesapları Kur"** (Setup Accounts)
3. Three Chrome windows will open
4. Login to a different Google account in each window
5. Click **"Doğrula"** (Verify) to confirm all accounts are ready

#### Step 2: Prepare Your Script

Same format as standard mode, but Gemini Pro creates both images and videos:

```
IMAGE 1: Muscle fibers under microscope, dramatic lighting
VIDEO 1: CAMERA: slow dolly in | reveal muscle structure | cinematic

IMAGE 2: ATP molecules powering muscle contraction
VIDEO 2: CAMERA: macro shot | energy particles flowing | smooth motion

...

VOICE: Your muscles are biological machines...
```

#### Step 3: Generate

1. Click **"Başlat"** (Start)
2. System distributes work across 3 accounts
3. Each account handles 3 image+video pairs
4. Automatic watermark removal
5. Final render with voice and subtitles

#### Daily Limits

| Accounts | Daily Video Limit |
|----------|-------------------|
| 1        | 3 videos          |
| 2        | 6 videos          |
| 3        | 9 videos          |

Limits reset at midnight.

---

### Fixing Missing Items

If some images or videos fail:

1. Go to your project
2. Click **"Eksikleri Gider"** (Fix Missing)
3. System automatically detects and regenerates failed items
4. Re-renders final video

---

## Script Writing Tips

### Image Prompts
- Be specific about lighting, colors, and mood
- Include style keywords: cinematic, dramatic, macro, wide shot
- Specify aspect ratio context: "vertical composition" for 9:16

### Video Prompts
- Start with CAMERA: to specify camera movement
- Include: shot type, motion direction, speed, atmosphere
- Examples:
  - `CAMERA: slow zoom in | focused on subject | shallow depth of field`
  - `CAMERA: orbit shot | 360 rotation | smooth motion`
  - `CAMERA: tracking shot | follow subject | dynamic movement`

### Voice Text
- Write naturally, as if speaking
- Use short sentences for better pacing
- Include pauses with periods
- Aim for 130-150 words per minute

---

## Project Structure

```
auto-shorts/
├── app.py                     # Flask web application (port 5050)
├── generator.py               # Gemini image generator
├── grok_video_generator.py    # Grok video generator
├── gemini_pro_manager.py      # Gemini Pro multi-account manager
├── video_renderer.py          # Final video rendering with Edge TTS
├── watermark_remover.py       # Gemini watermark removal
├── video_watermark_remover.py # Veo video watermark removal
├── complete_project.py        # Missing items completion
├── config.py                  # Configuration settings
├── templates/
│   └── index.html            # Web UI template
├── projects/                  # Generated projects (gitignored)
├── chrome_profile/            # Gemini browser session (gitignored)
└── chrome_profile_grok/       # Grok browser session (gitignored)
```

## Configuration

Edit `config.py`:

```python
# Output directory for projects
PROJECTS_DIR = "projects"

# URLs
GEMINI_URL = "https://gemini.google.com"
GROK_URL = "https://grok.com"

# Timeouts (seconds)
IMAGE_GENERATION_TIMEOUT = 120
VIDEO_GENERATION_TIMEOUT = 180
```

## Supported Formats

### Aspect Ratios
| Format | Resolution | Use Case |
|--------|------------|----------|
| 9:16   | 1080x1920  | TikTok, Reels, Shorts |
| 16:9   | 1920x1080  | YouTube, Twitter |
| 1:1    | 1080x1080  | Instagram Feed |

### Voice Styles
- **friendly** - Casual, conversational tone
- **professional** - Clear, authoritative tone
- **dramatic** - Intense, engaging tone

## Troubleshooting

### "Browser not starting"
- Make sure Chrome is installed
- Delete `chrome_profile/` folder and restart

### "Login required"
- Browser session expired
- Delete profile folder and login again

### "Video generation timeout"
- Grok/Gemini servers may be slow
- Try again or use "Fix Missing" feature

### "Watermark not removed"
- Watermark detection may fail on some images
- Manual editing may be required

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI |
| `/api/start` | POST | Start generation |
| `/api/progress` | GET | Get current progress |
| `/api/projects` | GET | List all projects |
| `/api/complete` | POST | Fix missing items |
| `/api/render` | POST | Render final video |
| `/api/gemini-pro/setup` | POST | Setup Gemini Pro accounts |
| `/api/gemini-pro/verify` | POST | Verify accounts |
| `/api/gemini-pro/start` | POST | Start Gemini Pro generation |

## Dependencies

- `flask` - Web framework
- `selenium` - Browser automation
- `undetected-chromedriver` - Anti-detection browser
- `edge-tts` - Microsoft Edge text-to-speech
- `Pillow` - Image processing
- `opencv-python` - Video processing
- `numpy` - Numerical operations

## License

MIT License

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Acknowledgments

- [Google Gemini](https://gemini.google.com) - Image & video generation
- [Grok](https://grok.com) - Video generation
- [Edge TTS](https://github.com/rany2/edge-tts) - Text-to-speech
- [undetected-chromedriver](https://github.com/ultrafunkamsterdam/undetected-chromedriver) - Browser automation
