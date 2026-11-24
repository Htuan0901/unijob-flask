"""Xử lý văn bản tiếng Việt dùng chung cho phân loại, gợi ý và so khớp kỹ năng.

tokenize() giữ đúng quy tắc của data-pipeline/pipeline.py (dùng khi huấn luyện mô hình):
lowercase + NFC, bỏ ký tự đặc biệt, bỏ token 1 ký tự hoặc toàn số, sinh unigram + bigram.
"""
import re
import unicodedata

_NON_WORD = re.compile(r'[^\w\s]', re.UNICODE)
_SPACES = re.compile(r'\s+')


def tokenize(text):
    if not text or not text.strip():
        return []
    t = unicodedata.normalize('NFC', text.lower())
    t = _NON_WORD.sub(' ', t)
    words = [w for w in _SPACES.split(t.strip()) if len(w) > 1 and not w.isdigit()]
    return words + [f'{a}_{b}' for a, b in zip(words, words[1:])]


def fold(text):
    """Bỏ dấu tiếng Việt: 'Kỹ năng Đàm phán' -> 'ky nang dam phan'."""
    if not text:
        return ''
    n = unicodedata.normalize('NFD', text.lower().replace('đ', 'd'))
    n = ''.join(ch for ch in n if unicodedata.category(ch) != 'Mn')
    return _SPACES.sub(' ', n).strip()


def split_skills(joined):
    seen, out = set(), []
    for s in (joined or '').replace(',', ';').split(';'):
        s = s.strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


def join_skills(skills):
    return ';'.join(split_skills(';'.join(skills))) or None


def skill_matches(a, b):
    """Hai kỹ năng khớp nếu (sau khi bỏ dấu) chuỗi này chứa chuỗi kia hoặc trùng >= 50% từ."""
    x, y = fold(a), fold(b)
    if not x or not y:
        return False
    if x == y or (len(x) >= 3 and x in y) or (len(y) >= 3 and y in x):
        return True
    wx, wy = set(x.split()), set(y.split())
    m = min(len(wx), len(wy))
    return m > 0 and len(wx & wy) * 2 >= max(2, m)


def truncate(text, n):
    if text is None:
        return ''
    return text if len(text) <= n else text[:n]
