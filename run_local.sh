#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

python_bin="${PYTHON:-python3}"
if ! command -v "$python_bin" >/dev/null 2>&1; then
    echo "Python 3 tidak ditemukan. Pasang Python 3 lalu coba lagi." >&2
    exit 1
fi
if [[ ! -x .venv/bin/python ]]; then
    "$python_bin" -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt

if ! command -v npm >/dev/null 2>&1; then
    echo "Node.js dan npm diperlukan untuk membangun CSS. Pasang Node.js lalu coba lagi." >&2
    exit 1
fi
if [[ ! -x node_modules/.bin/tailwindcss ]]; then
    npm ci
fi
npm run build:css

export YTDLP_COOKIES_FROM_BROWSER="${YTDLP_COOKIES_FROM_BROWSER:-chrome}"
export FLASK_PORT="${FLASK_PORT:-5000}"
echo "Dracin Studio: http://127.0.0.1:${FLASK_PORT}"
echo "Cookies yt-dlp: ${YTDLP_COOKIES_FROM_BROWSER} lokal"
exec .venv/bin/python main.py
