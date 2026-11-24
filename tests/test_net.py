"""Kiểm thử phần lập trình mạng với một HTTP server giả lập chạy cục bộ (threading + http.server)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.net import exchange, geocode, http_client, news
from app.net.http_client import NetworkError

RSS = '''<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Báo Test</title>
<item><title>Tin 1</title><link>http://x/1</link><description>&lt;p&gt;Mô tả &lt;b&gt;một&lt;/b&gt;&lt;/p&gt;</description>
<pubDate>Mon, 16 Nov 2026 08:00:00 +0700</pubDate></item><item><title>Tin 2</title><link>http://x/2</link></item></channel></rss>'''


class Handler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype='application/json'):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        Handler.calls.append((self.path, self.headers.get('User-Agent'), self.headers.get('Authorization')))
        if self.path.startswith('/rates'):
            self._send(200, json.dumps({'result': 'success', 'rates': {'USD': 0.00004, 'EUR': 0.000036, 'XYZ': 1},
                                        'time_last_update_utc': 'Wed, 18 Nov 2026'}))
        elif self.path.startswith('/geo'):
            self._send(200, json.dumps([{'lat': '10.77', 'lon': '106.70'}]))
        elif self.path.startswith('/rss'):
            self._send(200, RSS, 'application/rss+xml')
        elif self.path.startswith('/bad'):
            self._send(200, '<html>not json')
        else:
            self._send(500, '{}')

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length))
        Handler.calls.append((self.path, body, self.headers.get('Authorization')))
        if self.path == '/v1/chat/completions':
            self._send(200, json.dumps({'choices': [{'message': {'content': 'Trả lời từ LLM [1]'}}]}))
        elif self.path == '/api/chat':
            self._send(200, json.dumps({'message': {'content': 'Ollama trả lời [1]'}}))
        else:
            self._send(404, '{}')


@pytest.fixture
def server(app):
    srv = HTTPServer(('127.0.0.1', 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    app.config['NETWORK_ENABLED'] = True
    http_client.clear_cache()
    Handler.calls.clear()
    yield f'http://127.0.0.1:{srv.server_port}'
    srv.shutdown()
    http_client.clear_cache()


def test_get_json_sends_user_agent_and_caches(server):
    data = http_client.get_json(server + '/rates', params={'a': 1}, cache_ttl=60)
    http_client.get_json(server + '/rates', params={'a': 1}, cache_ttl=60)
    assert data['rates']['USD'] == 0.00004
    assert len(Handler.calls) == 1 and 'UniJob' in Handler.calls[0][1] and '?a=1' in Handler.calls[0][0]


def test_errors_are_wrapped(server):
    with pytest.raises(NetworkError):
        http_client.get_json(server + '/bad')
    with pytest.raises(NetworkError):
        http_client.get_json(server + '/500')
    with pytest.raises(NetworkError):
        http_client.get_json('http://127.0.0.1:1/khong-co', timeout=1)


def test_network_disabled(app):
    app.config['NETWORK_ENABLED'] = False
    with pytest.raises(NetworkError):
        http_client.get_json('http://example.com')


def test_exchange_rates_live_and_fallback(app, server, monkeypatch):
    monkeypatch.setattr(exchange, 'api_url', lambda: server + '/rates')
    r = exchange.get_rates()
    assert r['live'] and r['rates'] == {'USD': 0.00004, 'EUR': 0.000036}
    assert exchange.convert(5_000_000) == 200.0
    monkeypatch.setattr(exchange, 'api_url', lambda: server + '/500')
    http_client.clear_cache()
    assert exchange.get_rates()['live'] is False


def test_exchange_url_uses_api_key(app):
    app.config['EXCHANGE_API_KEY'] = 'KHOA123'
    assert exchange.api_url() == 'https://v6.exchangerate-api.com/v6/KHOA123/latest/VND'


def test_geocode(app, server):
    app.config['GEOCODER_URL'] = server + '/geo'
    assert geocode.geocode('12 Phan Xích Long', 'TP. Hồ Chí Minh') == (10.77, 106.70)
    assert 'format=json' in Handler.calls[0][0]
    app.config['GEOCODER_URL'] = server + '/500'
    http_client.clear_cache()
    assert geocode.geocode('x') is None


def test_rss_parse_and_fallback(app, server):
    app.config['NEWS_RSS_URL'] = server + '/rss'
    feed = news.get_news()
    assert feed['live'] and feed['channel'] == 'Báo Test'
    assert feed['items'][0]['summary'] == 'Mô tả một' and feed['items'][0]['published'].day == 16
    app.config['NEWS_RSS_URL'] = server + '/500'
    http_client.clear_cache()
    assert news.get_news()['live'] is False
