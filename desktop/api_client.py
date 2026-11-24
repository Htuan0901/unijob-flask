"""Client REST API của UniJob dùng urllib (không phụ thuộc GUI để dễ kiểm thử).

Ví dụ:
    c = UniJobClient('http://127.0.0.1:5000')
    c.login('ntd@unijob.vn', 'Tuyendung@123')
    page = c.jobs(q='pha chế', page=1)
"""
import base64
import json
import urllib.error
import urllib.parse
import urllib.request


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(f'{status}: {message}')
        self.status, self.message = status, message


class UniJobClient:
    def __init__(self, base_url='http://127.0.0.1:5000', timeout=10):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.token = None
        self.user = None

    def _request(self, method, path, params=None, payload=None, headers=None):
        url = self.base_url + path
        if params:
            url += '?' + urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, '')})
        data = json.dumps(payload).encode('utf-8') if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header('Accept', 'application/json')
        req.add_header('User-Agent', 'UniJobDesktop/1.0')
        if data is not None:
            req.add_header('Content-Type', 'application/json')
        if self.token:
            req.add_header('Authorization', f'Bearer {self.token}')
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as e:
            try:
                info = json.loads(e.read())
                msg = info.get('message') or json.dumps(info.get('fields', info), ensure_ascii=False)
            except ValueError:
                msg = e.reason
            raise ApiError(e.code, msg) from e
        except urllib.error.URLError as e:
            raise ApiError(0, f'Không kết nối được máy chủ: {e.reason}') from e

    # ---- xác thực ----
    def login(self, email, password):
        basic = base64.b64encode(f'{email}:{password}'.encode()).decode()
        self.token = None
        data = self._request('POST', '/api/tokens', headers={'Authorization': f'Basic {basic}'})
        self.token, self.user = data['token'], data['user']
        return self.user

    def logout(self):
        if self.token:
            try:
                self._request('DELETE', '/api/tokens')
            finally:
                self.token, self.user = None, None

    # ---- dữ liệu ----
    def jobs(self, q=None, category=None, city=None, page=1, per_page=15):
        return self._request('GET', '/api/jobs', {'q': q, 'category': category, 'city': city,
                                                  'page': page, 'per_page': per_page})

    def job(self, job_id):
        return self._request('GET', f'/api/jobs/{job_id}')

    def categories(self):
        return self._request('GET', '/api/categories')['items']

    def stats(self):
        return self._request('GET', '/api/stats')

    def classify(self, title):
        return self._request('GET', '/api/insights/classify', {'title': title})['predictions']

    def salary_suggestion(self, category):
        return self._request('GET', '/api/insights/salary-suggestion', {'category': category})

    def create_job(self, **fields):
        return self._request('POST', '/api/jobs', payload=fields)

    def recommendations(self):
        return self._request('GET', '/api/me/recommendations')['items']
