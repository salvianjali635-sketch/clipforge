import os, uuid, subprocess, json, math, shutil
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD = os.path.join(BASE, "uploads")
OUTPUT = os.path.join(BASE, "outputs")
os.makedirs(UPLOAD, exist_ok=True)
os.makedirs(OUTPUT, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

ALLOWED = {"mp4", "mov", "mkv", "webm", "avi"}

def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-3000:])
    return p.stdout

def duration(path):
    out = run(["ffprobe","-v","error","-show_entries","format=duration",
               "-of","default=noprint_wrappers=1:nokey=1",path])
    return float(out.strip())

def make_clip(src, out, start, length, style="viral"):
    # Center crop to 9:16, then scale to 1080x1920.
    vf = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
    if style == "cinematic":
        vf += ",eq=contrast=1.08:saturation=1.08"
    elif style == "news":
        vf += ",eq=contrast=1.04:saturation=1.02"
    elif style == "bright":
        vf += ",eq=brightness=0.04:saturation=1.12"
    cmd = ["ffmpeg","-y","-ss",str(start),"-i",src,"-t",str(length),
           "-vf",vf,"-r","30","-c:v","libx264","-preset","veryfast",
           "-crf","23","-c:a","aac","-b:a","128k","-movflags","+faststart",out]
    run(cmd)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/process", methods=["POST"])
def process():
    if "video" not in request.files:
        return jsonify(error="Video file is required"), 400
    f = request.files["video"]
    if not f.filename:
        return jsonify(error="Choose a video"), 400
    ext = f.filename.rsplit(".",1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED:
        return jsonify(error="Unsupported video format"), 400

    style = request.form.get("style","viral")
    try:
        clip_count = max(1, min(10, int(request.form.get("clips","3"))))
        clip_len = max(5, min(90, int(request.form.get("length","30"))))
    except:
        clip_count, clip_len = 3, 30

    job = uuid.uuid4().hex
    src = os.path.join(UPLOAD, job + "." + ext)
    f.save(src)

    try:
        total = duration(src)
        actual_len = min(clip_len, max(5, total))
        # Free deterministic highlight approximation:
        # distribute clips through the video instead of pretending to have
        # an AI ranking model.
        if total <= actual_len:
            starts = [0]
        else:
            max_start = total - actual_len
            if clip_count == 1:
                starts = [max_start/2]
            else:
                starts = [max_start*i/(clip_count-1) for i in range(clip_count)]

        results=[]
        for i,start in enumerate(starts,1):
            outname=f"{job}_clip_{i}.mp4"
            out=os.path.join(OUTPUT,outname)
            make_clip(src,out,start,actual_len,style)
            results.append({"name":outname,"url":"/outputs/"+outname,
                            "start":round(start,1),"duration":round(actual_len,1)})
        return jsonify(job=job, clips=results, message="Clips created locally without a credit system.")
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        try: os.remove(src)
        except: pass

@app.route("/outputs/<path:name>")
def outputs(name):
    return send_from_directory(OUTPUT, name, as_attachment=False)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
