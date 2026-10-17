#!/bin/zsh
# Mac ekranı kapansa bile botun uykuya dalmasını engeller ve 7/24 çalıştırır
cd "$(dirname "$0")"
echo "🚀 Vurgun Radarı 7/24 Uyku-Engelleyici (caffeinate) modunda başlatılıyor..."
exec /usr/bin/caffeinate -i python3 server.py
