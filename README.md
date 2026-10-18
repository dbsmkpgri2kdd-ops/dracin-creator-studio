# Dracin Creator Studio

Aplikasi web Flask untuk membaca metadata video YouTube publik dan membuat gambar thumbnail melalui Gemini API. Aplikasi tidak mengunduh atau merender video.

## Menjalankan aplikasi

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Buka `http://localhost:5000`. Di Codespaces, teruskan port `5000` lalu buka URL aplikasi yang disediakan Codespaces.

## Menggunakan fitur

- Masukkan URL video YouTube publik untuk membaca judul, durasi, dan thumbnail. Video privat, dibatasi usia/wilayah, atau permintaan yang terkena pembatasan YouTube mungkin tidak dapat dibaca. Aplikasi menampilkan kegagalan tersebut dan tidak mencoba menghindari pembatasan.
- Untuk membuat thumbnail, masukkan Gemini API key melalui **API Settings**. Key hanya disimpan di memori tab selama halaman terbuka dan dikirim dari browser langsung ke Google. Jangan gunakan key pada perangkat atau browser yang tidak Anda percaya.
- Fitur dubbing, pengolahan/render video, dan unggah otomatis belum tersedia. Pintasan platform hanya membuka situs resminya.
- Metadata bukan pemeriksaan hak cipta dan tidak memberi izin untuk menggunakan ulang konten. Pastikan Anda memiliki hak atau izin yang sesuai.

## Pengujian

```bash
python -m unittest discover -s tests
```
