$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Test-Path '.venv/Scripts/python.exe')) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv .venv
    } else {
        & python -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Gagal membuat virtual environment Python.' }
}

& .venv/Scripts/python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Gagal memasang dependency Python.' }

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'Node.js dan npm diperlukan untuk membangun CSS. Pasang Node.js lalu coba lagi.'
}
if (-not (Test-Path 'node_modules/.bin/tailwindcss.cmd')) {
    & npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Gagal memasang dependency CSS.' }
}
& npm run build:css
if ($LASTEXITCODE -ne 0) { throw 'Gagal membangun CSS.' }

if (-not $env:YTDLP_COOKIES_FROM_BROWSER) {
    $env:YTDLP_COOKIES_FROM_BROWSER = 'edge'
}
if (-not $env:FLASK_PORT) { $env:FLASK_PORT = '5000' }

Write-Host "Dracin Studio: http://127.0.0.1:$env:FLASK_PORT"
Write-Host "Cookies yt-dlp: $env:YTDLP_COOKIES_FROM_BROWSER lokal"
& .venv/Scripts/python.exe main.py
