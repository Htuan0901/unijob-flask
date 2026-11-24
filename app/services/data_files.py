"""Đọc các tệp dữ liệu JSON do data-pipeline xuất ra (đọc một lần, giữ trong bộ nhớ)."""
import json
import os
from functools import lru_cache

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')


@lru_cache(maxsize=None)
def load_json(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)
