#!/bin/sh
# Áp dụng migration, nạp dữ liệu mẫu (nếu CSDL trống) rồi chạy Gunicorn
set -e
flask db upgrade
flask seed
exec gunicorn -b :5000 --workers 3 --access-logfile - --error-logfile - unijob:app
