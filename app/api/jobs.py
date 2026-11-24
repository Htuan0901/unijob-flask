"""API tin tuyển dụng: tìm kiếm + phân trang, CRUD cho nhà tuyển dụng, gợi ý cho sinh viên."""
from datetime import date

import sqlalchemy as sa
from flask import g, jsonify, request, url_for

from . import api
from .auth import error_response, token_auth_required
from .. import db
from ..constants import CATEGORIES, JOB_TYPES, SALARY_UNITS, CITIES
from ..main.routes import open_jobs_query
from ..models import Application, Category, JobPost
from ..services import recommender
from ..services.workflow import on_job_created
from ..utils.text import join_skills, split_skills


def paginated(query, endpoint, **kwargs):
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 50)
    p = db.paginate(query, page=page, per_page=per_page, error_out=False)
    return {
        'items': [j.to_dict() for j in p.items],
        '_meta': {'page': p.page, 'per_page': per_page, 'total_pages': p.pages, 'total_items': p.total},
        '_links': {
            'self': url_for(endpoint, page=page, per_page=per_page, **kwargs),
            'next': url_for(endpoint, page=page + 1, per_page=per_page, **kwargs) if p.has_next else None,
            'prev': url_for(endpoint, page=page - 1, per_page=per_page, **kwargs) if p.has_prev else None,
        },
    }


@api.route('/jobs', methods=['GET'])
def list_jobs():
    args = {k: request.args.get(k) for k in ('q', 'category', 'city', 'job_type') if request.args.get(k)}
    query = open_jobs_query()
    if 'q' in args:
        like = f"%{args['q']}%"
        query = query.where(sa.or_(JobPost.title.ilike(like), JobPost.skills.ilike(like)))
    if 'category' in args:
        query = query.where(JobPost.category.has(Category.code == args['category']))
    if 'city' in args:
        query = query.where(JobPost.city == args['city'])
    if 'job_type' in args:
        query = query.where(JobPost.job_type == args['job_type'])
    query = query.order_by(JobPost.created_at.desc(), JobPost.id.desc())
    return jsonify(paginated(query, 'api.list_jobs', **args))


@api.route('/jobs/<int:job_id>', methods=['GET'])
def get_job(job_id):
    job = db.session.get(JobPost, job_id)
    if job is None or job.hidden:
        return error_response(404, 'Không tìm thấy tin.')
    return jsonify(job.to_dict(detail=True))


@api.route('/jobs/<int:job_id>/similar', methods=['GET'])
def similar_jobs(job_id):
    job = db.get_or_404(JobPost, job_id)
    pool = db.session.scalars(open_jobs_query().order_by(JobPost.created_at.desc()).limit(200)).all()
    return jsonify(items=[j.to_dict() for j in recommender.similar(job, pool, 5)])


def _validate_job_payload(data, partial=False):
    errors = {}
    required = ('title', 'category', 'city', 'description')
    for f in required:
        if not partial and not data.get(f):
            errors[f] = 'Bắt buộc'
    if 'category' in data and data['category'] not in dict(CATEGORIES):
        errors['category'] = 'Mã ngành không hợp lệ'
    if 'job_type' in data and data['job_type'] not in JOB_TYPES:
        errors['job_type'] = 'Loại hình không hợp lệ'
    if 'salary_unit' in data and data['salary_unit'] not in SALARY_UNITS:
        errors['salary_unit'] = 'Đơn vị lương không hợp lệ'
    if 'city' in data and data['city'] not in CITIES:
        errors['city'] = 'Tỉnh/thành không hợp lệ'
    for f in ('salary_min', 'salary_max', 'slots'):
        if data.get(f) is not None and (not isinstance(data[f], int) or data[f] < 0):
            errors[f] = 'Phải là số nguyên không âm'
    if 'deadline' in data and data['deadline']:
        try:
            date.fromisoformat(data['deadline'])
        except (TypeError, ValueError):
            errors['deadline'] = 'Định dạng YYYY-MM-DD'
    return errors


def _apply_payload(job, data):
    simple = ('title', 'description', 'requirements', 'benefits', 'city', 'address', 'job_type', 'salary_min',
              'salary_max', 'salary_unit', 'working_hours', 'slots', 'urgent')
    for f in simple:
        if f in data:
            setattr(job, f, data[f])
    if 'category' in data:
        with db.session.no_autoflush:
            job.category = db.session.scalar(sa.select(Category).where(Category.code == data['category']))
    if 'skills' in data:
        skills = data['skills'] if isinstance(data['skills'], list) else split_skills(data['skills'] or '')
        job.skills = join_skills(skills)
    if 'deadline' in data:
        job.deadline = date.fromisoformat(data['deadline']) if data['deadline'] else None
    job.update_monthly_salary()


@api.route('/jobs', methods=['POST'])
@token_auth_required('EMPLOYER')
def create_job():
    data = request.get_json(silent=True) or {}
    errors = _validate_job_payload(data)
    if errors:
        return jsonify(error='Unprocessable Entity', fields=errors, status=422), 422
    job = JobPost(employer=g.api_user)
    _apply_payload(job, data)
    db.session.add(job)
    db.session.flush()
    on_job_created(job)
    db.session.commit()
    resp = jsonify(job.to_dict(detail=True))
    resp.status_code = 201
    resp.headers['Location'] = url_for('api.get_job', job_id=job.id)
    return resp


@api.route('/jobs/<int:job_id>', methods=['PUT', 'PATCH'])
@token_auth_required('EMPLOYER')
def update_job(job_id):
    job = db.get_or_404(JobPost, job_id)
    if job.employer_id != g.api_user.id:
        return error_response(403, 'Bạn không phải chủ tin.')
    data = request.get_json(silent=True) or {}
    errors = _validate_job_payload(data, partial=True)
    if errors:
        return jsonify(error='Unprocessable Entity', fields=errors, status=422), 422
    _apply_payload(job, data)
    db.session.commit()
    return jsonify(job.to_dict(detail=True))


@api.route('/jobs/<int:job_id>', methods=['DELETE'])
@token_auth_required('EMPLOYER')
def delete_job(job_id):
    job = db.get_or_404(JobPost, job_id)
    if job.employer_id != g.api_user.id:
        return error_response(403, 'Bạn không phải chủ tin.')
    if job.count_applications(['ACCEPTED', 'COMPLETED']):
        return error_response(409, 'Tin đã có người được nhận, không thể xóa.')
    db.session.delete(job)
    db.session.commit()
    return '', 204


@api.route('/me/recommendations', methods=['GET'])
@token_auth_required('STUDENT')
def my_recommendations():
    pool = db.session.scalars(open_jobs_query().order_by(JobPost.created_at.desc()).limit(300)).all()
    applied = {a.job_id for a in db.session.scalars(g.api_user.applications.select())}
    recs = recommender.recommend(g.api_user.student_profile, pool, exclude_ids=applied, limit=10)
    return jsonify(items=[dict(r.job.to_dict(), score=r.score, reasons=r.reasons) for r in recs])


@api.route('/me/applications', methods=['GET'])
@token_auth_required('STUDENT')
def my_applications():
    apps = db.session.scalars(g.api_user.applications.select().order_by(Application.created_at.desc())).all()
    return jsonify(items=[{'id': a.id, 'job': a.job.to_dict(), 'status': a.status, 'match_score': a.match_score,
                           'created_at': a.created_at.isoformat() + 'Z'} for a in apps])
