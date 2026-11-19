# 🌴 ClippingTool — Autonomous Video Moments Finder & 9:16 Reels Generator

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/mdyusuf0/ClippingTool)
[![Local First](https://img.shields.io/badge/100%25-Free%20%26%20Local-rose.svg)](https://github.com/mdyusuf0/ClippingTool)

A **100% free, local, open-source AI clipping tool** built for gameplay recordings, stream VODs (**YouTube**, **Kick.com**), live stream broadcasts, and cutscenes.

Automatically detects high-engagement moments, reframes footage into **9:16 vertical shorts (TikTok, Shorts, Reels)**, burns in word-by-word karaoke auto-captions, normalizes audio to **-14 LUFS**, and exports ready-to-publish reels — **running entirely offline on your local machine**.

---

## ⚡ Quickstart (Run in 3 Steps)

### 1. Prerequisites (Install Python & ffmpeg)
- **Python 3.9+**: Download from [python.org](https://www.python.org/downloads/) *(Windows: check "Add Python to PATH")*.
- **ffmpeg**:
  - **Windows**: `winget install Gyan.FFmpeg`
  - **macOS**: `brew install ffmpeg`
  - **Linux**: `sudo apt install ffmpeg`

### 2. Clone & Install
```bash
git clone https://github.com/mdyusuf0/ClippingTool.git
cd ClippingTool
pip install -r requirements.txt
```

### 3. Launch the Studio Web UI
```bash
python main.py --ui
```
Open **`http://127.0.0.1:7860`** in your browser to start clipping!

---

## 🎮 Features at a Glance

- **🎯 Smart Category Presets**: Automatically adapts speech vocabulary, volume spike detection, and scene pacing:
  - 💥 **Action & Shootouts**: Combat intensity, wanted levels, SWAT responses.
  - 🏎️ **Vehicles & Chases**: High-speed pursuits, escapes, precision drifts.
  - 🤣 **Fails & Physics**: Ragdoll glitches, unscripted NPC chaos, hilarious fails.
  - 🎬 **Story & Dialogue**: Cutscenes, lore, character dynamics.
  - 💔 **Dramatic & Emotional**: Tense betrayals, downfalls, emotional turning points.
  - 🌆 **Atmosphere & Scenery**: Vice City sunsets, ocean drives, ambient cruises.
  - 🚀 **Stunts & Aerials**: Ramp jumps, skydiving, physics stunts.
  - 🏆 **Clutch Gameplay**: High-skill gunplay, tactical clutch moments.
- **⚡ Super-Fast Local Engine**:
  - **CUDA GPU Acceleration**: Whisper speech recognition runs in ~2s on NVIDIA GPUs (`ctranslate2`) with CPU `int8` fallback.
  - **Downscaled Scene Detection**: Rapid cut identification without CPU decode lag.
  - **Fast Bokeh Blur Render**: Downscaled two-stage blur renders 10s of vertical video in **~3.2s** at CRF 20.
- **🛑 Mid-Way Cancellation**: Dedicated **Cancel Generation** button to safely abort tasks anytime with instant subprocess termination.
- **📱 9:16 Vertical Video Formats**: Full HD vertical output (1080×1920 @ 30fps). Choose from `blur` (centered video over aesthetic blurred backdrop), `crop` (center crop), or `facecrop` (OpenCV face-tracking pan & crop).
- **🎤 Karaoke Captions**: Burned-in word-by-word subtitles with safe-zone margin padding (presets: `vice_city`, `pop`, `bold`, `minimal`, `none`) + separate `.srt` files.
- **🔊 Studio-Grade Audio**: Automatic EBU R128 loudness normalization to **-14 LUFS** with smooth 0.3s fade-in/fade-out.
- **🌐 Any Media Input**: Local videos (`.mp4`, `.mkv`, `.mov`), online YouTube/Kick links, Google Drive links, and batch text files (`--links-file`).
- **🔴 Active Live Stream Clipping**: Clip ongoing YouTube Live streams and Kick broadcasts on the fly.
- **🤖 Optional Free AI Enhancement**: Works 100% offline using built-in keyword templates. You can optionally provide a free Gemini API key to enhance titles, descriptions, and hashtags.

---

## 🎬 Pre-loaded Viral Reels Showcase (Ready to Play in UI)

The repository comes packaged with **10 pre-rendered viral 9:16 vertical reels** in `rendered_reels/` with matching high-resolution thumbnails in `rendered_reels/thumbnails/`.

When you launch the studio (`python main.py --ui`), open the **Rendered Reels & Exports** tab to immediately preview, play, and copy social captions:
- 📻 **Reel 1**: `xQc Haunted Radio Glitch` — Dynamic webcam & gameplay stack with Vine Boom & Bruh SFX.
- 🍗 **Reel 2**: `Speed KFC & Keanu Reeves Glitch` — Reaction stack with KFC character & Keanu punchlines.
- ⚡ **Reels 3 & 4**: `IShowSpeed Tokyo Girl Hype & Lore Edits` — High-energy trailer hype edits.
- 🚔 **Reels 5 & 6**: `CarryMinati Arrest & Vice City Night Cruising` — Carry reaction & Vice City cruising edits.
- 🌅 **Reels 7 & 10**: `Vice City Beach Sunset & Ocean Drive Neon Drift` — 9:16 full-bleed cinematic landscape & neon drive.
- ❤️ **Reel 8**: `Jason & Lucia "Trust" Relationship Edit` — Cinematic couple lore & story edit.
- ⛓️ **Reel 9**: `Lucia Prison Bad Luck Lore Edit` — Lucia origin story edit.

Includes ready-to-copy Instagram/TikTok captions, hashtag sets, and 1-click package download.

---

## 💻 Command Line (CLI) Usage

Prefer the terminal? Run ClippingTool headlessly:

### 1. Clip a Local Gameplay Video
```bash
python main.py my_gameplay.mp4 --preset action --clips 4 --min 15 --max 35 --style blur --captions vice_city
```

### 2. Clip a YouTube Video (VOD)
```bash
python main.py "https://www.youtube.com/watch?v=VIDEO_ID" --preset funny --clips 4 --i-have-permission
```

### 3. Clip an Ongoing YouTube Live Stream
```bash
python main.py "https://www.youtube.com/live/STREAM_ID" --preset action --clips 3 --live-duration 2 --i-have-permission
```
*(Captures the latest 2 minutes of the stream for rapid extraction).*

### 4. Clip a Kick.com Stream VOD
```bash
python main.py "https://kick.com/video/VOD_ID" --preset chases --clips 4 --i-have-permission
```

### 5. Batch Process from a File
Create `links.txt` with one URL or file path per line, then run:
```bash
python main.py --links-file links.txt --preset stunts --clips 4 --i-have-permission --out output/
```

### 6. Quick Dry-Run (Preview Timestamps Without Rendering)
```bash
python main.py my_gameplay.mp4 --preset action --dry-run
```

---

## ⚙️ CLI Flag Reference

| Flag | Description | Default |
| :--- | :--- | :--- |
| `--ui` | Launch local Gradio Web Studio | `False` |
| `--preset` | Category preset (`action`, `funny`, `serious`, `sad`, `chases`, `cinematic`, `stunts`, `gaming`) | `general` |
| `--clips` | Number of clips to extract | `5` |
| `--min` / `--max` | Minimum and maximum clip duration in seconds | `15` / `45` |
| `--style` | Framing: `blur` (recommended), `crop`, or `facecrop` | `blur` |
| `--captions` | Caption style: `vice_city`, `pop`, `bold`, `minimal`, `none` | `bold` |
| `--mask-profanity`| Mask profanity in subtitles (e.g. `f***`) | `False` |
| `--live-duration` | Minutes to capture from live stream | `2.0` |
| `--model` | Whisper model size: `tiny`, `base`, `small`, `medium` | `base` |
| `--lang` | Audio language (`auto` for auto-detection) | `auto` |
| `--i-have-permission` | Required confirmation flag before downloading external URLs | `False` |
| `--out` | Output directory destination | `output/` |

---

## 🧪 Running Tests

Ensure all unit tests pass locally:
```bash
python -m pytest tests/
```

---

## 🔒 Permission & Content Notice

ClippingTool includes a strict permission gate (`--i-have-permission` flag or interactive confirmation checkbox in the UI). Always respect platform terms of service and copyright laws. Only download and process content that you own or have explicit authorization to use.

---

## 📄 License

Distributed under the **MIT License**. Free for personal and commercial use.
