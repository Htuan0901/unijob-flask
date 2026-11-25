"""Lớp gọi HTTP dùng urllib (thư viện chuẩn) – phần Lập trình mạng (CLO3).

- get_json / get_text / post_json: tự ghép query string, đặt User-Agent, timeout
- Bộ nhớ đệm có thời hạn (TTL) để không gọi lại API bên ngoài ở mỗi request
- Mọi lỗi mạng/HTTP/JSON được gói thành NetworkError để nơi gọi chọn phương án dự phòng
"""
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from flask import current_app, has_app_context


class NetworkError(Exception):
    pass


_cache = {}
_lock = threading.Lock()


def _cfg(key, default=None):
    if has_app_context():
        return current_app.config.get(key, default)
    return default


def clear_cache():
    with _lock:
        _cache.clear()


def _cache_get(key):
    with _lock:
        item = _cache.get(key)
        if item and item[0] > time.time():
            return item[1]
    return None


def _cache_set(key, value, ttl):
    if ttl:
        with _lock:
            _cache[key] = (time.time() + ttl, value)


def build_url(url, params=None):
    if not params:
        return url
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return url + ('&' if '?' in url else '?') + query


def fetch(url, params=None, headers=None, data=None, method=None, timeout=None, cache_ttl=0):
    """Trả về (status, bytes). Ném NetworkError khi mạng bị tắt, lỗi kết nối hoặc mã HTTP >= 400."""
    if not _cfg('NETWORK_ENABLED', True):
        raise NetworkError('Truy cập mạng đang tắt (NETWORK_ENABLED=0)')
    full = build_url(url, params)
    key = (method or ('POST' if data else 'GET'), full, data)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    req = urllib.request.Request(full, data=data, method=method)
    req.add_header('User-Agent', _cfg('HTTP_USER_AGENT', 'UniJob/1.0'))
    req.add_header('Accept', 'application/json, application/xml;q=0.9, */*;q=0.5')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout or _cfg('HTTP_TIMEOUT', 6)) as resp:
            result = (resp.status, resp.read())
    except urllib.error.HTTPError as e:
        try:
            detail = e.read(300).decode('utf-8', errors='replace').strip()
        except Exception:
            detail = ''
        err = NetworkError(f'HTTP {e.code} khi gọi {url}' + (f': {detail}' if detail else ''))
        err.status = e.code
        raise err from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise NetworkError(f'Không kết nối được {url}: {e}') from e
    _cache_set(key, result, cache_ttl)
    return result


def get_json(url, params=None, headers=None, timeout=None, cache_ttl=0):
    _, body = fetch(url, params, headers, timeout=timeout, cache_ttl=cache_ttl)
    try:
        return json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise NetworkError(f'Phản hồi không phải JSON hợp lệ: {e}') from e


def get_text(url, params=None, headers=None, timeout=None, cache_ttl=0):
    _, body = fetch(url, params, headers, timeout=timeout, cache_ttl=cache_ttl)
    return body.decode('utf-8', errors='replace')


def post_json(url, payload, headers=None, timeout=None):
    h = {'Content-Type': 'application/json'}
    h.update(headers or {})
    _, body = fetch(url, headers=h, data=json.dumps(payload).encode('utf-8'), method='POST', timeout=timeout)
    try:
        return json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise NetworkError(f'Phản hồi không phải JSON hợp lệ: {e}') from e
