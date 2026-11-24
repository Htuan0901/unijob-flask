"""Quản trị: thống kê + biểu đồ Matplotlib, quản lý người dùng/tin, xuất CSV, hộp thư đi (email demo)."""
import csv
import email
import email.policy
import io
import os

import sqlalchemy as sa
from flask import Response, abort, current_app, flash, redirect, render_template, request, url_for

from . import admin
from .. import db
from ..decorators import admin_required
from ..models import Application, EmployerProfile, JobPost, Review, User
from ..services import charts


@admin.route('/')
@admin_required
def dashboard():
    count = lambda q: db.session.scalar(q) or 0
    kpi = {
        'students': count(sa.select(sa.func.count(User.id)).where(User.role == 'STUDENT')),
        'employers': count(sa.select(sa.func.count(User.id)).where(User.role == 'EMPLOYER')),
        'jobs': count(sa.select(sa.func.count(JobPost.id))),
        'open_jobs': count(sa.select(sa.func.count(JobPost.id)).where(JobPost.status == 'OPEN')),
        'applications': count(sa.select(sa.func.count(Application.id))),
        'completed': count(sa.select(sa.func.count(Application.id)).where(Application.status == 'COMPLETED')),
        'reviews': count(sa.select(sa.func.count(Review.id))),
        'avg_rating': db.session.scalar(sa.select(sa.func.avg(Review.rating))) or 0,
    }
    return render_template('admin/dashboard.html', kpi=kpi, charts=list(charts.CHARTS))


@admin.route('/charts/<name>.png')
@admin_required
def chart(name):
    fn = charts.CHARTS.get(name)
    if fn is None:
        abort(404)
    return Response(fn(), mimetype='image/png', headers={'Cache-Control': 'no-store'})


@admin.route('/users')
@admin_required
def users():
    q, role = request.args.get('q', '').strip(), request.args.get('role', '')
    page = request.args.get('page', 1, type=int)
    query = sa.select(User).order_by(User.created_at.desc())
    if q:
        query = query.where(sa.or_(User.email.ilike(f'%{q}%'), User.full_name.ilike(f'%{q}%')))
    if role:
        query = query.where(User.role == role)
    pagination = db.paginate(query, page=page, per_page=current_app.config['ADMIN_PER_PAGE'], error_out=False)
    return render_template('admin/users.html', pagination=pagination, users=pagination.items, q=q, role=role)


@admin.route('/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.is_admin:
        flash('Không thể khóa tài khoản quản trị.', 'warning')
    else:
        user.enabled = not user.enabled
        db.session.commit()
        flash(f'Đã {"mở khóa" if user.enabled else "khóa"} {user.email}.', 'success')
    return redirect(request.referrer or url_for('admin.users'))


@admin.route('/companies/<int:company_id>/verify', methods=['POST'])
@admin_required
def verify_company(company_id):
    c = db.get_or_404(EmployerProfile, company_id)
    c.verified = not c.verified
    db.session.commit()
    flash(f'{c.name}: {"đã xác minh" if c.verified else "bỏ xác minh"}.', 'success')
    return redirect(request.referrer or url_for('admin.users'))


@admin.route('/jobs')
@admin_required
def jobs():
    q, status = request.args.get('q', '').strip(), request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    query = sa.select(JobPost).order_by(JobPost.created_at.desc())
    if q:
        query = query.where(JobPost.title.ilike(f'%{q}%'))
    if status == 'HIDDEN':
        query = query.where(JobPost.hidden.is_(True))
    elif status:
        query = query.where(JobPost.status == status)
    pagination = db.paginate(query, page=page, per_page=current_app.config['ADMIN_PER_PAGE'], error_out=False)
    return render_template('admin/jobs.html', pagination=pagination, jobs=pagination.items, q=q, status=status)


@admin.route('/jobs/<int:job_id>/toggle-hidden', methods=['POST'])
@admin_required
def toggle_hidden(job_id):
    job = db.get_or_404(JobPost, job_id)
    job.hidden = not job.hidden
    db.session.commit()
    flash(f'Đã {"ẩn" if job.hidden else "hiện"} tin "{job.title}".', 'success')
    return redirect(request.referrer or url_for('admin.jobs'))


@admin.route('/export/applications.csv')
@admin_required
def export_applications():
    rows = db.session.scalars(sa.select(Application).order_by(Application.created_at)).all()
    buf = io.StringIO()
    buf.write('﻿')            # BOM để Excel đọc đúng tiếng Việt
    w = csv.writer(buf)
    w.writerow(['id', 'tin', 'nha_tuyen_dung', 'sinh_vien', 'email', 'trang_thai', 'diem_phu_hop', 'ngay_nop'])
    for a in rows:
        w.writerow([a.id, a.job.title, a.job.employer.display_name, a.student.full_name, a.student.email,
                    a.status, a.match_score, a.created_at.strftime('%Y-%m-%d %H:%M')])
    return Response(buf.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=applications.csv'})


@admin.route('/outbox')
@admin_required
def outbox():
    """Email đã 'gửi' khi chưa cấu hình SMTP (MAIL_SUPPRESS_SEND) – dùng khi demo."""
    folder = os.path.join(current_app.instance_path, 'outbox')
    items = []
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder), reverse=True)[:50]:
            with open(os.path.join(folder, name), 'rb') as f:
                msg = email.message_from_bytes(f.read(), policy=email.policy.default)
            body = msg.get_body(preferencelist=('plain',))
            items.append({'name': name, 'to': msg['To'], 'subject': msg['Subject'],
                          'body': body.get_content() if body else ''})
    return render_template('admin/outbox.html', items=items, suppress=current_app.config['MAIL_SUPPRESS_SEND'])
