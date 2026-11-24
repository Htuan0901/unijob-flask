"""Khu vực nhà tuyển dụng: CRUD tin tuyển dụng, duyệt hồ sơ, đổi trạng thái, đánh giá sinh viên, tìm ứng viên."""
import sqlalchemy as sa
from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from . import employer
from .forms import CompanyForm, DecisionForm, JobForm, StatusForm
from .. import db
from ..decorators import employer_required
from ..models import Application, Category, EmployerProfile, JobPost, StudentProfile, User
from ..net.geocode import geocode
from ..services import recommender
from ..services.workflow import (WorkflowError, add_review, change_job_status, decide as decide_app,
                                 on_job_created)
from ..student.forms import ReviewForm
from ..utils.text import join_skills, split_skills


def _own_job(job_id):
    job = db.get_or_404(JobPost, job_id)
    if job.employer_id != current_user.id:
        abort(403)
    return job


@employer.route('/')
@employer_required
def dashboard():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status')
    query = current_user.jobs.select().order_by(JobPost.created_at.desc())
    if status:
        query = query.where(JobPost.status == status)
    pagination = db.paginate(query, page=page, per_page=10, error_out=False)
    stats = {
        'jobs': db.session.scalar(sa.select(sa.func.count(JobPost.id)).where(JobPost.employer_id == current_user.id)),
        'open': db.session.scalar(sa.select(sa.func.count(JobPost.id)).where(JobPost.employer_id == current_user.id,
                                                                             JobPost.status == 'OPEN')),
        'pending': db.session.scalar(sa.select(sa.func.count(Application.id)).join(Application.job).where(
            JobPost.employer_id == current_user.id, Application.status == 'PENDING')),
        'views': db.session.scalar(sa.select(sa.func.coalesce(sa.func.sum(JobPost.view_count), 0))
                                   .where(JobPost.employer_id == current_user.id)),
    }
    return render_template('employer/dashboard.html', pagination=pagination, jobs=pagination.items,
                           stats=stats, status=status, status_form=StatusForm())


def _fill_job(job, form):
    job.title, job.job_type, job.city = form.title.data.strip(), form.job_type.data, form.city.data
    with db.session.no_autoflush:
        job.category = db.session.scalar(sa.select(Category).where(Category.code == form.category.data))
    job.salary_min, job.salary_max, job.salary_unit = form.salary_min.data, form.salary_max.data, form.salary_unit.data
    job.working_hours, job.experience_level = form.working_hours.data, form.experience_level.data
    job.slots, job.deadline, job.urgent = form.slots.data, form.deadline.data, form.urgent.data
    job.description, job.requirements, job.benefits = form.description.data, form.requirements.data, form.benefits.data
    job.skills = join_skills(split_skills(form.skills.data))
    new_address = form.address.data or None
    if new_address != job.address or job.latitude is None:
        job.address = new_address
        coords = geocode(job.address, job.city) if job.address else None   # gọi API bản đồ (urllib)
        job.latitude, job.longitude = coords if coords else (None, None)
    job.update_monthly_salary()


@employer.route('/jobs/new', methods=['GET', 'POST'])
@employer_required
def new_job():
    form = JobForm()
    if request.method == 'GET' and current_user.employer_profile:
        form.city.data = current_user.employer_profile.city
        form.address.data = current_user.employer_profile.address
    if form.validate_on_submit():
        job = JobPost(employer=current_user)
        _fill_job(job, form)
        db.session.add(job)
        db.session.flush()
        n = on_job_created(job)
        db.session.commit()
        flash(f'Đã đăng tin "{job.title}". Đã báo cho {n} sinh viên quan tâm.', 'success')
        return redirect(url_for('main.job_detail', job_id=job.id))
    return render_template('employer/job_form.html', form=form, job=None)


@employer.route('/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
@employer_required
def edit_job(job_id):
    job = _own_job(job_id)
    form = JobForm(obj=job)
    if request.method == 'GET':
        form.category.data = job.category.code if job.category else None
        form.skills.data = job.skills
    if form.validate_on_submit():
        _fill_job(job, form)
        db.session.commit()
        flash('Đã cập nhật tin.', 'success')
        return redirect(url_for('main.job_detail', job_id=job.id))
    return render_template('employer/job_form.html', form=form, job=job)


@employer.route('/jobs/<int:job_id>/delete', methods=['POST'])
@employer_required
def delete_job(job_id):
    job = _own_job(job_id)
    if job.count_applications(['ACCEPTED', 'COMPLETED']):
        flash('Tin đã có người được nhận nên không thể xóa, hãy chuyển sang "Đóng tin".', 'warning')
    else:
        db.session.delete(job)
        db.session.commit()
        flash('Đã xóa tin.', 'info')
    return redirect(url_for('employer.dashboard'))


@employer.route('/jobs/<int:job_id>/status', methods=['POST'])
@employer_required
def job_status(job_id):
    job = _own_job(job_id)
    form = StatusForm()
    if form.validate_on_submit():
        try:
            change_job_status(job, form.status.data, current_user)
            db.session.commit()
            flash(f'Tin "{job.title}" chuyển sang {job.status_label}.', 'success')
        except WorkflowError as e:
            db.session.rollback()
            flash(str(e), 'warning')
    return redirect(request.referrer or url_for('employer.dashboard'))


@employer.route('/jobs/<int:job_id>/applicants')
@employer_required
def applicants(job_id):
    job = _own_job(job_id)
    apps = db.session.scalars(job.applications.select().order_by(Application.match_score.desc(),
                                                                  Application.created_at)).all()
    gaps = {a.id: recommender.skill_match(a.student.student_profile.skill_list if a.student.student_profile else [],
                                          job.skill_list) for a in apps}
    from ..services.workflow import can_review
    reviewable = {a.id for a in apps if a.status == 'COMPLETED' and can_review(job, current_user, a.student)}
    return render_template('employer/applicants.html', job=job, apps=apps, gaps=gaps, form=DecisionForm(),
                           reviewable=reviewable, status_form=StatusForm(status=job.status))


@employer.route('/applications/<int:app_id>/decide', methods=['POST'])
@employer_required
def decide(app_id):
    app = db.get_or_404(Application, app_id)
    form = DecisionForm()
    if form.validate_on_submit():
        try:
            decide_app(app, bool(form.accept.data), current_user, form.note.data)
            db.session.commit()
            flash(f'Đã {"nhận" if form.accept.data else "từ chối"} {app.student.full_name}.', 'success')
        except WorkflowError as e:
            db.session.rollback()
            flash(str(e), 'warning')
    return redirect(url_for('employer.applicants', job_id=app.job_id))


@employer.route('/review/<int:job_id>/<int:student_id>', methods=['GET', 'POST'])
@employer_required
def review(job_id, student_id):
    job = _own_job(job_id)
    student = db.get_or_404(User, student_id)
    form = ReviewForm()
    if form.validate_on_submit():
        try:
            add_review(job, current_user, student, int(form.rating.data), form.comment.data)
            db.session.commit()
            flash('Đã gửi đánh giá.', 'success')
            return redirect(url_for('employer.applicants', job_id=job.id))
        except WorkflowError as e:
            db.session.rollback()
            flash(str(e), 'warning')
    return render_template('review_form.html', form=form, job=job, target=student.full_name)


@employer.route('/company', methods=['GET', 'POST'])
@employer_required
def company():
    p = current_user.employer_profile or EmployerProfile(user=current_user)
    form = CompanyForm(obj=p)
    if request.method == 'GET':
        form.full_name.data, form.phone.data = current_user.full_name, current_user.phone
    if form.validate_on_submit():
        current_user.full_name, current_user.phone = form.full_name.data, form.phone.data
        form.populate_obj(p)
        p.company_name = form.company_name.data or None
        p.individual = not p.company_name
        db.session.add(p)
        db.session.commit()
        flash('Đã lưu thông tin nhà tuyển dụng.', 'success')
        return redirect(url_for('employer.dashboard'))
    return render_template('employer/company.html', form=form)


@employer.route('/candidates')
@employer_required
def candidates():
    """Tìm ứng viên phù hợp với một tin của mình (xếp theo điểm phù hợp)."""
    my_jobs = db.session.scalars(current_user.jobs.select().where(JobPost.status == 'OPEN')
                                 .order_by(JobPost.created_at.desc())).all()
    job_id = request.args.get('job_id', type=int) or (my_jobs[0].id if my_jobs else None)
    job = _own_job(job_id) if job_id else None
    results = []
    if job:
        profiles = db.session.scalars(sa.select(StudentProfile).join(StudentProfile.user)
                                      .where(User.enabled.is_(True))).all()
        results = sorted(((recommender.match_score(p, job), p) for p in profiles), key=lambda x: -x[0])[:20]
    return render_template('employer/candidates.html', my_jobs=my_jobs, job=job, results=results)
