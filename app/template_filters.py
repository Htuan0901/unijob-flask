"""Bộ lọc Jinja2 tự định nghĩa."""
from datetime import datetime

from .models import utcnow


def money(value):
    if value is None:
        return '—'
    return f'{value:,.0f}'.replace(',', '.')


def timeago(dt):
    if not dt:
        return ''
    s = (utcnow() - dt).total_seconds()
    if s < 60:
        return 'vừa xong'
    for unit, sec in (('năm', 31536000), ('tháng', 2592000), ('ngày', 86400), ('giờ', 3600), ('phút', 60)):
        if s >= sec:
            return f'{int(s // sec)} {unit} trước'
    return ''


def dmy(dt):
    return dt.strftime('%d/%m/%Y') if dt else ''


def stars(value):
    v = int(round(value or 0))
    return '★' * v + '☆' * (5 - v)


def register(app):
    app.jinja_env.filters.update(money=money, timeago=timeago, dmy=dmy, stars=stars)
    app.jinja_env.globals['now'] = datetime.now
