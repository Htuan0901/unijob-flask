"""Tỷ giá ngoại tệ qua API JSON – quy đổi lương VND sang USD/EUR/JPY/KRW cho sinh viên quốc tế.

- Có EXCHANGE_API_KEY -> https://v6.exchangerate-api.com/v6/<API_KEY>/latest/VND (khóa đặt trong .env)
- Không có khóa       -> https://open.er-api.com/v6/latest/VND (gói miễn phí, không cần khóa)
- Mất mạng           -> tỷ giá dự phòng trong cấu hình, ghi rõ nguồn "dự phòng"
"""
from flask import current_app

from .http_client import get_json, NetworkError

FALLBACK = {'USD': None, 'EUR': 0.0000350, 'JPY': 0.00590, 'KRW': 0.0530, 'CNY': 0.000275}
CURRENCIES = ['USD', 'EUR', 'JPY', 'KRW', 'CNY']


def api_url():
    key = current_app.config.get('EXCHANGE_API_KEY')
    if key:
        return f'https://v6.exchangerate-api.com/v6/{key}/latest/VND'
    return 'https://open.er-api.com/v6/latest/VND'


def get_rates():
    """Trả về dict {'rates': {...}, 'source': str, 'updated': str|None, 'live': bool}."""
    try:
        data = get_json(api_url(), cache_ttl=6 * 3600)
        rates = data.get('rates') or data.get('conversion_rates')
        if data.get('result') not in (None, 'success') or not rates:
            raise NetworkError(data.get('error-type') or 'Phản hồi thiếu trường rates')
        return {'rates': {c: rates[c] for c in CURRENCIES if c in rates},
                'source': 'exchangerate-api.com' if 'conversion_rates' in data else 'open.er-api.com',
                'updated': data.get('time_last_update_utc'), 'live': True}
    except NetworkError as e:
        current_app.logger.info('Dùng tỷ giá dự phòng: %s', e)
        rates = dict(FALLBACK, USD=current_app.config['EXCHANGE_FALLBACK_USD'])
        return {'rates': rates, 'source': 'Tỷ giá dự phòng (không kết nối được API)', 'updated': None, 'live': False}


def convert(amount_vnd, currency='USD'):
    if amount_vnd is None:
        return None
    rate = get_rates()['rates'].get(currency)
    return None if rate is None else round(amount_vnd * rate, 2)
