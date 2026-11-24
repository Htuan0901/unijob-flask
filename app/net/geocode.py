"""Chuyển địa chỉ -> tọa độ bằng API Nominatim (OpenStreetMap) trả về JSON.

Dùng khi nhà tuyển dụng đăng/sửa tin để hiện bản đồ ở trang chi tiết.
Chính sách Nominatim: tối đa 1 request/giây và phải có User-Agent – nên kết quả được cache 1 ngày.
"""
from flask import current_app

from .http_client import get_json, NetworkError


def geocode(address, city=None):
    q = ', '.join(p for p in [address, city, 'Việt Nam'] if p)
    try:
        data = get_json(current_app.config['GEOCODER_URL'],
                        params={'q': q, 'format': 'json', 'limit': 1, 'countrycodes': 'vn'},
                        cache_ttl=24 * 3600)
    except NetworkError as e:
        current_app.logger.info('Geocode thất bại: %s', e)
        return None
    if not isinstance(data, list) or not data:
        return None
    try:
        return float(data[0]['lat']), float(data[0]['lon'])
    except (KeyError, ValueError, TypeError):
        return None
