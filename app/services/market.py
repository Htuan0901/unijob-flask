"""Thống kê thị trường lao động từ bộ dữ liệu VietJobs (market_stats.json).

Lương trong tệp tính theo triệu đồng/tháng.
"""
from ..constants import HOURS_PER_SHIFT, DAYS_PER_MONTH
from .data_files import load_json

EXP_ORDER = ['NONE', 'UNDER_1Y', 'Y1', 'Y2', 'Y3', 'Y4', 'Y5', 'OVER_5Y']
PART_TIME_HOURS_PER_MONTH = HOURS_PER_SHIFT * DAYS_PER_MONTH


def stats():
    return load_json('market_stats.json') or {}


def _round_to(value, step):
    return int(round(value / step) * step)


def suggest_salary(category_code):
    """Gợi ý mức lương khi đăng tin: P25/trung vị/P75 tin bán thời gian cùng ngành, quy đổi ra giờ/ca."""
    s = stats()
    cat = next((c for c in s.get('categories', []) if c['code'] == category_code), None)
    name = cat['name'] if cat else 'Tất cả ngành'
    if cat and cat.get('partTimeSalary') and cat['partTimeSalary'].get('count', 0) >= 15:
        block, basis = cat['partTimeSalary'], 'Tin bán thời gian/thực tập cùng ngành'
    elif s.get('partTimeOverall'):
        block, basis = s['partTimeOverall'], 'Tin bán thời gian/thực tập toàn thị trường (ngành này ít mẫu)'
    else:
        return None
    hourly = _round_to(block['median'] * 1_000_000 / PART_TIME_HOURS_PER_MONTH, 1000)
    return {'category': category_code, 'category_name': name, 'basis': basis, 'sample': block['count'],
            'p25': block['p25'], 'median': block['median'], 'p75': block['p75'],
            'hourly': hourly, 'per_shift': hourly * HOURS_PER_SHIFT,
            'note': f'Quy đổi theo giờ giả định {HOURS_PER_SHIFT} giờ/ngày × {DAYS_PER_MONTH} ngày/tháng. '
                    'Số liệu chỉ mang tính tham khảo.'}


def salary_lookup(category=None, experience=None, city=None):
    """Tra cứu lương ngành × kinh nghiệm × tỉnh; thiếu mẫu thì lùi dần về phạm vi rộng hơn."""
    table = stats().get('salaryLookup', [])
    idx = {(r['category'], r['experience'], r['city']): r for r in table}
    cat, exp, c = category or None, experience or None, city or None
    chain = []
    if c:
        chain.append((exp, c, 'Trong tỉnh/thành đã chọn'))
    chain.append((exp, None, 'Toàn quốc'))
    if exp:
        if c:
            chain.append((None, c, 'Trong tỉnh/thành, mọi mức kinh nghiệm'))
        chain.append((None, None, 'Toàn quốc, mọi mức kinh nghiệm'))
    result, scope = None, None
    for e, cc, label in chain:
        result = idx.get((cat, e, cc))
        if result:
            scope = label
            break
    by_exp = []
    for e in EXP_ORDER:
        r = idx.get((cat, e, c)) if c else None
        local = r is not None
        r = r or idx.get((cat, e, None))
        if r:
            by_exp.append(dict(r, local=local))
    by_city = sorted([r for r in table if r['category'] == cat and r['experience'] == exp and r['city']],
                     key=lambda r: -r['median'])
    return {'result': result, 'scope': scope, 'by_experience': by_exp, 'by_city': by_city}


def lookup_cities():
    return stats().get('lookupCities', [])
