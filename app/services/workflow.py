"""Nghiệp vụ chính: đăng tin → ứng tuyển → duyệt → hoàn thành → đánh giá hai chiều.

Các hàm ở đây không phụ thuộc request (dễ kiểm thử), ném WorkflowError khi vi phạm quy tắc.
Route chỉ gọi hàm, bắt lỗi và flash thông báo.
"""
import sqlalchemy as sa
from flask import url_for, current_app

from .. import db
from ..constants import JOB_TRANSITIONS, JOB_STATUSES
from ..email import send_email
from ..models import Application, JobAlert, Notification, Review, User, company_follows, utcnow
from . import recommender


class WorkflowError(Exception):
    pass


# ---------------------------------------------------------------- thông báo
def notify(user, type_, message, link=None, email_template=None, subject=None, **email_ctx):
    db.session.add(Notification(user_id=user.id, type=type_, message=message, link=link))
    if email_template and user.email:
        try:
            send_email(user.email, subject or message, email_template, user=user, link=link,
                       message=message, **email_ctx)
        except Exception as exc:     # email lỗi không chặn nghiệp vụ
            current_app.logger.warning('Không gửi được email: %s', exc)


# ---------------------------------------------------------------- tin tuyển dụng
def on_job_created(job):
    """Gọi sau khi tin mới được lưu: báo người theo dõi công ty và các job alert khớp."""
    link = url_for('main.job_detail', job_id=job.id)
    company = job.employer.employer_profile
    notified = set()
    if company:
        follower_ids = db.session.scalars(sa.select(company_follows.c.user_id)
                                          .where(company_follows.c.company_id == company.id)).all()
        for uid in follower_ids:
            u = db.session.get(User, uid)
            notify(u, 'COMPANY_NEW_JOB', f'{company.name} vừa đăng tin: {job.title}', link)
            notified.add(uid)
    alerts = db.session.scalars(sa.select(JobAlert).where(JobAlert.active.is_(True))).all()
    for a in alerts:
        if a.user_id in notified or not a.matches(job):
            continue
        notify(a.user, 'JOB_ALERT', f'Có việc mới khớp "{a.name}": {job.title}', link,
               email_template='email/job_alert' if a.email_enabled else None,
               subject=f'Việc làm mới khớp "{a.name}"', job=job, alert=a)
        notified.add(a.user_id)
    return len(notified)


def change_job_status(job, new_status, actor):
    if actor.id != job.employer_id and not actor.is_admin:
        raise WorkflowError('Bạn không có quyền đổi trạng thái tin này.')
    if new_status not in JOB_TRANSITIONS.get(job.status, set()):
        raise WorkflowError(f'Không thể chuyển từ "{job.status_label}" sang "{JOB_STATUSES.get(new_status, new_status)}".')
    job.status = new_status
    link = url_for('main.job_detail', job_id=job.id)
    if new_status == 'COMPLETED':
        accepted = db.session.scalars(job.applications.select().where(Application.status == 'ACCEPTED')).all()
        for a in accepted:
            a.status = 'COMPLETED'
            notify(a.student, 'REVIEW_REMINDER',
                   f'Công việc "{job.title}" đã hoàn thành. Hãy đánh giá nhà tuyển dụng.',
                   url_for('student.dashboard'))
        notify(job.employer, 'REVIEW_REMINDER', f'Hãy đánh giá {len(accepted)} sinh viên đã làm "{job.title}".',
               url_for('employer.applicants', job_id=job.id))
    elif new_status in ('CLOSED',):
        pending = db.session.scalars(job.applications.select().where(Application.status == 'PENDING')).all()
        for a in pending:
            a.status = 'REJECTED'
            a.decided_at = utcnow()
            notify(a.student, 'JOB_STATUS', f'Tin "{job.title}" đã đóng, hồ sơ của bạn không được xét tiếp.', link)
    return job


# ---------------------------------------------------------------- ứng tuyển
def apply(job, student, cover_letter=''):
    if not student.is_student:
        raise WorkflowError('Chỉ sinh viên mới được ứng tuyển.')
    if not job.is_open:
        raise WorkflowError('Tin này không còn nhận hồ sơ.')
    app = db.session.scalar(sa.select(Application).where(Application.job_id == job.id,
                                                          Application.student_id == student.id))
    if app and app.status != 'WITHDRAWN':
        raise WorkflowError('Bạn đã ứng tuyển tin này rồi.')
    score = recommender.match_score(student.student_profile, job)
    if app is None:
        app = Application(job=job, student=student)
        db.session.add(app)
    app.status, app.cover_letter, app.match_score = 'PENDING', cover_letter, score
    app.created_at, app.decided_at, app.employer_note = utcnow(), None, None
    db.session.flush()
    notify(job.employer, 'NEW_APPLICATION', f'{student.full_name} ứng tuyển "{job.title}" (phù hợp {score}%).',
           url_for('employer.applicants', job_id=job.id),
           email_template='email/new_application', subject=f'Hồ sơ mới cho "{job.title}"',
           job=job, student=student, score=score)
    return app


def decide(application, accept, actor, note=None):
    job = application.job
    if actor.id != job.employer_id:
        raise WorkflowError('Bạn không phải chủ tin này.')
    if application.status != 'PENDING':
        raise WorkflowError('Chỉ duyệt được hồ sơ đang chờ.')
    if accept and job.status != 'OPEN':
        raise WorkflowError('Tin không còn ở trạng thái Đang tuyển.')
    application.status = 'ACCEPTED' if accept else 'REJECTED'
    application.employer_note = note
    application.decided_at = utcnow()
    verb = 'được nhận' if accept else 'chưa phù hợp'
    notify(application.student, 'APPLICATION_ACCEPTED' if accept else 'APPLICATION_REJECTED',
           f'Hồ sơ "{job.title}" của bạn {verb}.', url_for('student.dashboard'),
           email_template='email/application_decision', subject=f'Kết quả ứng tuyển "{job.title}"',
           job=job, accepted=accept, note=note)
    if accept and job.count_applications('ACCEPTED') >= job.slots:
        job.status = 'FILLED'
        notify(job.employer, 'JOB_STATUS', f'Tin "{job.title}" đã đủ {job.slots} người, tự chuyển sang Đã đủ người.',
               url_for('employer.applicants', job_id=job.id))
    return application


def withdraw(application, actor):
    if actor.id != application.student_id:
        raise WorkflowError('Bạn không thể rút hồ sơ này.')
    if application.status not in ('PENDING', 'ACCEPTED'):
        raise WorkflowError('Hồ sơ này không thể rút.')
    was_accepted = application.status == 'ACCEPTED'
    application.status = 'WITHDRAWN'
    job = application.job
    if was_accepted and job.status == 'FILLED':
        job.status = 'OPEN'
    notify(job.employer, 'APPLICATION_WITHDRAWN', f'{actor.full_name} đã rút hồ sơ "{job.title}".',
           url_for('employer.applicants', job_id=job.id))
    return application


# ---------------------------------------------------------------- đánh giá hai chiều
def can_review(job, reviewer, reviewee):
    """Chỉ đánh giá được khi giữa hai bên có hồ sơ ở trạng thái COMPLETED và chưa đánh giá trước đó."""
    if reviewer.id == reviewee.id:
        return False
    student = reviewer if reviewer.is_student else reviewee
    employer = reviewer if reviewer.is_employer else reviewee
    if employer.id != job.employer_id or not student.is_student:
        return False
    done = db.session.scalar(sa.select(Application).where(
        Application.job_id == job.id, Application.student_id == student.id, Application.status == 'COMPLETED'))
    if done is None:
        return False
    existed = db.session.scalar(sa.select(Review).where(
        Review.job_id == job.id, Review.reviewer_id == reviewer.id, Review.reviewee_id == reviewee.id))
    return existed is None


def add_review(job, reviewer, reviewee, rating, comment):
    if not can_review(job, reviewer, reviewee):
        raise WorkflowError('Bạn không thể đánh giá trong trường hợp này.')
    if not 1 <= int(rating) <= 5:
        raise WorkflowError('Số sao phải từ 1 đến 5.')
    r = Review(job=job, reviewer=reviewer, reviewee=reviewee, rating=int(rating), comment=comment)
    db.session.add(r)
    db.session.flush()
    reviewee.recalc_rating()
    notify(reviewee, 'NEW_REVIEW', f'{reviewer.display_name} đã đánh giá bạn {rating}★ cho "{job.title}".',
           url_for('main.company_detail', company_id=reviewee.employer_profile.id)
           if reviewee.is_employer and reviewee.employer_profile else url_for('main.student_public', user_id=reviewee.id))
    return r


def pending_reviews(user):
    """Danh sách (job, đối tượng) mà user còn có thể đánh giá."""
    out = []
    if user.is_student:
        apps = db.session.scalars(user.applications.select().where(Application.status == 'COMPLETED')).all()
        for a in apps:
            if can_review(a.job, user, a.job.employer):
                out.append((a.job, a.job.employer))
    elif user.is_employer:
        apps = db.session.scalars(sa.select(Application).join(Application.job).where(
            Application.status == 'COMPLETED', Application.job.has(employer_id=user.id))).all()
        for a in apps:
            if can_review(a.job, user, a.student):
                out.append((a.job, a.student))
    return out
