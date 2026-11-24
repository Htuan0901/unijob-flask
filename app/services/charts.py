"""Biểu đồ thống kê bằng Matplotlib (Chương 5), render ra PNG trong bộ nhớ để trả về qua route.

Dùng backend 'Agg' (không cần màn hình) và API hướng đối tượng Figure/Axes – an toàn đa luồng hơn pyplot.
"""
import io
from datetime import timedelta

import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure  # noqa: E402
import sqlalchemy as sa  # noqa: E402

from .. import db  # noqa: E402
from ..constants import APP_STATUSES  # noqa: E402
from ..models import Application, Category, JobPost, utcnow  # noqa: E402
from . import market  # noqa: E402

# Bảng màu gốc của UniJob: ink, info, shift (vàng), signal (đỏ), xám, ok (xanh lương)
BLUE, TEAL, AMBER, RED, GREY, GREEN = '#1b2a4a', '#2f5fd0', '#ffc83d', '#d93a2f', '#c9d1e0', '#0e8a6a'


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=110, bbox_inches='tight')
    return buf.getvalue()


def _style(ax, title):
    ax.set_title(title, loc='left', fontsize=11, fontweight='bold', color='#1b2a4a')
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors='#3a4866', labelsize=8)


def jobs_by_category():
    rows = db.session.execute(
        sa.select(Category.name, sa.func.count(JobPost.id))
        .join(JobPost, JobPost.category_id == Category.id)
        .where(JobPost.hidden.is_(False))
        .group_by(Category.name).order_by(sa.func.count(JobPost.id))).all()
    fig = Figure(figsize=(6.4, 4.2))
    ax = fig.subplots()
    names = [r[0] for r in rows]
    values = [r[1] for r in rows]
    bars = ax.barh(names, values, color=BLUE)
    ax.bar_label(bars, padding=3, fontsize=7, color='#3a4866')
    _style(ax, 'Số tin tuyển dụng theo ngành')
    return _png(fig)


def applications_by_status():
    rows = dict(db.session.execute(sa.select(Application.status, sa.func.count(Application.id))
                                   .group_by(Application.status)).all())
    labels = [APP_STATUSES[s] for s in APP_STATUSES if rows.get(s)]
    values = [rows[s] for s in APP_STATUSES if rows.get(s)]
    colors = {'PENDING': TEAL, 'ACCEPTED': GREEN, 'REJECTED': RED, 'WITHDRAWN': GREY, 'COMPLETED': BLUE}
    fig = Figure(figsize=(4.6, 4.2))
    ax = fig.subplots()
    if values:
        ax.pie(values, labels=labels, autopct='%1.0f%%', startangle=90, pctdistance=0.78,
               colors=[colors[s] for s in APP_STATUSES if rows.get(s)],
               wedgeprops={'width': 0.42, 'edgecolor': 'white'}, textprops={'fontsize': 8})
    ax.set_title('Hồ sơ ứng tuyển theo trạng thái', loc='left', fontsize=11, fontweight='bold')
    return _png(fig)


def jobs_per_day(days=30):
    start = utcnow() - timedelta(days=days - 1)
    rows = db.session.execute(sa.select(sa.func.date(JobPost.created_at), sa.func.count(JobPost.id))
                              .where(JobPost.created_at >= start.replace(hour=0, minute=0, second=0))
                              .group_by(sa.func.date(JobPost.created_at))).all()
    counts = {str(d): c for d, c in rows}
    xs = [(start + timedelta(days=i)).date() for i in range(days)]
    ys = [counts.get(str(x), 0) for x in xs]
    fig = Figure(figsize=(6.4, 3.0))
    ax = fig.subplots()
    ax.plot(xs, ys, color=TEAL, marker='o', markersize=3, linewidth=1.8)
    ax.fill_between(xs, ys, color=TEAL, alpha=0.12)
    ax.set_ylim(bottom=0)
    fig.autofmt_xdate(rotation=0, ha='center')
    ax.xaxis.set_major_locator(matplotlib.dates.DayLocator(interval=7))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%d/%m'))
    _style(ax, f'Tin mới đăng trong {days} ngày')
    return _png(fig)


def market_salary():
    cats = sorted(market.stats().get('categories', []), key=lambda c: c['salary']['median'])
    fig = Figure(figsize=(6.4, 4.4))
    ax = fig.subplots()
    names = [c['name'].split(' - ')[0] for c in cats]
    med = [c['salary']['median'] for c in cats]
    p25 = [c['salary']['p25'] for c in cats]
    p75 = [c['salary']['p75'] for c in cats]
    ax.hlines(names, p25, p75, color='#c9d1e0', linewidth=5)
    ax.scatter(med, names, color=BLUE, zorder=3, s=22, label='Trung vị')
    ax.set_xlabel('Triệu đồng / tháng (P25 – trung vị – P75)', fontsize=8)
    _style(ax, 'Lương thị trường theo ngành (VietJobs)')
    return _png(fig)


CHARTS = {
    'jobs_by_category': jobs_by_category,
    'applications_by_status': applications_by_status,
    'jobs_per_day': jobs_per_day,
    'market_salary': market_salary,
}
