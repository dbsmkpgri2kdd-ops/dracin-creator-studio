import logging
import re
from urllib.parse import parse_qs, urlsplit

import yt_dlp
from flask import Flask, jsonify, render_template, request


app = Flask(__name__, template_folder=".", static_folder=".")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
logging.basicConfig(level=logging.INFO)

YOUTUBE_HOSTS = {
    "youtu.be",
    "www.youtube.com",
    "youtube.com",
    "m.youtube.com",
    "music.youtube.com",
}
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
DEFAULT_THUMBNAIL = (
    "https://images.unsplash.com/photo-1578632767115-351597cf2477"
    "?w=800&auto=format&fit=crop&q=80"
)


def is_supported_video_url(value: object) -> bool:
    if not isinstance(value, str):
        return False

    try:
        parsed = urlsplit(value.strip())
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return False

    if (
        parsed.scheme not in {"http", "https"}
        or hostname not in YOUTUBE_HOSTS
        or port not in {None, 80, 443}
        or parsed.username is not None
        or parsed.password is not None
    ):
        return False

    if hostname == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0]
    else:
        path_parts = parsed.path.strip("/").split("/")
        video_id = path_parts[1] if len(path_parts) == 2 and path_parts[0] in {
            "embed",
            "live",
            "shorts",
        } else ""

    return bool(VIDEO_ID_PATTERN.fullmatch(video_id))


@app.route("/")
def home():
    return render_template("index.html")


@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        "error": "Permintaan terlalu besar.",
        "detail": error.description,
    }), 413


@app.route("/api/analisis-video", methods=["POST"])
def analisis_video():
    if not request.is_json:
        return jsonify({"error": "Kirim URL dalam format JSON."}), 415

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Isi permintaan JSON tidak valid."}), 400

    video_url = data.get("url")
    if not is_supported_video_url(video_url):
        return jsonify({
            "error": "Masukkan URL video YouTube yang valid (watch, youtu.be, shorts, embed, atau live)."
        }), 400
    video_url = video_url.strip()

    ydl_options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 15,
        "retries": 1,
        "extractor_retries": 1,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_options) as ydl:
            info = ydl.extract_info(video_url, download=False)
    except yt_dlp.utils.DownloadError:
        app.logger.exception("YouTube did not provide video metadata")
        return jsonify({
            "error": (
                "Metadata tidak dapat diakses. Video mungkin privat, dibatasi "
                "wilayah/usia, atau sementara tidak tersedia. Buka video di "
                "YouTube untuk memeriksa akses dan izin Anda."
            )
        }), 422
    except Exception:
        app.logger.exception("Unexpected error while analyzing YouTube metadata")
        return jsonify({
            "error": "Terjadi gangguan saat membaca metadata. Silakan coba lagi nanti."
        }), 502

    if not info or info.get("_type") == "playlist":
        return jsonify({"error": "URL tidak mengarah ke satu video yang dapat dibaca."}), 422

    duration = info.get("duration")
    if not isinstance(duration, (int, float)) or duration < 0:
        duration = None

    return jsonify({
        "status": "success",
        "judul": info.get("title") or "Video tanpa judul",
        "durasi_detik": duration,
        "thumbnail": info.get("thumbnail") or DEFAULT_THUMBNAIL,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
