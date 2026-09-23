import os
import uuid
import subprocess
import shutil
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD = os.path.join(BASE, "uploads")
OUTPUT = os.path.join(BASE, "outputs")

os.makedirs(UPLOAD, exist_ok=True)
os.makedirs(OUTPUT, exist_ok=True)

app = Flask(__name__, template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

ALLOWED = {"mp4", "mov", "mkv", "webm", "avi"}


def run(cmd):
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "Server पर FFmpeg/FFprobe installed नहीं है."
        )

    if p.returncode != 0:
        raise RuntimeError(p.stderr[-4000:])

    return p.stdout


def duration(path):
    out = run([
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ])

    return float(out.strip())


def make_clip(src, out, start, length, style="viral"):

    vf = (
        "crop=ih*9/16:ih:"
        "(iw-ih*9/16)/2:0,"
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
    )

    if style == "cinematic":
        vf += ",eq=contrast=1.08:saturation=1.08"

    elif style == "news":
        vf += ",eq=contrast=1.04:saturation=1.02"

    elif style == "bright":
        vf += ",eq=brightness=0.04:saturation=1.12"

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(start),
        "-i", src,
        "-t", str(length),
        "-vf", vf,
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        out
    ]

    run(cmd)


def download_video(url, destination):

    if not shutil.which("yt-dlp"):
        raise RuntimeError(
            "URL processing अभी available नहीं है क्योंकि server पर yt-dlp installed नहीं है."
        )

    output_template = os.path.join(destination, "%(id)s.%(ext)s")

    run([
        "yt-dlp",
        "--no-playlist",
        "-f", "bv*+ba/b",
        "--merge-output-format", "mp4",
        "-o", output_template,
        url
    ])

    files = []

    for name in os.listdir(destination):
        path = os.path.join(destination, name)

        if os.path.isfile(path):
            files.append(path)

    if not files:
        raise RuntimeError("Video download नहीं हुआ.")

    return max(files, key=os.path.getsize)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/process", methods=["POST"])
def process():

    work = None
    src = None

    try:

        style = request.form.get("style", "viral")

        try:
            clip_count = int(request.form.get("clips", "3"))
            clip_len = int(request.form.get("length", "30"))
        except ValueError:
            clip_count = 3
            clip_len = 30

        clip_count = max(1, min(10, clip_count))
        clip_len = max(5, min(90, clip_len))

        job = uuid.uuid4().hex
        work = os.path.join(UPLOAD, job)

        os.makedirs(work, exist_ok=True)

        # Option 1: uploaded video
        uploaded = request.files.get("video")

        if uploaded and uploaded.filename:

            filename = secure_filename(uploaded.filename)

            if "." not in filename:
                raise RuntimeError("Invalid video filename.")

            ext = filename.rsplit(".", 1)[1].lower()

            if ext not in ALLOWED:
                raise RuntimeError(
                    "Unsupported video format. MP4, MOV, MKV, WEBM या AVI इस्तेमाल करें."
                )

            src = os.path.join(work, "source." + ext)

            uploaded.save(src)

        # Option 2: authorized video URL
        else:

            url = request.form.get("url", "").strip()

            if not url:
                raise RuntimeError(
                    "पहले video upload करें या authorized video URL डालें."
                )

            src = download_video(url, work)

        total = duration(src)

        if total <= 0:
            raise RuntimeError("Video duration पढ़ी नहीं जा सकी.")

        actual_len = min(clip_len, total)

        if total <= actual_len:
            starts = [0]
        else:

            max_start = total - actual_len

            if clip_count == 1:
                starts = [max_start / 2]
            else:
                starts = [
                    max_start * i / (clip_count - 1)
                    for i in range(clip_count)
                ]

        results = []

        for i, start in enumerate(starts, 1):

            outname = f"{job}_clip_{i}.mp4"
            out = os.path.join(OUTPUT, outname)

            make_clip(
                src,
                out,
                start,
                actual_len,
                style
            )

            results.append({
                "name": outname,
                "url": "/outputs/" + outname,
                "start": round(start, 1),
                "duration": round(actual_len, 1)
            })

        return jsonify({
            "success": True,
            "job": job,
            "message": f"{len(results)} vertical clips created.",
            "clips": results
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

    finally:

        if work and os.path.exists(work):
            shutil.rmtree(work, ignore_errors=True)


@app.route("/outputs/<path:name>")
def outputs(name):
    return send_from_directory(
        OUTPUT,
        name,
        as_attachment=False
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
