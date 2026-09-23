# ClipForge — Free/No-Credit Clip Studio

This is a starter implementation for a Cliphi-style video clipping website.

## What it does
- Upload MP4/MOV/MKV/WEBM/AVI
- Create multiple clips
- Convert clips to vertical 9:16
- Export 1080x1920 MP4
- Style presets
- No account credits, tokens, or payment gate in the code

## Run on Windows
1. Install Python 3.11+.
2. Install FFmpeg and make sure `ffmpeg` and `ffprobe` are in PATH.
3. Open a terminal in this folder.
4. Run:
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
5. Open http://127.0.0.1:5000

## Run on Linux/Mac
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py

## Next upgrade
To make this a serious production product, add:
- Whisper/faster-whisper captions
- scene detection
- speech/activity based highlight ranking
- face/speaker tracking
- animated captions
- FFmpeg filter templates
- project database
- background job queue
- object storage
- login and admin dashboard
- usage limits based on server capacity instead of credits
- YouTube/API ingestion only where you have rights/permission
