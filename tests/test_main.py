import unittest
import os
import tempfile
from io import BytesIO
from zipfile import ZipFile
from unittest.mock import patch

import main


class VideoAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.client = main.app.test_client()

    def test_homepage_is_served(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Metadata & Materi Kreatif", response.data)

    @patch("main.app.run")
    def test_server_always_binds_to_loopback(self, run):
        with patch.dict(os.environ, {}, clear=True):
            main.run_server()
        run.assert_called_once_with(host="127.0.0.1", port=5000)

        run.reset_mock()
        with patch.dict(os.environ, {"FLASK_HOST": "0.0.0.0", "FLASK_PORT": "8000"}):
            main.run_server()
        run.assert_called_once_with(host="127.0.0.1", port=8000)

    def test_static_css_is_served_without_exposing_root_files(self):
        css_response = self.client.get("/static/app.css")

        self.assertEqual(css_response.status_code, 200)
        self.assertTrue(css_response.mimetype.startswith("text/css"))
        self.assertEqual(self.client.get("/static/cookies.txt").status_code, 404)

    def test_cookie_file_is_opt_in_and_must_not_be_empty(self):
        with tempfile.NamedTemporaryFile(mode="w") as cookie_file:
            cookie_file.write("# Netscape HTTP Cookie File\n")
            cookie_file.flush()
            with patch.dict(os.environ, {"YTDLP_COOKIES_FILE": cookie_file.name}):
                self.assertEqual(main.ytdlp_options()["cookiefile"], cookie_file.name)

        with tempfile.NamedTemporaryFile() as empty_cookie_file:
            with patch.dict(os.environ, {"YTDLP_COOKIES_FILE": empty_cookie_file.name}):
                with self.assertRaises(ValueError):
                    main.ytdlp_options()

    def test_browser_cookies_support_chrome_and_edge(self):
        for browser in ("chrome", "edge"):
            with self.subTest(browser=browser):
                with patch.dict(os.environ, {"YTDLP_COOKIES_FROM_BROWSER": browser}):
                    options = main.ytdlp_options()

                self.assertEqual(options["cookiesfrombrowser"], (browser, None, None, None))

    def test_browser_and_cookie_file_settings_cannot_conflict(self):
        with patch.dict(os.environ, {
            "YTDLP_COOKIES_FILE": "/tmp/cookies.txt",
            "YTDLP_COOKIES_FROM_BROWSER": "chrome",
        }):
            with self.assertRaises(ValueError):
                main.ytdlp_options()

    @patch("main.shutil.which", return_value="/usr/bin/node")
    def test_enables_node_for_youtube_javascript_extraction(self, which):
        options = main.ytdlp_options()

        self.assertEqual(options["js_runtimes"], {"node": {"path": "/usr/bin/node"}})
        which.assert_called_once_with("node")

    def test_accepts_supported_youtube_video_urls(self):
        urls = (
            "https://www.youtube.com/watch?v=abcdefghijk",
            "https://youtu.be/abcdefghijk",
            "https://m.youtube.com/shorts/abcdefghijk",
            "https://www.youtube.com/embed/abcdefghijk",
            "https://www.youtube.com/live/abcdefghijk",
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertTrue(main.is_supported_video_url(url))

    def test_rejects_non_youtube_and_malformed_urls(self):
        urls = (
            "https://example.com/watch?v=abcdefghijk",
            "https://youtube.com.example.com/watch?v=abcdefghijk",
            "https://youtube.com:8080/watch?v=abcdefghijk",
            "https://youtube.com/watch?v=short",
            "https://youtube.com.evil/watch?v=abcdefghijk",
            "file:///etc/passwd",
        )

        for url in urls:
            with self.subTest(url=url):
                response = self.client.post("/api/analisis-video", json={"url": url})
                self.assertEqual(response.status_code, 400)

    @patch("main.yt_dlp.YoutubeDL")
    def test_returns_video_metadata(self, youtube_dl):
        extractor = youtube_dl.return_value.__enter__.return_value
        extractor.extract_info.return_value = {
            "title": "Video uji",
            "duration": 125,
            "thumbnail": "https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg",
        }

        response = self.client.post(
            "/api/analisis-video",
            json={"url": "https://www.youtube.com/watch?v=abcdefghijk"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["judul"], "Video uji")
        self.assertEqual(response.json["durasi_detik"], 125)
        self.assertEqual(response.json["status"], "success")
        self.assertTrue(youtube_dl.call_args.args[0]["noplaylist"])

    @patch("main.yt_dlp.YoutubeDL")
    def test_invalid_duration_values_are_reported_as_unavailable(self, youtube_dl):
        extractor = youtube_dl.return_value.__enter__.return_value
        for duration in (True, float("nan"), -1, "unknown"):
            with self.subTest(duration=duration):
                extractor.extract_info.return_value = {
                    "title": "Video uji",
                    "duration": duration,
                }
                response = self.client.post(
                    "/api/analisis-video",
                    json={"url": "https://youtu.be/abcdefghijk"},
                )

                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.json["durasi_detik"])

    @patch("main.yt_dlp.YoutubeDL")
    def test_does_not_report_success_when_youtube_rejects_metadata(self, youtube_dl):
        extractor = youtube_dl.return_value.__enter__.return_value
        extractor.extract_info.side_effect = main.yt_dlp.utils.DownloadError("unavailable")

        with self.assertLogs("main", level="ERROR"):
            response = self.client.post(
                "/api/analisis-video",
                json={"url": "https://www.youtube.com/watch?v=abcdefghijk"},
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("error", response.json)
        self.assertNotIn("judul", response.json)

    @patch("main.yt_dlp.YoutubeDL")
    def test_explains_temporary_youtube_rate_limit(self, youtube_dl):
        extractor = youtube_dl.return_value.__enter__.return_value
        extractor.extract_info.side_effect = main.yt_dlp.utils.DownloadError("HTTP Error 429: Too Many Requests")

        with self.assertLogs("main", level="ERROR"):
            response = self.client.post(
                "/api/analisis-video",
                json={"url": "https://youtu.be/abcdefghijk"},
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("403/429", response.json["error"])

    @patch("main.yt_dlp.YoutubeDL")
    def test_explains_youtube_bot_verification_requirement(self, youtube_dl):
        extractor = youtube_dl.return_value.__enter__.return_value
        extractor.extract_info.side_effect = main.yt_dlp.utils.DownloadError(
            "Sign in to confirm you’re not a bot"
        )

        with self.assertLogs("main", level="ERROR"):
            response = self.client.post(
                "/api/analisis-video",
                json={"url": "https://youtu.be/abcdefghijk"},
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("verifikasi akun", response.json["error"])
        self.assertIn("alamat IP hosting", response.json["error"])

    def test_requires_json_request(self):
        response = self.client.post(
            "/api/analisis-video",
            data="url=https://www.youtube.com/watch?v=abcdefghijk",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(response.status_code, 415)

    def test_rejects_malformed_json(self):
        response = self.client.post(
            "/api/analisis-video",
            data="{",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_limits_request_body_size(self):
        response = self.client.post(
            "/api/analisis-video",
            data=b"x" * (16 * 1024 + 1),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 413)
        self.assertIn("error", response.json)

    @patch("main.yt_dlp.YoutubeDL")
    def test_download_requires_rights_confirmation(self, youtube_dl):
        response = self.client.post(
            "/api/unduh-video",
            json={"url": "https://youtu.be/abcdefghijk"},
        )

        self.assertEqual(response.status_code, 400)
        youtube_dl.assert_not_called()

    @patch("main.yt_dlp.YoutubeDL")
    def test_download_returns_one_video_as_attachment(self, youtube_dl):
        extractor = youtube_dl.return_value.__enter__.return_value

        def create_track(url, download):
            options = youtube_dl.call_args.args[0]
            extension = "mp4" if options["format"].startswith("bestvideo") else "m4a"
            output_path = options["outtmpl"].replace("%(ext)s", extension)
            with open(output_path, "wb") as track_file:
                track_file.write(f"{extension}-data".encode())
            return {"title": "Video Uji", "id": "abcdefghijk"}

        extractor.extract_info.side_effect = create_track
        response = self.client.post(
            "/api/unduh-video",
            json={
                "url": "https://youtu.be/abcdefghijk",
                "rights_confirmed": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")
        self.assertIn("attachment", response.headers["Content-Disposition"])
        with ZipFile(BytesIO(response.data)) as archive:
            self.assertEqual(archive.namelist(), ["Video_Uji-video.mp4", "Video_Uji-audio.m4a"])
            self.assertEqual(archive.read("Video_Uji-video.mp4"), b"mp4-data")
            self.assertEqual(archive.read("Video_Uji-audio.m4a"), b"m4a-data")
        self.assertEqual(youtube_dl.call_count, 2)
        for call in youtube_dl.call_args_list:
            self.assertTrue(call.args[0]["noplaylist"])
            self.assertEqual(call.args[0]["max_filesize"], 512 * 1024 * 1024)
        response.close()

    @patch("main.subprocess.run")
    def test_edit_video_trims_and_replaces_audio(self, run_ffmpeg):
        def write_output(command, **kwargs):
            with open(command[-1], "wb") as output_file:
                output_file.write(b"edited-video")

        run_ffmpeg.side_effect = write_output
        response = self.client.post(
            "/api/edit-video",
            data={
                "rights_confirmed": "true",
                "start_seconds": "2",
                "end_seconds": "12",
                "aspect_ratio": "9:16",
                "speed": "1.25",
                "brightness": "0.1",
                "contrast": "1.1",
                "saturation": "1.2",
                "volume": "0.8",
                "video": (BytesIO(b"source-video"), "source.mp4", "video/mp4"),
                "dubbing": (BytesIO(b"voice-track"), "voice.mp3", "audio/mpeg"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"edited-video")
        self.assertIn("dracin-edited.mp4", response.headers["Content-Disposition"])
        command = run_ffmpeg.call_args.args[0]
        self.assertIn("1:a:0", command)
        video_filter = command[command.index("-vf") + 1]
        self.assertIn("scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280", video_filter)
        self.assertIn("eq=brightness=0.1:contrast=1.1:saturation=1.2", video_filter)
        self.assertIn("setpts=PTS/1.25", video_filter)
        self.assertEqual(command[command.index("-af") + 1], "atempo=1.25,volume=0.8,apad")
        self.assertEqual(run_ffmpeg.call_args.kwargs["timeout"], 180)
        response.close()

    @patch("main.subprocess.run")
    def test_edit_video_rejects_invalid_time_range(self, run_ffmpeg):
        response = self.client.post(
            "/api/edit-video",
            data={
                "rights_confirmed": "true",
                "start_seconds": "10",
                "end_seconds": "5",
                "video": (BytesIO(b"source-video"), "source.mp4", "video/mp4"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        run_ffmpeg.assert_not_called()


if __name__ == "__main__":
    unittest.main()
