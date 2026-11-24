"""Khu vực công khai: trang chủ, tìm kiếm + lọc + phân trang, chi tiết tin, công ty, tra cứu lương, tin tức."""
from datetime import timedelta
import io

import sqlalchemy as sa
from flask import (abort, current_app, flash, redirect, render_template, request, send_file, url_for)
from flask_login import current_user, login_required

from . import main
from .forms import ApplyForm, EmptyForm, JobSearchForm, SalaryLookupForm
from .. import db
from ..constants import CATEGORIES, EXPERIENCE_LEVELS
from ..decorators import student_required
from ..models import (Application, Category, EmployerProfile, JobPost, Notification, Review, User,
                      company_follows, saved_jobs, utcnow)
from ..net import exchange, news
from ..services import cv_files, market, recommender
from ..services.workflow import WorkflowError, apply as apply_job, pending_reviews


def open_jobs_query():
    today = utcnow().date()
    return (sa.select(JobPost).where(JobPost.status == 'OPEN', JobPost.hidden.is_(False),
                                     sa.or_(JobPost.deadline.is_(None), JobPost.deadline >= today)))


def apply_filters(query, form):
    """Thêm điều kiện WHERE theo form tìm kiếm."""
    if form.q.data:
        like = f'%{form.q.data.strip()}%'
        query = query.where(sa.or_(JobPost.title.ilike(like), JobPost.skills.ilike(like),
                                   JobPost.description.ilike(like)))
    if form.category.data:
        query = query.where(JobPost.category.has(Category.code == form.category.data))
    if form.city.data:
        query = query.where(JobPost.city == form.city.data)
    if form.job_type.data:
        query = query.where(JobPost.job_type == form.job_type.data)
    if form.experience.data:
        query = query.where(JobPost.experience_level == form.experience.data)
    if form.min_salary.data:
        query = query.where(JobPost.salary_monthly_max >= form.min_salary.data * 1_000_000)
    if form.posted.data:
        query = query.where(JobPost.created_at >= utcnow() - timedelta(days=int(form.posted.data)))
    if form.urgent.data:
        query = query.where(JobPost.urgent.is_(True))
    return query


@main.app_context_processor
def inject_globals():
    unread = current_user.unread_notifications() if current_user.is_authenticated else 0
    return {'unread_count': unread, 'empty_form': EmptyForm(), 'CATEGORIES': CATEGORIES}


@main.route('/')
def index():
    form = JobSearchForm(formdata=None)
    counts = dict(db.session.execute(
        sa.select(Category.code, sa.func.count(JobPost.id)).join(JobPost, JobPost.category_id == Category.id)
        .where(JobPost.status == 'OPEN', JobPost.hidden.is_(False)).group_by(Category.code)).all())
    latest = db.session.scalars(open_jobs_query().order_by(JobPost.created_at.desc()).limit(6)).all()
    urgent = db.session.scalars(open_jobs_query().where(JobPost.urgent.is_(True))
                                .order_by(JobPost.created_at.desc()).limit(4)).all()
    recs = []
    if current_user.is_authenticated and current_user.is_student and current_user.student_profile:
        pool = db.session.scalars(open_jobs_query().order_by(JobPost.created_at.desc()).limit(300)).all()
        recs = recommender.recommend(current_user.student_profile, pool, limit=4)
    total = db.session.scalar(sa.select(sa.func.count()).select_from(open_jobs_query().subquery()))
    companies = db.session.scalar(sa.select(sa.func.count(EmployerProfile.id)))
    return render_template('index.html', form=form, counts=counts, latest=latest, urgent=urgent,
                           recs=recs, total=total, companies=companies, market=market.stats())


@main.route('/jobs')
def jobs():
    form = JobSearchForm(request.args)
    form.validate()
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['JOBS_PER_PAGE']
    query = apply_filters(open_jobs_query(), form)
    sort = form.sort.data or 'newest'
    if sort == 'match' and current_user.is_authenticated and current_user.is_student \
            and current_user.student_profile:
        # Xếp theo điểm phù hợp: tính trên tập kết quả rồi phân trang thủ công
        pool = db.session.scalars(query.order_by(JobPost.created_at.desc()).limit(500)).all()
        scored = recommender.recommend(current_user.student_profile, pool, limit=len(pool))
        pagination = ManualPagination([s.job for s in scored], page, per_page)
        scores = {s.job.id: s.score for s in scored}
    else:
        order = {'salary': JobPost.salary_monthly_max.desc().nulls_last(), 'views': JobPost.view_count.desc()}
        query = query.order_by(order.get(sort, JobPost.created_at.desc()), JobPost.id.desc())
        pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
        scores = {}
    args = {k: v for k, v in request.args.items() if k != 'page'}
    return render_template('jobs/list.html', form=form, pagination=pagination, jobs=pagination.items,
                           scores=scores, args=args)


class ManualPagination:
    """Phân trang cho danh sách đã có sẵn trong bộ nhớ, cùng giao diện với db.paginate()."""

    def __init__(self, items, page, per_page):
        self.total = len(items)
        self.per_page = per_page
        self.pages = max(1, -(-self.total // per_page))
        self.page = min(max(page, 1), self.pages)
        self.items = items[(self.page - 1) * per_page: self.page * per_page]
        self.has_prev, self.has_next = self.page > 1, self.page < self.pages
        self.prev_num, self.next_num = self.page - 1, self.page + 1

    def iter_pages(self, left_edge=2, left_current=2, right_current=4, right_edge=2):
        last = 0
        for num in range(1, self.pages + 1):
            if (num <= left_edge or (self.page - left_current - 1 < num < self.page + right_current)
                    or num > self.pages - right_edge):
                if last + 1 != num:
                    yield None
                yield num
                last = num


@main.route('/jobs/<int:job_id>')
def job_detail(job_id):
    job = db.get_or_404(JobPost, job_id)
    owner = current_user.is_authenticated and (current_user.id == job.employer_id or current_user.is_admin)
    if job.hidden and not owner:
        abort(404)
    job.view_count = (job.view_count or 0) + 1
    db.session.commit()
    my_app, gap = None, None
    if current_user.is_authenticated and current_user.is_student:
        my_app = db.session.scalar(sa.select(Application).where(Application.job_id == job.id,
                                                                 Application.student_id == current_user.id))
        if current_user.student_profile:
            gap = recommender.skill_match(current_user.student_profile.skill_list, job.skill_list)
    pool = db.session.scalars(open_jobs_query().where(JobPost.id != job.id)
                              .order_by(JobPost.created_at.desc()).limit(200)).all()
    similar = recommender.similar(job, pool, limit=4)
    reviews = db.session.scalars(sa.select(Review).where(Review.reviewee_id == job.employer_id)
                                 .order_by(Review.created_at.desc()).limit(3)).all()
    rates = exchange.get_rates()
    return render_template('jobs/detail.html', job=job, form=ApplyForm(), my_app=my_app, gap=gap,
                           similar=similar, reviews=reviews, rates=rates, owner=owner)


@main.route('/jobs/<int:job_id>/apply', methods=['POST'])
@student_required
def apply(job_id):
    job = db.get_or_404(JobPost, job_id)
    form = ApplyForm()
    if form.validate_on_submit():
        try:
            app = apply_job(job, current_user, form.cover_letter.data)
            db.session.commit()
            flash(f'Đã gửi hồ sơ! Mức độ phù hợp của bạn: {app.match_score}%.', 'success')
        except WorkflowError as e:
            db.session.rollback()
            flash(str(e), 'warning')
    return redirect(url_for('main.job_detail', job_id=job.id))


@main.route('/jobs/<int:job_id>/save', methods=['POST'])
@student_required
def toggle_save(job_id):
    job = db.get_or_404(JobPost, job_id)
    if EmptyForm().validate_on_submit():
        if current_user.has_saved(job):
            db.session.execute(sa.delete(saved_jobs).where(saved_jobs.c.user_id == current_user.id,
                                                           saved_jobs.c.job_id == job.id))
            flash('Đã bỏ lưu tin.', 'info')
        else:
            current_user.saved.add(job)
            flash('Đã lưu tin vào danh sách của bạn.', 'success')
        db.session.commit()
    return redirect(request.referrer or url_for('main.job_detail', job_id=job.id))


# ---------------------------------------------------------------- công ty
@main.route('/companies')
def companies():
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    job_count = (sa.select(sa.func.count(JobPost.id)).where(JobPost.employer_id == EmployerProfile.user_id,
                                                            JobPost.status == 'OPEN', JobPost.hidden.is_(False))
                 .correlate(EmployerProfile).scalar_subquery())
    query = sa.select(EmployerProfile).where(EmployerProfile.company_name.is_not(None))
    if q:
        query = query.where(EmployerProfile.company_name.ilike(f'%{q}%'))
    query = query.order_by(job_count.desc(), EmployerProfile.company_name)
    pagination = db.paginate(query, page=page, per_page=12, error_out=False)
    rows = [(c, db.session.scalar(sa.select(sa.func.count(JobPost.id)).where(
        JobPost.employer_id == c.user_id, JobPost.status == 'OPEN', JobPost.hidden.is_(False))))
        for c in pagination.items]
    return render_template('companies/list.html', rows=rows, pagination=pagination, q=q)


@main.route('/companies/<int:company_id>')
def company_detail(company_id):
    company = db.get_or_404(EmployerProfile, company_id)
    jobs = db.session.scalars(open_jobs_query().where(JobPost.employer_id == company.user_id)
                              .order_by(JobPost.created_at.desc())).all()
    reviews = db.session.scalars(sa.select(Review).where(Review.reviewee_id == company.user_id)
                                 .order_by(Review.created_at.desc())).all()
    following = current_user.is_authenticated and current_user.is_student and current_user.is_following(company)
    return render_template('companies/detail.html', company=company, jobs=jobs, reviews=reviews, following=following)


@main.route('/companies/<int:company_id>/follow', methods=['POST'])
@student_required
def toggle_follow(company_id):
    company = db.get_or_404(EmployerProfile, company_id)
    if EmptyForm().validate_on_submit():
        if current_user.is_following(company):
            db.session.execute(sa.delete(company_follows).where(company_follows.c.user_id == current_user.id,
                                                                company_follows.c.company_id == company.id))
            flash(f'Đã bỏ theo dõi {company.name}.', 'info')
        else:
            current_user.followed_companies.add(company)
            flash(f'Đang theo dõi {company.name}. Bạn sẽ được báo khi có tin mới.', 'success')
        db.session.commit()
    return redirect(url_for('main.company_detail', company_id=company.id))


@main.route('/students/<int:user_id>')
@login_required
def student_public(user_id):
    user = db.get_or_404(User, user_id)
    if not user.is_student or not (current_user.is_employer or current_user.is_admin or current_user.id == user.id):
        abort(404 if not user.is_student else 403)
    reviews = db.session.scalars(sa.select(Review).where(Review.reviewee_id == user.id)
                                 .order_by(Review.created_at.desc())).all()
    done = db.session.scalar(sa.select(sa.func.count(Application.id)).where(
        Application.student_id == user.id, Application.status == 'COMPLETED'))
    return render_template('student/public.html', user=user, p=user.student_profile, reviews=reviews, done=done)


@main.route('/students/<int:user_id>/cv')
@login_required
def student_cv(user_id):
    """Xem (inline) hoặc tải về (?download=1) CV PDF. Chỉ chủ CV, nhà tuyển dụng và admin."""
    user = db.get_or_404(User, user_id)
    if not (current_user.is_employer or current_user.is_admin or current_user.id == user.id):
        abort(403)
    p = user.student_profile
    data = cv_files.read_cv(p)
    if data is None:
        abort(404)
    return send_file(io.BytesIO(data), mimetype='application/pdf',
                     as_attachment=request.args.get('download') == '1',
                     download_name=p.cv_original_name or 'cv.pdf', max_age=0)


# ---------------------------------------------------------------- công cụ dữ liệu
@main.route('/salary')
def salary():
    form = SalaryLookupForm(request.args)
    form.city.choices = [('', 'Toàn quốc')] + [(c, c) for c in market.lookup_cities()]
    result = market.salary_lookup(form.category.data, form.experience.data, form.city.data)
    suggestion = market.suggest_salary(form.category.data) if form.category.data else None
    return render_template('salary.html', form=form, data=result, suggestion=suggestion,
                           stats=market.stats(), exp_labels=EXPERIENCE_LEVELS)


@main.route('/news')
def news_page():
    return render_template('news.html', feed=news.get_news())


@main.route('/currency')
def currency():
    amount = request.args.get('amount', 5_000_000, type=int)
    rates = exchange.get_rates()
    return render_template('currency.html', amount=amount, rates=rates)


@main.route('/about')
def about():
    return render_template('about.html')


# ---------------------------------------------------------------- thông báo
@main.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    query = current_user.notifications.select().order_by(Notification.created_at.desc())
    pagination = db.paginate(query, page=page, per_page=15, error_out=False)
    items = list(pagination.items)
    reviews = pending_reviews(current_user)
    db.session.execute(sa.update(Notification).where(Notification.user_id == current_user.id,
                                                     Notification.read.is_(False)).values(read=True))
    db.session.commit()
    return render_template('notifications.html', items=items, pagination=pagination, pending=reviews)
