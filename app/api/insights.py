"""API dữ liệu: danh mục, phân loại ngành (Naive Bayes), gợi ý/tra cứu lương, thống kê, tỷ giá."""
import sqlalchemy as sa
from flask import jsonify, request

from . import api
from .auth import error_response
from .. import db
from ..models import Application, Category, JobPost, User
from ..net import exchange
from ..services import classifier, market


@api.route('/categories')
def categories():
    rows = db.session.execute(sa.select(Category.code, Category.name, sa.func.count(JobPost.id))
                              .outerjoin(JobPost, sa.and_(JobPost.category_id == Category.id,
                                                          JobPost.status == 'OPEN', JobPost.hidden.is_(False)))
                              .group_by(Category.id).order_by(Category.name)).all()
    return jsonify(items=[{'code': c, 'name': n, 'open_jobs': k} for c, n, k in rows])


@api.route('/insights/classify')
def classify():
    title = (request.args.get('title') or '').strip()
    if not title:
        return error_response(400, 'Thiếu tham số title.')
    return jsonify(title=title, predictions=classifier.classify(title, 3))


@api.route('/insights/salary-suggestion')
def salary_suggestion():
    s = market.suggest_salary(request.args.get('category'))
    return jsonify(s) if s else error_response(404, 'Không có dữ liệu lương.')


@api.route('/insights/salary-lookup')
def salary_lookup():
    return jsonify(market.salary_lookup(request.args.get('category'), request.args.get('experience'),
                                        request.args.get('city')))


@api.route('/stats')
def stats():
    """Số liệu tổng hợp cho ứng dụng desktop / dashboard."""
    by_cat = db.session.execute(sa.select(Category.name, sa.func.count(JobPost.id))
                                .join(JobPost, JobPost.category_id == Category.id)
                                .where(JobPost.hidden.is_(False)).group_by(Category.name)).all()
    by_status = db.session.execute(sa.select(Application.status, sa.func.count(Application.id))
                                   .group_by(Application.status)).all()
    return jsonify(
        open_jobs=db.session.scalar(sa.select(sa.func.count(JobPost.id)).where(JobPost.status == 'OPEN')),
        students=db.session.scalar(sa.select(sa.func.count(User.id)).where(User.role == 'STUDENT')),
        employers=db.session.scalar(sa.select(sa.func.count(User.id)).where(User.role == 'EMPLOYER')),
        jobs_by_category=[{'name': n, 'count': c} for n, c in by_cat],
        applications_by_status=[{'status': s, 'count': c} for s, c in by_status],
    )


@api.route('/rates')
def rates():
    return jsonify(exchange.get_rates())
