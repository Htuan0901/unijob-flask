"""Khu vực sinh viên: bảng điều khiển, hồ sơ, việc đã lưu, thông báo việc làm (CRUD), CV, đánh giá."""
import sqlalchemy as sa
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from . import student
from .forms import CVUploadForm, JobAlertForm, ProfileForm, ReviewForm
from .. import db
from ..decorators import student_required
from ..main.routes import open_jobs_query
from ..models import Application, JobAlert, JobPost, Review, StudentProfile, User, saved_jobs
from ..services import recommender
from ..services.cv_files import CVError, remove_cv, save_cv
from ..services.workflow import WorkflowError, add_review, pending_reviews, withdraw as withdraw_app
from ..utils.text import join_skills, split_skills


@student.route('/')
@student_required
def dashboard():
    status = request.args.get('status')
    query = current_user.applications.select().order_by(Application.created_at.desc())
    if status:
        query = query.where(Application.status == status)
    apps = db.session.scalars(query).all()
    counts = dict(db.session.execute(sa.select(Application.status, sa.func.count(Application.id))
                                     .where(Application.student_id == current_user.id)
                                     .group_by(Application.status)).all())
    applied_ids = {a.job_id for a in db.session.scalars(current_user.applications.select())}
    pool = db.session.scalars(open_jobs_query().order_by(JobPost.created_at.desc()).limit(300)).all()
    recs = recommender.recommend(current_user.student_profile, pool, exclude_ids=applied_ids, limit=6) \
        if current_user.student_profile else []
    return render_template('student/dashboard.html', apps=apps, counts=counts, recs=recs, status=status,
                           pending=pending_reviews(current_user))


@student.route('/applications/<int:app_id>/withdraw', methods=['POST'])
@student_required
def withdraw(app_id):
    app = db.get_or_404(Application, app_id)
    try:
        withdraw_app(app, current_user)
        db.session.commit()
        flash('Đã rút hồ sơ.', 'info')
    except WorkflowError as e:
        db.session.rollback()
        flash(str(e), 'warning')
    return redirect(url_for('student.dashboard'))


@student.route('/profile', methods=['GET', 'POST'])
@student_required
def profile():
    p = current_user.student_profile or StudentProfile(user=current_user)
    form = ProfileForm(obj=p)
    if request.method == 'GET':
        form.full_name.data, form.phone.data = current_user.full_name, current_user.phone
    if form.validate_on_submit():
        current_user.full_name, current_user.phone = form.full_name.data, form.phone.data
        form.populate_obj(p)
        p.skills = join_skills(split_skills(form.skills.data))
        p.preferred_category = form.preferred_category.data or None
        db.session.add(p)
        db.session.commit()
        flash('Đã cập nhật hồ sơ. Gợi ý việc làm sẽ dựa trên hồ sơ mới.', 'success')
        return redirect(url_for('student.dashboard'))
    return render_template('student/profile.html', form=form)


@student.route('/saved')
@student_required
def saved():
    jobs = db.session.scalars(sa.select(JobPost).join(saved_jobs, saved_jobs.c.job_id == JobPost.id)
                              .where(saved_jobs.c.user_id == current_user.id)
                              .order_by(saved_jobs.c.created_at.desc())).all()
    return render_template('student/saved.html', jobs=jobs)


# ---------------------------------------------------------------- Job alerts (CRUD đầy đủ)
@student.route('/alerts', methods=['GET', 'POST'])
@student_required
def alerts():
    form = JobAlertForm()
    if form.validate_on_submit():
        alert = JobAlert(user=current_user)
        _fill_alert(alert, form)
        db.session.add(alert)
        db.session.commit()
        flash('Đã tạo thông báo việc làm.', 'success')
        return redirect(url_for('student.alerts'))
    items = db.session.scalars(current_user.job_alerts.select().order_by(JobAlert.created_at.desc())).all()
    return render_template('student/alerts.html', form=form, items=items)


def _fill_alert(alert, form):
    alert.name, alert.keyword = form.name.data, form.keyword.data or None
    alert.category_code, alert.city = form.category_code.data or None, form.city.data or None
    alert.job_type = form.job_type.data or None
    alert.min_salary = form.min_salary.data * 1_000_000 if form.min_salary.data else None
    alert.email_enabled, alert.active = form.email_enabled.data, form.active.data


def _own_alert(alert_id):
    alert = db.get_or_404(JobAlert, alert_id)
    if alert.user_id != current_user.id:
        abort(403)
    return alert


@student.route('/alerts/<int:alert_id>/edit', methods=['GET', 'POST'])
@student_required
def edit_alert(alert_id):
    alert = _own_alert(alert_id)
    form = JobAlertForm(obj=alert)
    if request.method == 'GET':
        form.min_salary.data = alert.min_salary // 1_000_000 if alert.min_salary else None
    if form.validate_on_submit():
        _fill_alert(alert, form)
        db.session.commit()
        flash('Đã cập nhật thông báo việc làm.', 'success')
        return redirect(url_for('student.alerts'))
    return render_template('student/alert_edit.html', form=form, alert=alert)


@student.route('/alerts/<int:alert_id>/delete', methods=['POST'])
@student_required
def delete_alert(alert_id):
    alert = _own_alert(alert_id)
    db.session.delete(alert)
    db.session.commit()
    flash('Đã xóa thông báo việc làm.', 'info')
    return redirect(url_for('student.alerts'))


@student.route('/alerts/<int:alert_id>/preview')
@student_required
def preview_alert(alert_id):
    alert = _own_alert(alert_id)
    pool = db.session.scalars(open_jobs_query().order_by(JobPost.created_at.desc()).limit(500)).all()
    matches = [j for j in pool if alert.matches(j)][:20]
    return render_template('student/alert_preview.html', alert=alert, jobs=matches)


# ---------------------------------------------------------------- CV + đánh giá
@student.route('/cv')
@student_required
def cv():
    done = db.session.scalars(current_user.applications.select().where(Application.status == 'COMPLETED')
                              .order_by(Application.created_at.desc())).all()
    reviews = db.session.scalars(sa.select(Review).where(Review.reviewee_id == current_user.id)
                                 .order_by(Review.created_at.desc())).all()
    return render_template('student/cv.html', u=current_user, p=current_user.student_profile, done=done,
                           reviews=reviews, form=CVUploadForm())


@student.route('/cv/upload', methods=['POST'])
@student_required
def upload_cv():
    """Tải CV PDF lên (Flask-WTF FileField + kiểm tra chữ ký PDF), thay CV cũ nếu có."""
    form = CVUploadForm()
    p = current_user.student_profile or StudentProfile(user=current_user)
    if form.validate_on_submit():
        try:
            db.session.add(p)
            db.session.flush()                      # cần user_id để đặt tên tệp
            save_cv(p, form.cv.data)
            db.session.commit()
            flash('Đã tải CV lên. Nhà tuyển dụng có thể xem CV khi bạn ứng tuyển.', 'success')
        except CVError as e:
            db.session.rollback()
            flash(str(e), 'danger')
    else:
        for err in form.cv.errors:
            flash(err, 'danger')
    return redirect(url_for('student.cv'))


@student.route('/cv/delete', methods=['POST'])
@student_required
def delete_cv():
    p = current_user.student_profile
    if p and p.has_cv:
        remove_cv(p)
        db.session.commit()
        flash('Đã xóa tệp CV.', 'info')
    return redirect(url_for('student.cv'))


@student.route('/review/<int:job_id>', methods=['GET', 'POST'])
@student_required
def review(job_id):
    job = db.get_or_404(JobPost, job_id)
    form = ReviewForm()
    if form.validate_on_submit():
        try:
            add_review(job, current_user, job.employer, int(form.rating.data), form.comment.data)
            db.session.commit()
            flash('Cảm ơn bạn đã đánh giá!', 'success')
            return redirect(url_for('student.dashboard'))
        except WorkflowError as e:
            db.session.rollback()
            flash(str(e), 'warning')
    return render_template('review_form.html', form=form, job=job, target=job.employer.display_name)
