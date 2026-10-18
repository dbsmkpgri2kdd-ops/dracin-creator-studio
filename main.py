from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import yt_dlp

# Mengatur agar Flask mencari file HTML di direktori yang sama
app = Flask(__name__, template_folder='.', static_folder='.')
CORS(app) 

@app.route('/')
def home():
    # Membaca dan menampilkan index.html
    return render_template('index.html')

@app.route('/api/analisis-video', methods=['POST'])
def analisis_video():
    data = request.json
    url_youtube = data.get('url')

    if not url_youtube:
        return jsonify({"error": "URL YouTube kosong"}), 400

    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url_youtube, download=False)

        return jsonify({
            "status": "sukses",
            "judul": info.get('title', 'Video Dracin Tanpa Judul'),
            "durasi_detik": info.get('duration', 300),
            "thumbnail": info.get('thumbnail', 'https://images.unsplash.com/photo-1578632767115-351597cf2477?w=800&auto=format&fit=crop&q=80'),
            "pesan": "Video berhasil dipindai!"
        })
    except Exception as e:
        # Mode Fallback aman: Langsung masuk ke Studio Manual tanpa error merah
        return jsonify({
            "status": "fallback",
            "judul": "Dracin Spesial Episode Pilihan [Mode Manual Aktif]",
            "durasi_detik": 3600,
            "thumbnail": "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=800&auto=format&fit=crop&q=80",
            "pesan": "Masuk ke Studio Manual."
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)