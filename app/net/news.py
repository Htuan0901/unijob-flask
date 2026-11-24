"""Đọc tin tức nghề nghiệp từ RSS (XML) bằng urllib + xml.etree.ElementTree.

Không tải được RSS (mất mạng, lỗi XML) -> đọc tệp mẫu app/data/news_sample.xml.
"""
import os
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from flask import current_app

from .http_client import get_text, NetworkError
from ..services.data_files import DATA_DIR

_TAG = re.compile(r'<[^>]+>')


def parse_rss(xml_text, limit=12):
    root = ET.fromstring(xml_text)
    items = []
    for item in root.iter('item'):
        title = (item.findtext('title') or '').strip()
        if not title:
            continue
        desc = _TAG.sub(' ', item.findtext('description') or '')
        pub = item.findtext('pubDate')
        try:
            published = parsedate_to_datetime(pub) if pub else None
        except (TypeError, ValueError):
            published = None
        items.append({'title': title, 'link': (item.findtext('link') or '').strip(),
                      'summary': ' '.join(desc.split())[:260], 'published': published})
        if len(items) >= limit:
            break
    channel = root.find('channel')
    return {'channel': channel.findtext('title') if channel is not None else 'RSS', 'items': items}


def get_news(limit=12):
    url = current_app.config['NEWS_RSS_URL']
    try:
        feed = parse_rss(get_text(url, cache_ttl=1800), limit)
        feed.update(source=url, live=True)
        return feed
    except (NetworkError, ET.ParseError) as e:
        current_app.logger.info('Dùng RSS mẫu: %s', e)
        with open(os.path.join(DATA_DIR, 'news_sample.xml'), encoding='utf-8') as f:
            feed = parse_rss(f.read(), limit)
        feed.update(source='Tệp mẫu news_sample.xml (ngoại tuyến)', live=False)
        return feed
