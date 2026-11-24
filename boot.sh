#!/bin/sh
# Áp dụng migration, nạp dữ liệu mẫu (nếu CSDL trống) rồi chạy Gunicorn.
# PORT do nền tảng host cấp (Render, Railway...); chạy Docker trên máy thì mặc định 5000.
set -e
flask db upgrade
flask seed
exec gunicorn -b "0.0.0.0:${PORT:-5000}" --workers "${WEB_CONCURRENCY:-2}" --threads 4 --timeout 120 \
    --access-logfile - --error-logfile - unijob:app
