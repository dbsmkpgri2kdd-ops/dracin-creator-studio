import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import imageio_ffmpeg
import yt_dlp
from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename


app = Flask(__name__, template_folder=".", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024
logging.basicConfig(level=logging.INFO)

YOUTUBE_HOSTS = {
    "youtu.be",
    "www.youtube.com",
    "youtube.com",
    "m.youtube.com",
    "music.youtube.com",
}
YTDLP_BROWSERS = {"brave", "chrome", "chromium", "edge", "firefox", "opera", "safari", "vivaldi", "whale"}
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
DEFAULT_THUMBNAIL = (
    "https://images.unsplash.com/photo-1578632767115-351597cf2477"
    "?w=800&auto=format&fit=crop&q=80"
)


def ytdlp_options(**overrides):
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 1,
        "extractor_retries": 1,
    }
    node_path = shutil.which("node")
    if node_path:
        options["js_runtimes"] = {"node": {"path": node_path}}
    cookie_path = os.environ.get("YTDLP_COOKIES_FILE")
    cookie_browser = os.environ.get("YTDLP_COOKIES_FROM_BROWSER", "").strip().lower()
    if cookie_path and cookie_browser:
        raise ValueError("Set either YTDLP_COOKIES_FILE or YTDLP_COOKIES_FROM_BROWSER, not both")
    if cookie_path:
        cookie_file = Path(cookie_path).expanduser()
        if not cookie_file.is_file() or cookie_file.stat().st_size == 0:
            raise ValueError("YTDLP_COOKIES_FILE must point to a non-empty Netscape cookies file")
        options["cookiefile"] = str(cookie_file)
    if cookie_browser:
        if cookie_browser not in YTDLP_BROWSERS:
            supported_browsers = ", ".join(sorted(YTDLP_BROWSERS))
            raise ValueError(f"Unsupported YTDLP_COOKIES_FROM_BROWSER; choose one of: {supported_browsers}")
        options["cookiesfrombrowser"] = (cookie_browser, None, None, None)
    options.update(overrides)
    return options


def youtube_access_error(error):
    message = str(error).lower()
    if "not a bot" in message or "confirm you’re not a bot" in message:
        return (
            "YouTube meminta verifikasi akun untuk request dari server aplikasi. "
            "Untuk video yang berhak Anda akses, atur YTDLP_COOKIES_FILE ke file cookies Netscape valid. "
            "Jika tetap ditolak, alamat IP hosting mungkin dibatasi dan aplikasi tidak dapat melewati blokir tersebut."
        )
    if any(term in message for term in ("sign in", "age-restricted", "members-only", "private video")):
        return (
            "YouTube meminta login atau membatasi video ini. Jika Anda berhak mengaksesnya, "
            "ekspor cookies akun sendiri dalam format Netscape dan atur YTDLP_COOKIES_FILE. "
            "Jangan bagikan atau commit file cookies tersebut."
        )
    if "po token" in message or "potoken" in message:
        return (
            "YouTube menolak permintaan player untuk video ini (PO Token diperlukan). "
            "Perbarui yt-dlp dan coba lagi nanti; aplikasi tidak melewati proteksi YouTube."
        )
    if "not available in your country" in message or "geo" in message:
        return "Video tidak tersedia di wilayah server aplikasi. Aplikasi tidak melewati pembatasan wilayah."
    if "403" in message or "429" in message or "http error" in message:
        return "YouTube menolak permintaan sementara (HTTP 403/429). Coba lagi nanti atau perbarui yt-dlp."
    if "unavailable" in message or "not available" in message:
        return "Video tidak tersedia untuk server YouTube saat ini, atau visibilitasnya dibatasi."
    return "YouTube menolak permintaan. Pastikan video publik dan dapat diputar dari server aplikasi."


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
    if request.content_length and request.content_length > 16 * 1024:
        return jsonify({"error": "Permintaan terlalu besar."}), 413
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

    try:
        ydl_options = ytdlp_options(skip_download=True)
        with yt_dlp.YoutubeDL(ydl_options) as ydl:
            info = ydl.extract_info(video_url, download=False)
    except yt_dlp.utils.DownloadError as error:
        app.logger.exception("YouTube did not provide video metadata")
        message = youtube_access_error(error)
        return jsonify({"error": f"Metadata tidak dapat diakses. {message}"}), 422
    except ValueError as error:
        return jsonify({"error": f"Konfigurasi cookies tidak valid: {error}"}), 500
    except Exception:
        app.logger.exception("Unexpected error while analyzing YouTube metadata")
        return jsonify({
            "error": "Terjadi gangguan saat membaca metadata. Silakan coba lagi nanti."
        }), 502

    if not info or info.get("_type") == "playlist":
        return jsonify({"error": "URL tidak mengarah ke satu video yang dapat dibaca."}), 422

    duration = info.get("duration")
    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration < 0
    ):
        duration = None

    return jsonify({
        "status": "success",
        "judul": info.get("title") or "Video tanpa judul",
        "durasi_detik": duration,
        "thumbnail": info.get("thumbnail") or DEFAULT_THUMBNAIL,
    })


@app.route("/api/unduh-video", methods=["POST"])
def unduh_video():
    if request.content_length and request.content_length > 16 * 1024:
        return jsonify({"error": "Permintaan terlalu besar."}), 413
    if not request.is_json:
        return jsonify({"error": "Kirim URL dalam format JSON."}), 415

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Isi permintaan JSON tidak valid."}), 400
    if data.get("rights_confirmed") is not True:
        return jsonify({"error": "Konfirmasikan bahwa Anda memiliki hak untuk mengunduh video ini."}), 400

    video_url = data.get("url")
    if not is_supported_video_url(video_url):
        return jsonify({"error": "Masukkan URL satu video YouTube yang valid."}), 400

    temp_dir = tempfile.mkdtemp(prefix="dracin-download-")
    try:
        tracks = {}
        info = None
        for track_name, format_selector in (
            ("video", "bestvideo[height<=1080][ext=mp4]/bestvideo[height<=720]/bestvideo"),
            ("audio", "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio"),
        ):
            ydl_options = ytdlp_options(
                format=format_selector,
                max_filesize=512 * 1024 * 1024,
                outtmpl=str(Path(temp_dir) / f"{track_name}.%(ext)s"),
            )
            with yt_dlp.YoutubeDL(ydl_options) as ydl:
                track_info = ydl.extract_info(video_url.strip(), download=True)
            if not track_info or track_info.get("_type") == "playlist":
                raise yt_dlp.utils.DownloadError("Expected one video")
            if track_name == "video":
                info = track_info

            downloaded_files = [
                path for path in Path(temp_dir).glob(f"{track_name}.*") if path.is_file()
            ]
            if len(downloaded_files) != 1 or downloaded_files[0].stat().st_size > 512 * 1024 * 1024:
                raise yt_dlp.utils.DownloadError(f"Expected one {track_name} track within size limit")
            tracks[track_name] = downloaded_files[0]

        if tracks["video"].suffix.lower() not in {".mp4", ".webm", ".mkv"}:
            raise yt_dlp.utils.DownloadError("Unsupported video format")
        if tracks["audio"].suffix.lower() not in {".m4a", ".webm", ".mp3", ".opus"}:
            raise yt_dlp.utils.DownloadError("Unsupported audio format")

        title = secure_filename(info.get("title") or "video")[:100] or "video"
        archive_path = Path(temp_dir) / "tracks.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
            for track_name, track_path in tracks.items():
                archive.write(track_path, f"{title}-{track_name}{track_path.suffix.lower()}")

        response = send_file(
            archive_path,
            as_attachment=True,
            download_name=f"{title}-video-audio.zip",
            mimetype="application/zip",
            conditional=True,
        )
        response.call_on_close(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return response
    except yt_dlp.utils.DownloadError as error:
        shutil.rmtree(temp_dir, ignore_errors=True)
        app.logger.exception("YouTube video download failed")
        message = youtube_access_error(error)
        return jsonify({"error": f"Video tidak dapat diunduh. {message}"}), 422
    except ValueError as error:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": f"Konfigurasi cookies tidak valid: {error}"}), 500
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        app.logger.exception("Unexpected error while downloading YouTube video")
        return jsonify({"error": "Terjadi gangguan saat menyiapkan unduhan."}), 502


@app.route("/api/edit-video", methods=["POST"])
def edit_video():
    if request.form.get("rights_confirmed") != "true":
        return jsonify({"error": "Konfirmasikan bahwa Anda memiliki hak untuk mengedit video ini."}), 400

    video_file = request.files.get("video")
    if not video_file or not video_file.filename:
        return jsonify({"error": "Pilih file video terlebih dahulu."}), 400

    try:
        start_seconds = float(request.form.get("start_seconds", "0"))
        end_seconds = float(request.form.get("end_seconds", ""))
        speed = float(request.form.get("speed", "1"))
        brightness = float(request.form.get("brightness", "0"))
        contrast = float(request.form.get("contrast", "1"))
        saturation = float(request.form.get("saturation", "1"))
        volume = float(request.form.get("volume", "1"))
    except (TypeError, ValueError):
        return jsonify({"error": "Waktu dan nilai efek harus berupa angka."}), 400

    if (
        not math.isfinite(start_seconds)
        or not math.isfinite(end_seconds)
        or start_seconds < 0
        or end_seconds <= start_seconds
        or end_seconds > 7200
        or not math.isfinite(speed)
        or not 0.5 <= speed <= 2
        or not math.isfinite(brightness)
        or not -0.5 <= brightness <= 0.5
        or not math.isfinite(contrast)
        or not 0.5 <= contrast <= 1.5
        or not math.isfinite(saturation)
        or not 0 <= saturation <= 2
        or not math.isfinite(volume)
        or not 0 <= volume <= 2
    ):
        return jsonify({"error": "Rentang edit atau nilai efek berada di luar batas."}), 400

    aspect_ratio = request.form.get("aspect_ratio", "16:9")
    if aspect_ratio not in {"16:9", "9:16"}:
        return jsonify({"error": "Pilih rasio 16:9 atau 9:16."}), 400

    dubbing_file = request.files.get("dubbing")
    temp_dir = tempfile.mkdtemp(prefix="dracin-edit-")
    video_path = Path(temp_dir) / "source-video"
    output_path = Path(temp_dir) / "edited-video.mp4"
    video_file.save(video_path)

    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-ss", str(start_seconds), "-t", str(end_seconds - start_seconds),
        "-i", str(video_path),
    ]
    if dubbing_file and dubbing_file.filename:
        dubbing_path = Path(temp_dir) / "dubbing-audio"
        dubbing_file.save(dubbing_path)
        command.extend(["-i", str(dubbing_path)])

    if aspect_ratio == "9:16":
        video_filter = "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280"
    else:
        video_filter = "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720"
    video_filter += (
        f",eq=brightness={brightness}:contrast={contrast}:saturation={saturation}"
        f",setpts=PTS/{speed}"
    )
    audio_filter = f"atempo={speed},volume={volume},apad"

    command.extend([
        "-map", "0:v:0",
        "-map", "1:a:0" if dubbing_file and dubbing_file.filename else "0:a?",
        "-shortest",
        "-vf", video_filter,
        "-af", audio_filter,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-movflags", "+faststart", str(output_path),
    ])

    try:
        subprocess.run(command, check=True, capture_output=True, timeout=180)
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise subprocess.CalledProcessError(1, command)

        response = send_file(
            output_path,
            as_attachment=True,
            download_name="dracin-edited.mp4",
            mimetype="video/mp4",
            conditional=True,
        )
        response.call_on_close(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return response
    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": "Proses edit melebihi batas waktu. Coba video yang lebih pendek."}), 422
    except subprocess.CalledProcessError:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": "Video atau audio tidak dapat diproses. Periksa format file dan rentang waktunya."}), 422
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        app.logger.exception("Unexpected error while editing video")
        return jsonify({"error": "Terjadi gangguan saat mengedit video."}), 502


def run_server():
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("FLASK_PORT", "5000")),
    )


if __name__ == "__main__":
    run_server()
