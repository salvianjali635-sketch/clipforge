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

ALLOWED = {
    "mp4",
    "mov",
    "mkv",
    "webm",
    "avi"
}


def run(cmd):

    process = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if process.returncode != 0:
        raise RuntimeError(
            process.stderr[-4000:]
        )

    return process.stdout


def get_duration(path):

    output = run([
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        path
    ])

    return float(output.strip())


def create_short(
    source,
    output,
    start,
    duration
):

    video_filter = (
        "crop=ih*9/16:ih:"
        "(iw-ih*9/16)/2:0,"
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
    )

    run([
        "ffmpeg",
        "-y",

        "-ss",
        str(start),

        "-i",
        source,

        "-t",
        str(duration),

        "-vf",
        video_filter,

        "-r",
        "30",

        "-c:v",
        "libx264",

        "-preset",
        "veryfast",

        "-crf",
        "23",

        "-c:a",
        "aac",

        "-b:a",
        "128k",

        "-movflags",
        "+faststart",

        output
    ])


@app.route("/")
def home():

    return render_template(
        "index.html"
    )


@app.route(
    "/api/process",
    methods=["POST"]
)
def process():

    work = None

    try:

        video = request.files.get(
            "video"
        )

        if not video or not video.filename:

            return jsonify({
                "success": False,
                "error": "Video file required."
            }), 400

        filename = secure_filename(
            video.filename
        )

        if "." not in filename:

            return jsonify({
                "success": False,
                "error": "Invalid video file."
            }), 400

        extension = filename.rsplit(
            ".",
            1
        )[1].lower()

        if extension not in ALLOWED:

            return jsonify({
                "success": False,
                "error": "Unsupported video format."
            }), 400

        job = uuid.uuid4().hex

        work = os.path.join(
            UPLOAD,
            job
        )

        os.makedirs(
            work,
            exist_ok=True
        )

        source = os.path.join(
            work,
            "source." + extension
        )

        video.save(source)

        total = get_duration(
            source
        )

        clip_length = int(
            request.form.get(
                "length",
                30
            )
        )

        clip_count = int(
            request.form.get(
                "clips",
                3
            )
        )

        clip_length = max(
            5,
            min(
                90,
                clip_length
            )
        )

        clip_count = max(
            1,
            min(
                10,
                clip_count
            )
        )

        clip_length = min(
            clip_length,
            total
        )

        if total <= clip_length:

            starts = [0]

        else:

            maximum_start = (
                total - clip_length
            )

            if clip_count == 1:

                starts = [
                    maximum_start / 2
                ]

            else:

                starts = [
                    maximum_start * i /
                    (clip_count - 1)

                    for i in range(
                        clip_count
                    )
                ]

        clips = []

        for number, start in enumerate(
            starts,
            1
        ):

            filename = (
                f"{job}_short_{number}.mp4"
            )

            output = os.path.join(
                OUTPUT,
                filename
            )

            create_short(
                source,
                output,
                start,
                clip_length
            )

            clips.append({

                "name": filename,

                "url":
                    "/outputs/" +
                    filename,

                "start":
                    round(start, 1),

                "duration":
                    round(
                        clip_length,
                        1
                    )
            })

        return jsonify({

            "success": True,

            "message":
                f"{len(clips)} Shorts created.",

            "clips":
                clips

        })

    except Exception as error:

        return jsonify({

            "success": False,

            "error":
                str(error)

        }), 500

    finally:

        if work and os.path.exists(
            work
        ):

            shutil.rmtree(
                work,
                ignore_errors=True
            )


@app.route(
    "/outputs/<path:name>"
)
def output_file(name):

    return send_from_directory(
        OUTPUT,
        name,
        as_attachment=False
    )


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        )
    )
