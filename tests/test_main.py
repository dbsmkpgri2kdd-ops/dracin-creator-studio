import unittest
from unittest.mock import patch

import main


class VideoAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.client = main.app.test_client()

    def test_homepage_is_served(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Metadata & Materi Kreatif", response.data)

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


if __name__ == "__main__":
    unittest.main()
