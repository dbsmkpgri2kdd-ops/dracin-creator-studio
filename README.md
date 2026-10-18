# Dracin Creator Studio

Aplikasi web Flask untuk membaca metadata, mengunduh satu video YouTube yang Anda berhak gunakan, mengedit video lokal, mengganti track dubbing, dan membuat gambar thumbnail melalui Gemini API.

## Instalasi dan penggunaan lokal

Aplikasi hanya membuka server di komputer ini (`127.0.0.1`); tidak menerima koneksi dari jaringan atau host lain. Tidak diperlukan Codespaces.

### Desktop lokal (disarankan untuk cookies browser)

Linux/macOS:

```bash
./run_local.sh
```

Windows PowerShell:

```powershell
.\run_local.ps1
```

Launcher memasang dependency yang diperlukan, membangun CSS, lalu menjalankan Flask hanya di `127.0.0.1`. Windows memakai cookies Edge secara default; Linux/macOS memakai Chrome. Browser lain juga didukung.

Untuk memilih browser lain:

```powershell
$env:YTDLP_COOKIES_FROM_BROWSER = 'chrome'
.\run_local.ps1
```

```bash
YTDLP_COOKIES_FROM_BROWSER=edge ./run_local.sh
```

### Setup manual (opsional)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
npm run build:css
python main.py
```

Buka `http://127.0.0.1:5000`. Hentikan aplikasi dengan `Ctrl+C` pada terminal yang menjalankannya.

## Menggunakan fitur

- Masukkan URL video YouTube untuk membaca judul, durasi, dan thumbnail. Video privat, dibatasi usia/wilayah, atau permintaan yang terkena pembatasan YouTube mungkin tidak dapat dibaca atau diunduh. Aplikasi tidak mencoba menghindari pembatasan.
- Jika video memang memerlukan akun yang Anda berhak akses, ekspor cookies akun sendiri ke format Netscape dan atur `YTDLP_COOKIES_FILE=/path/ke/cookies.txt` sebelum menjalankan aplikasi. File cookies sesi kosong tidak membantu; jangan commit atau bagikan file valid karena isinya dapat memberi akses ke akun Anda.
- Launcher desktop membaca cookies dari browser lokal (Chrome secara default). Untuk memilih browser lain, atur `YTDLP_COOKIES_FROM_BROWSER` sebelum menjalankan launcher, misalnya `firefox`, `edge`, atau `brave`. Cookies hanya dibaca di komputer ini dan tidak dikirim oleh aplikasi ke server lain. Cookies tetap tidak mengatasi IP/jaringan yang diblokir YouTube.
- Jika yt-dlp tidak dapat membaca database profil browser, tutup browser lalu coba lagi. Jangan unggah atau bagikan cookies browser.
- Unduhan mengambil satu trek video dan satu trek audio terpisah dalam ZIP. Masing-masing dibatasi 512 MB dan memerlukan konfirmasi hak/izin. Unduh hanya konten yang memang boleh Anda simpan.
- Editor menerima file video lokal sampai batas unggah 512 MB, memotong rentang waktu sampai dua jam, mengubah rasio 16:9/9:16, mengatur kecepatan, kecerahan, kontras, saturasi, dan volume. Track audio dapat diganti dengan file sendiri atau hasil dubbing AI. Hasil render MP4.
- Panel audio dapat mentranskripsikan audio sampai 20 MB dengan Gemini, lalu menghasilkan suara sintetis dari naskah yang dapat diedit. Fitur ini bukan kloning suara pemeran. Kualitas, kuota, model, dan biaya mengikuti akses Gemini API key Anda.
- Generator metadata AI membuat tiga judul, deskripsi, dan tag berdasarkan judul video/transkrip. Thumbnail dibuat melalui Gemini Image. Untuk semua fitur AI tersebut, masukkan Gemini API key melalui **API Settings**. Key hanya disimpan di memori tab dan dikirim langsung dari browser ke Google.
- Aplikasi tidak mengunggah hasil ke platform. Pintasan platform hanya membuka situs resminya.
- Metadata bukan pemeriksaan hak cipta dan tidak memberi izin untuk menggunakan ulang konten. Pastikan Anda memiliki hak atau izin yang sesuai.

## Pengujian

```bash
python -m unittest discover -s tests
```

Tailwind CSS dibangun lokal melalui `npm run build:css`; aplikasi tidak memakai Tailwind CDN.
